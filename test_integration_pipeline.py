"""End-to-end integration test for the full Bounty Radar pipeline.

Validates the complete flow:
source fixture -> ingestion -> enrichment -> persistence -> evaluation task -> notification delivery -> delivered state
"""

import json
import os
import shutil
import tempfile
import unittest
import urllib.request
from unittest import mock

import a2a_server
import db
import enrich
import radar


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")
        os.environ["RADAR_DB"] = self.db_path
        db.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @mock.patch("radar.time.sleep", return_value=None)
    @mock.patch("urllib.request.urlopen")
    def test_complete_end_to_end_flow(self, mock_urlopen, mock_sleep):
        # ------------------------------------------------------------- 1. Source Fixture
        source_fixture = [
            {
                "id": "e92e317b-0d0f-49f4-9937-0623d4816df6",
                "slug": "zns-sol-integration",
                "title": "ZNS Domain Lookup Bot",
                "rewardAmount": 750,
                "token": "USDC",
                "deadline": "2026-09-15T00:00:00.000Z",
                "agentAccess": "AGENT_ALLOWED",
            }
        ]

        mock_detail_html = """
        <html><head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "listing": {
                "description": "<p>Build automated Solana agent for ZNS registry</p>",
                "skills": [{"skills": "Solana", "subskills": ["Anchor", "Rust"]}],
                "eligibility": [{"type": "text", "question": "GitHub repo URL", "optional": false}],
                "region": "Global",
                "requirements": "Must submit open source repo with unit tests"
              }
            }
          }
        }
        </script></head><body></body></html>
        """

        def mock_urlopen_router(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            resp = mock.MagicMock()

            if "api/listings" in url:
                resp.status = 200
                resp.read.return_value = json.dumps(source_fixture).encode("utf-8")
            elif "listing/zns-sol-integration" in url:
                resp.status = 200
                resp.read.return_value = mock_detail_html.encode("utf-8")
            elif "discord.com/api/webhooks" in url:
                resp.status = 204
                resp.read.return_value = b""
            elif "api.telegram.org" in url:
                resp.status = 200
                resp.read.return_value = b'{"ok":true}'
            else:
                resp.status = 200
                resp.read.return_value = b"{}"

            resp.__enter__ = lambda s: resp
            resp.__exit__ = mock.Mock(return_value=False)
            return resp

        mock_urlopen.side_effect = mock_urlopen_router

        # ------------------------------------------------------------- 2. Ingestion
        ingested = radar.fetch_superteam()
        self.assertEqual(len(ingested), 1)
        item = ingested[0]
        self.assertEqual(item["id"], "e92e317b-0d0f-49f4-9937-0623d4816df6")
        self.assertEqual(item["agent_access"], "AGENT_ALLOWED")

        # ------------------------------------------------------------- 3. Detail Enrichment
        enrichment_data = enrich.enrich_listing(item["url"])
        self.assertIn("Solana agent", enrichment_data["description_text"])
        self.assertEqual(len(enrichment_data["skills"]), 1)

        # ------------------------------------------------------------- 4. Persistence
        new_stored = db.store_listings([item], db_path=self.db_path)
        self.assertEqual(len(new_stored), 1)

        # Build full normalized Opportunity Contract object
        opportunity_contract = {
            "source": item["source"],
            "id": item["id"],
            "title": item["title"],
            "reward": item["reward"],
            "deadline": item["deadline"],
            "url": item["url"],
            "agent_access": item["agent_access"],
            "observed_at": db.utcnow(),
            "provenance": "superteam.fun/api/listings?type=bounty&filter=agents",
            "skills": enrichment_data.get("skills", []),
            "eligibility": enrichment_data.get("eligibility", []),
            "region": enrichment_data.get("region"),
            "requirements": enrichment_data.get("requirements"),
            "description_text": enrichment_data.get("description_text", ""),
        }
        db.record_opportunity(opportunity_contract, enriched=True, db_path=self.db_path)

        # Verify initial DB delivery state is 'pending'
        pending = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], item["id"])
        self.assertEqual(pending[0]["delivery_state"], "pending")

        # ------------------------------------------------------------- 5. Evaluation Task via A2A
        evaluator_response_text = (
            "PARSE SUCCESS: YES\n"
            "ELIGIBILITY UNDERSTOOD: YES\n"
            "DECISION: ACCEPT\n"
            "CAPABILITY FIT: HIGH\n"
            "REASON: Agent has validated Solana and Anchor capability with test coverage.\n"
            "MISSING INFORMATION: []\n"
            "REQUIRED BEFORE ACTION: [Human confirmation of PR link]\n"
            "AUTO-CONSUMABLE: YES"
        )
        rpc_body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [
                            {
                                "kind": "text",
                                "text": "validate evaluation response "
                                + json.dumps({"response_text": evaluator_response_text}),
                            }
                        ],
                    }
                },
            }
        ).encode("utf-8")

        result, status_code = a2a_server.handle_request(rpc_body)
        self.assertEqual(status_code, 200)
        self.assertEqual(result["id"], 42)
        task = result["result"]
        self.assertEqual(task["status"]["state"], "completed")
        reply_text = task["status"]["message"]["parts"][0]["text"]
        eval_result = json.loads(reply_text)
        self.assertTrue(eval_result["valid"])
        self.assertEqual(len(eval_result["missing_fields"]), 0)

        # ------------------------------------------------------------- 6. Notification Delivery
        os.environ["RADAR_CHANNEL"] = "discord"
        os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/999/fake_token"

        delivered, transient_errs, permanent_errs = radar.deliver_pending(channel="discord")
        self.assertEqual(delivered, 1)
        self.assertEqual(transient_errs, 0)
        self.assertEqual(permanent_errs, 0)

        # ------------------------------------------------------------- 7. Delivered State Verification
        conn = db.get_connection(self.db_path)
        row = conn.execute("SELECT * FROM listings WHERE id = ?", (item["id"],)).fetchone()
        self.assertEqual(row["delivery_state"], "delivered")
        self.assertEqual(row["delivery_attempts"], 1)
        self.assertIsNotNone(row["delivered_at"])
        self.assertIsNone(row["last_error"])

        # Check opportunities table
        opp_row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (item["id"],)).fetchone()
        self.assertIsNotNone(opp_row)
        opp_obj = json.loads(opp_row["object_json"])
        self.assertEqual(opp_obj["id"], item["id"])
        self.assertEqual(opp_obj["title"], "ZNS Domain Lookup Bot")
        self.assertIn("Solana", opp_obj["skills"][0]["skills"])
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
