"""Offline tests for Bounty Radar A2A server and SSRF defenses. No live services contacted."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import a2a_server
import db
import enrich


def rpc(method, params=None, rid=1):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
    ).encode("utf-8")
    result, status = a2a_server.handle_request(body)
    return status, result


class TestCardAndEndpoints(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")
        os.environ["RADAR_DB"] = self.db_path
        db.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_well_known_agent_card_served(self):
        """Test GET /.well-known/agent-card.json returns valid A2A v0.3 card."""
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/.well-known/agent-card.json"}
        chunks = a2a_server.app(environ, lambda status, headers: None)
        card = json.loads(b"".join(chunks).decode("utf-8"))
        self.assertEqual(card["protocolVersion"], "0.3.0")
        self.assertEqual(len(card["skills"]), 3)
        ids = {s["id"] for s in card["skills"]}
        self.assertEqual(
            ids,
            {
                "opportunity_feed_subscription",
                "opportunity_enrichment_lookup",
                "evaluation_contract_validation",
            },
        )

    def test_a2a_get_card_served(self):
        """Test GET /a2a returns valid card."""
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/a2a"}
        chunks = a2a_server.app(environ, lambda status, headers: None)
        card = json.loads(b"".join(chunks).decode("utf-8"))
        self.assertEqual(card["protocolVersion"], "0.3.0")

    def test_dynamic_card_public_url(self):
        """Test that public URL is taken from config and not fabricated."""
        with mock.patch.dict(os.environ, {"A2A_PUBLIC_URL": "https://radar.example.com/a2a"}):
            card = a2a_server.get_agent_card()
            self.assertEqual(card["url"], "https://radar.example.com/a2a")

        with mock.patch.dict(os.environ, {"A2A_PUBLIC_URL": "", "PUBLIC_URL": "", "A2A_PORT": "9090"}):
            card = a2a_server.get_agent_card()
            self.assertEqual(card["url"], "http://localhost:9090/a2a")

    def test_health(self):
        """Test GET /health returns 200 ok."""
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/health"}
        chunks = a2a_server.app(environ, lambda status, headers: None)
        self.assertEqual(json.loads(b"".join(chunks).decode("utf-8"))["status"], "ok")


class TestJSONRPC(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")
        os.environ["RADAR_DB"] = self.db_path
        db.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_error(self):
        result, status = a2a_server.handle_request(b"{not json")
        self.assertEqual(result["error"]["code"], -32700)

    def test_invalid_request(self):
        result, status = a2a_server.handle_request(b'"just a string"')
        self.assertEqual(result["error"]["code"], -32600)

        # Missing jsonrpc 2.0 version
        body = json.dumps({"id": 1, "method": "message/send"}).encode("utf-8")
        result, status = a2a_server.handle_request(body)
        self.assertEqual(result["error"]["code"], -32600)

    def test_method_not_found(self):
        status, result = rpc("no/such/method")
        self.assertEqual(result["error"]["code"], -32601)

    def test_message_send_requires_text(self):
        status, result = rpc("message/send", {"message": {"parts": []}})
        self.assertEqual(result["error"]["code"], -32602)

    def test_tasks_lifecycle(self):
        # Create a task via message/send
        status, result = rpc(
            "message/send",
            {"message": {"parts": [{"kind": "text", "text": "hello"}]}},
        )
        self.assertIn("result", result)
        task_id = result["result"]["id"]
        self.assertEqual(result["result"]["status"]["state"], "completed")

        # Query task via tasks/get
        status, get_res = rpc("tasks/get", {"id": task_id})
        self.assertEqual(get_res["result"]["id"], task_id)

        # Cancel task via tasks/cancel
        status, cancel_res = rpc("tasks/cancel", {"id": task_id})
        self.assertEqual(cancel_res["result"]["status"]["state"], "canceled")

    def test_tasks_get_unknown(self):
        status, result = rpc("tasks/get", {"id": "nope-not-found"})
        self.assertEqual(result["error"]["code"], -32602)

    def test_tasks_cancel_unknown(self):
        status, result = rpc("tasks/cancel", {"id": "nope-not-found"})
        self.assertEqual(result["error"]["code"], -32602)

    def test_request_size_limit_enforcement(self):
        """Test that requests exceeding MAX_REQUEST_SIZE are rejected."""
        oversized = b"a" * (a2a_server.MAX_REQUEST_SIZE + 10)
        result, status = a2a_server.handle_request(oversized)
        self.assertEqual(result["error"]["code"], -32600)


class TestSSRFDefenseAndEnrichment(unittest.TestCase):
    def test_ssrf_url_rejections(self):
        """Test that SSRF attempts to private networks or external domains are rejected."""
        # Cloud metadata service
        self.assertIsNone(enrich.extract_slug("http://169.254.169.254/latest/meta-data"))
        self.assertEqual(enrich.enrich_listing("http://169.254.169.254/latest/meta-data"), {})

        # Localhost
        self.assertIsNone(enrich.extract_slug("http://localhost:8080/admin"))
        self.assertIsNone(enrich.extract_slug("http://127.0.0.1:8080/secret"))

        # File scheme
        self.assertIsNone(enrich.extract_slug("file:///etc/passwd"))

        # Arbitrary external domains
        self.assertIsNone(enrich.extract_slug("https://attacker.com/listing/exploit"))
        self.assertIsNone(enrich.extract_slug("https://evil-superteam.fun/listing/fake"))

        # Directory traversal / command injection in slug
        self.assertIsNone(enrich.extract_slug("../../etc/passwd"))
        self.assertIsNone(enrich.extract_slug("bounty; rm -rf /"))

    def test_valid_slug_and_url_accepted(self):
        """Test that valid Superteam Earn URLs and slugs are extracted properly."""
        self.assertEqual(
            enrich.extract_slug("https://earn.superteam.fun/listing/zns-sol"),
            "zns-sol",
        )
        self.assertEqual(
            enrich.extract_slug("https://superteam.fun/listing/frontend-bounty_1"),
            "frontend-bounty_1",
        )
        self.assertEqual(enrich.extract_slug("zns-sol"), "zns-sol")

    @mock.patch.object(enrich.urllib.request, "urlopen")
    def test_enrich_listing_mocked_html(self, mock_urlopen):
        fake_html = """
        <html><head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "listing": {
                "description": "<p>Build a React UI &amp; Solana bot</p>",
                "skills": [{"skills": "Frontend", "subskills": ["React"]}],
                "eligibility": [{"type": "text", "question": "GitHub profile"}],
                "region": "Global",
                "requirements": "Must submit PR"
              }
            }
          }
        }
        </script></head><body>Content</body></html>
        """
        resp = mock.MagicMock()
        resp.status = 200
        resp.read.return_value = fake_html.encode("utf-8")
        resp.__enter__ = lambda s: resp
        resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = resp

        res = enrich.enrich_listing("https://earn.superteam.fun/listing/zns-sol")
        self.assertEqual(res["description_text"], "Build a React UI & Solana bot")
        self.assertEqual(res["region"], "Global")
        self.assertEqual(len(res["skills"]), 1)
        self.assertEqual(len(res["eligibility"]), 1)
        self.assertEqual(res["requirements"], "Must submit PR")


class TestSkills(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")
        os.environ["RADAR_DB"] = self.db_path
        db.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_feed_subscription_no_refresh(self):
        res = a2a_server.skill_feed_subscription({})
        self.assertIn("opportunities", res)

    def test_enrichment_lookup_requires_ref(self):
        with self.assertRaises(ValueError):
            a2a_server.skill_enrichment_lookup({})

    def test_validate_evaluation_valid(self):
        sample = (
            "PARSE SUCCESS: YES\nELIGIBILITY UNDERSTOOD: YES\n"
            "DECISION: REJECT\nCAPABILITY FIT: LOW\nREASON: Capability does not match\n"
            "MISSING INFORMATION: [none]\nREQUIRED BEFORE ACTION: [n/a]\n"
            "AUTO-CONSUMABLE: PARTIAL"
        )
        res = a2a_server.validate_evaluation(sample)
        self.assertTrue(res["valid"], res)

    def test_validate_evaluation_missing_fields(self):
        res = a2a_server.validate_evaluation("PARSE SUCCESS: YES only")
        self.assertFalse(res["valid"])
        self.assertIn("decision", res["missing_fields"])

    def test_validate_evaluation_conflicting_enum(self):
        sample = (
            "DECISION: ACCEPT\nDECISION: REJECT\nPARSE SUCCESS: YES\n"
            "ELIGIBILITY UNDERSTOOD: YES\nCAPABILITY FIT: HIGH\nREASON: Test\n"
            "AUTO-CONSUMABLE: YES"
        )
        res = a2a_server.validate_evaluation(sample)
        self.assertFalse(res["valid"])
        self.assertIn("decision", res["invalid_values"])

    def test_route_help(self):
        text = a2a_server.route("hello", {})
        self.assertIn("Bounty Radar skills:", text)

    def test_route_validate(self):
        sample = (
            "PARSE SUCCESS: YES\nELIGIBILITY UNDERSTOOD: YES\nDECISION: ACCEPT\n"
            "CAPABILITY FIT: MEDIUM\nREASON: Good match\nMISSING INFORMATION: []\n"
            "REQUIRED BEFORE ACTION: []\nAUTO-CONSUMABLE: YES"
        )
        out = a2a_server.route(
            "validate this evaluation response " + json.dumps({"response_text": sample}), {}
        )
        data = json.loads(out)
        self.assertTrue(data["valid"])

    @mock.patch.object(a2a_server, "fetch_listings")
    def test_route_feed_mocked(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "source": "superteam-earn",
                "id": f"x-{i}",
                "slug": f"x-slug-{i}",
                "title": f"Title {i}",
                "reward": "1 USDC",
                "deadline": "2026-09-01",
                "url": f"https://earn.superteam.fun/listing/x-slug-{i}",
                "agent_access": "AGENT_ALLOWED",
                "observed_at": "2026-08-24T00:00:00Z",
                "provenance": "test",
                "skills": [],
                "eligibility": [],
                "region": None,
                "requirements": None,
                "description_text": "",
            }
            for i in range(3)
        ]
        out = a2a_server.route("show new opportunities from feed", {"refresh": True})
        data = json.loads(out)
        self.assertGreaterEqual(len(data["opportunities"]), 3)
        self.assertEqual(data["newly_discovered_on_refresh"], 3)

        # Second pass: dedup means 0 newly discovered
        out2 = a2a_server.route("show new opportunities from feed", {"refresh": True})
        data2 = json.loads(out2)
        self.assertEqual(data2["newly_discovered_on_refresh"], 0)
        self.assertEqual(mock_fetch.call_count, 2)

    @mock.patch.object(enrich, "enrich_listing")
    def test_route_enrich_mocked(self, mock_enrich):
        mock_enrich.return_value = {
            "description_text": "full text",
            "skills": [],
            "eligibility": [],
            "region": "Global",
            "requirements": None,
        }
        db.record_opportunity(
            {"id": "e92e317b-0d0f-49f4-9937-0623d4816df6", "title": "ZNS"},
            enriched=False,
            db_path=self.db_path,
        )
        out = a2a_server.route(
            "enrich opportunity "
            + json.dumps({"id": "e92e317b-0d0f-49f4-9937-0623d4816df6"}),
            {},
        )
        data = json.loads(out)
        self.assertTrue(data["enrichment_complete"])
        mock_enrich.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
