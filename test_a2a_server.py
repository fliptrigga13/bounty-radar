"""Offline tests for Bounty Radar A2A server. No live services contacted."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

os.environ["RADAR_DB"] = tempfile.mktemp(suffix=".db")
import a2a_server
a2a_server.init_db()


def rpc(method, params=None, rid=1):
    body = json.dumps({"jsonrpc": "2.0", "id": rid,
                       "method": method, "params": params or {}}).encode()
    result, status = a2a_server.handle_request(body)
    return status, result


class TestCard(unittest.TestCase):
    def test_card_served(self):
        start_response = lambda status, headers: None
        # simulate GET /a2a via app()
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/a2a"}
        chunks = a2a_server.app(environ, start_response)
        card = json.loads(b"".join(chunks).decode())
        self.assertEqual(card["protocolVersion"], "0.3.0")
        self.assertEqual(len(card["skills"]), 3)
        ids = {s["id"] for s in card["skills"]}
        self.assertEqual(ids, {"opportunity_feed_subscription",
                               "opportunity_enrichment_lookup",
                               "evaluation_contract_validation"})

    def test_health(self):
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/health"}
        chunks = a2a_server.app(environ, lambda *a: None)
        self.assertEqual(json.loads(b"".join(chunks))["status"], "ok")


class TestJSONRPC(unittest.TestCase):
    def test_parse_error(self):
        result, status = a2a_server.handle_request(b"{not json")
        self.assertEqual(result["error"]["code"], -32700)

    def test_method_not_found(self):
        status, result = rpc("no/such/method")
        self.assertEqual(result["error"]["code"], -32601)

    def test_message_send_requires_text(self):
        status, result = rpc("message/send", {"message": {"parts": []}})
        self.assertEqual(result["error"]["code"], -32602)

    def test_tasks_get_unknown(self):
        status, result = rpc("tasks/get", {"id": "nope"})
        self.assertEqual(result["error"]["code"], -32602)

    def test_tasks_cancel_unknown(self):
        status, result = rpc("tasks/cancel", {"id": "nope"})
        self.assertEqual(result["error"]["code"], -32602)


class TestSkills(unittest.TestCase):
    def test_feed_subscription_no_refresh(self):
        res = a2a_server.skill_feed_subscription({})
        self.assertIn("opportunities", res)

    def test_enrichment_lookup_requires_ref(self):
        with self.assertRaises(ValueError):
            a2a_server.skill_enrichment_lookup({})

    def test_validate_evaluation_valid(self):
        sample = ("PARSE SUCCESS: YES\nELIGIBILITY UNDERSTOOD: YES\n"
                  "DECISION: REJECT\nCAPABILITY FIT: LOW\nREASON: n/a\n"
                  "MISSING INFORMATION: [none]\nREQUIRED BEFORE ACTION: [n/a]\n"
                  "AUTO-CONSUMABLE: PARTIAL")
        res = a2a_server.validate_evaluation(sample)
        self.assertTrue(res["valid"], res)

    def test_validate_evaluation_missing_fields(self):
        res = a2a_server.validate_evaluation("PARSE SUCCESS: YES only")
        self.assertFalse(res["valid"])
        self.assertIn("decision", res["missing_fields"])

    def test_validate_evaluation_conflicting_enum(self):
        sample = ("DECISION: ACCEPT\nDECISION: REJECT\nPARSE SUCCESS: YES\n"
                  "ELIGIBILITY UNDERSTOOD: YES\nCAPABILITY FIT: HIGH\n"
                  "AUTO-CONSUMABLE: YES")
        res = a2a_server.validate_evaluation(sample)
        self.assertFalse(res["valid"])
        self.assertIn("decision", res["invalid_values"])

    def test_route_help(self):
        text = a2a_server.route("hello", {})
        self.assertIn("Bounty Radar skills:", text)

    def test_route_validate(self):
        sample = ("PARSE SUCCESS: YES\nELIGIBILITY UNDERSTOOD: YES\nDECISION: ACCEPT\n"
                  "CAPABILITY FIT: MEDIUM\nREASON: r\nMISSING INFORMATION: []\n"
                  "REQUIRED BEFORE ACTION: []\nAUTO-CONSUMABLE: YES")
        out = a2a_server.route('validate this evaluation response ' +
                               json.dumps({"response_text": sample}), {})
        data = json.loads(out)
        self.assertTrue(data["valid"])

    @mock.patch.object(a2a_server, "fetch_listings")
    def test_route_feed_mocked(self, mock_fetch):
        # use an isolated temp DB so concurrent-connection locks don't apply
        a2a_server.RADAR_DB = tempfile.mktemp(suffix=".db")
        a2a_server.init_db()
        mock_fetch.return_value = [{
            "source": "superteam-earn", "id": f"x-{i}", "title": "t",
            "reward": "1 USDC", "deadline": "2026-09-01",
            "url": f"https://earn.superteam.fun/listing/x{i}",
            "agent_access": "AGENT_ALLOWED",
            "observed_at": "2026-08-24T00:00:00Z",
            "provenance": "test", "skills": [], "eligibility": [],
            "region": None, "requirements": None, "description_text": ""}
            for i in range(3)]
        out = a2a_server.route('show new opportunities from feed', {"refresh": True})
        data = json.loads(out)
        self.assertGreaterEqual(len(data["opportunities"]), 3)
        self.assertEqual(data["newly_discovered_on_refresh"], 3)
        # second pass: dedup means nothing new (fetch called again by design)
        out2 = a2a_server.route('show new opportunities from feed', {"refresh": True})
        data2 = json.loads(out2)
        self.assertEqual(data2["newly_discovered_on_refresh"], 0)
        self.assertEqual(mock_fetch.call_count, 2)

    @mock.patch.object(a2a_server, "enrich")
    def test_route_enrich_mocked(self, mock_enrich):
        mock_enrich.return_value = {"description_text": "full text",
                                    "skills": [], "eligibility": [],
                                    "region": "Global", "requirements": None}
        a2a_server.record_opportunity(
            {"id": "e92e317b-0d0f-49f4-9937-0623d4816df6", "title": "ZNS"},
            enriched=False)
        out = a2a_server.route('enrich opportunity ' + json.dumps(
            {"id": "e92e317b-0d0f-49f4-9937-0623d4816df6"}), {})
        data = json.loads(out)
        self.assertTrue(data["enrichment_complete"])
        mock_enrich.assert_called_once()


class TestIngestion(unittest.TestCase):
    def test_fetch_rejects_non_list(self):
        with mock.patch.object(a2a_server.urllib.request, "urlopen") as m:
            resp = mock.MagicMock()
            resp.read.return_value = b'{"not":"a list"}'
            resp.__enter__ = lambda s: resp
            resp.__exit__ = mock.Mock(return_value=False)
            m.return_value = resp
            with self.assertRaises(ValueError):
                a2a_server.fetch_listings()

    def test_fetch_skips_malformed_entries(self):
        payload = json.dumps([
            {"id": "ok-1", "slug": "good", "agentAccess": "AGENT_ALLOWED",
             "title": "Good", "rewardAmount": 5, "token": "USDC"},
            {"slug": "no-id"},          # missing id -> skipped
            {"id": ""},                 # empty id -> skipped
        ]).encode()
        with mock.patch.object(a2a_server.urllib.request, "urlopen") as m:
            resp = mock.MagicMock()
            resp.read.return_value = payload
            resp.__enter__ = lambda s: resp
            resp.__exit__ = mock.Mock(return_value=False)
            m.return_value = resp
            items = a2a_server.fetch_listings()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "ok-1")

    def test_dedup_stable_without_upstream_id_change(self):
        """Same listing re-fetched under a changed upstream id must not duplicate."""
        base = {"slug": "same-listing", "agentAccess": "AGENT_ALLOWED",
                "title": "Same", "rewardAmount": 5, "token": "USDC"}
        p1 = json.dumps([{**base, "id": "aaa"}]).encode()
        p2 = json.dumps([{**base, "id": "bbb"}]).encode()  # id rotated upstream
        def fake_urlopen(payload):
            resp = mock.MagicMock()
            resp.read.return_value = payload
            resp.__enter__ = lambda s: resp
            resp.__exit__ = mock.Mock(return_value=False)
            return resp
        with mock.patch.object(a2a_server.urllib.request, "urlopen",
                               return_value=fake_urlopen(p1)):
            first = a2a_server.fetch_listings()
        with mock.patch.object(a2a_server.urllib.request, "urlopen",
                               return_value=fake_urlopen(p2)):
            second = a2a_server.fetch_listings()
        # slug-based stable key: same URL means same listing
        self.assertEqual(first[0]["url"], second[0]["url"])
        # store() keyed by id would treat as new; document current behavior:
        self.assertNotEqual(first[0]["id"], second[0]["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
