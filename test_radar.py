"""Offline tests for Bounty Radar persistence, migration, delivery lifecycle, and radar.py daemon."""

import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

import db
import radar


class TestDatabaseMigrationAndPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_schema_migration_without_data_loss(self):
        """Test migrating an old schema table (8 columns with seen_at) to the new 6-state schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE listings (
                id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                reward TEXT,
                deadline TEXT,
                agent_access TEXT,
                url TEXT,
                seen_at TEXT
            )"""
        )
        conn.execute(
            """INSERT INTO listings VALUES (
                'legacy-1', 'superteam-earn', 'Legacy Bounty 1', '100 USDC',
                '2026-09-01', 'AGENT_ALLOWED', 'https://earn.superteam.fun/listing/leg-1',
                '2026-08-20T12:00:00Z'
            )"""
        )
        conn.execute(
            """INSERT INTO listings VALUES (
                'legacy-2', 'superteam-earn', 'Legacy Bounty 2', '500 USDC',
                '2026-09-02', 'HUMAN_ONLY', 'https://earn.superteam.fun/listing/leg-2',
                '2026-08-21T12:00:00Z'
            )"""
        )
        conn.commit()
        conn.close()

        db.init_db(self.db_path)

        conn = db.get_connection(self.db_path)
        cur = conn.execute("PRAGMA table_info(listings)")
        col_names = [r["name"] for r in cur.fetchall()]
        expected_cols = [
            "id", "source", "title", "reward", "deadline", "agent_access", "url",
            "seen_at", "delivery_state", "delivery_attempts", "next_retry_at",
            "delivered_at", "last_error", "updated_at"
        ]
        for col in expected_cols:
            self.assertIn(col, col_names)

        row1 = conn.execute("SELECT * FROM listings WHERE id = 'legacy-1'").fetchone()
        self.assertEqual(row1["delivery_state"], "delivered")
        self.assertEqual(row1["delivered_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(row1["title"], "Legacy Bounty 1")

        row2 = conn.execute("SELECT * FROM listings WHERE id = 'legacy-2'").fetchone()
        self.assertEqual(row2["delivery_state"], "delivered")
        conn.close()

    def test_migration_on_real_radar_db_copy(self):
        """If a radar.db exists in the repository, test non-destructive migration on its copy."""
        real_db = "radar.db"
        if os.path.exists(real_db):
            copy_path = os.path.join(self.temp_dir, "real_radar_copy.db")
            shutil.copy2(real_db, copy_path)
            
            conn = sqlite3.connect(copy_path)
            count_before = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            conn.close()

            db.init_db(copy_path)

            conn = db.get_connection(copy_path)
            count_after = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            self.assertEqual(count_before, count_after)
            conn.close()


class TestDeliveryLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")
        db.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_store_and_state_transitions(self):
        """Test full lifecycle: discovered/pending -> delivering -> delivered."""
        items = [
            {
                "id": "item-agent-1",
                "source": "superteam-earn",
                "title": "Agent Task 1",
                "reward": "250 USDC",
                "deadline": "2026-09-10",
                "agent_access": "AGENT_ALLOWED",
                "slug": "agent-task-1",
            },
            {
                "id": "item-human-1",
                "source": "superteam-earn",
                "title": "Human Task 1",
                "reward": "1000 USDC",
                "deadline": "2026-09-15",
                "agent_access": "HUMAN_ONLY",
                "slug": "human-task-1",
            },
        ]
        new_items = db.store_listings(items, db_path=self.db_path)
        self.assertEqual(len(new_items), 2)

        pending = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], "item-agent-1")
        self.assertEqual(pending[0]["delivery_state"], "pending")

        claimed = db.claim_delivery("item-agent-1", db_path=self.db_path)
        self.assertTrue(claimed)

        claimed_again = db.claim_delivery("item-agent-1", db_path=self.db_path)
        self.assertFalse(claimed_again)

        db.mark_delivered("item-agent-1", db_path=self.db_path)

        pending_after = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending_after), 0)

        conn = db.get_connection(self.db_path)
        row = conn.execute("SELECT * FROM listings WHERE id = 'item-agent-1'").fetchone()
        self.assertEqual(row["delivery_state"], "delivered")
        self.assertIsNotNone(row["delivered_at"])
        self.assertIsNone(row["last_error"])
        conn.close()

    def test_transient_failure_and_exponential_backoff(self):
        """Test transient failure transitions to retry_wait and eventually permanently_failed."""
        item = {
            "id": "item-retry-1",
            "source": "superteam-earn",
            "title": "Retry Task",
            "reward": "50 USDC",
            "deadline": "2026-09-10",
            "agent_access": "AGENT_ALLOWED",
            "slug": "retry-task",
        }
        db.store_listings([item], db_path=self.db_path)

        self.assertTrue(db.claim_delivery("item-retry-1", db_path=self.db_path))
        state1 = db.mark_transient_failure(
            "item-retry-1", "HTTP 429 Rate Limit", max_attempts=3, base_backoff_sec=10, db_path=self.db_path
        )
        self.assertEqual(state1, db.STATE_RETRY_WAIT)

        conn = db.get_connection(self.db_path)
        row = conn.execute("SELECT * FROM listings WHERE id = 'item-retry-1'").fetchone()
        self.assertEqual(row["delivery_state"], "retry_wait")
        self.assertEqual(row["delivery_attempts"], 1)
        self.assertIsNotNone(row["next_retry_at"])
        self.assertIn("HTTP 429", row["last_error"])

        past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        conn.execute("UPDATE listings SET next_retry_at = ? WHERE id = 'item-retry-1'", (past_time,))
        conn.commit()
        conn.close()

        pending = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending), 1)

        self.assertTrue(db.claim_delivery("item-retry-1", db_path=self.db_path))
        state2 = db.mark_transient_failure(
            "item-retry-1", "HTTP 500 Server Error", max_attempts=3, base_backoff_sec=10, db_path=self.db_path
        )
        self.assertEqual(state2, db.STATE_RETRY_WAIT)

        self.assertTrue(db.claim_delivery("item-retry-1", db_path=self.db_path))
        state3 = db.mark_transient_failure(
            "item-retry-1", "HTTP 503 Service Unavailable", max_attempts=3, base_backoff_sec=10, db_path=self.db_path
        )
        self.assertEqual(state3, db.STATE_PERMANENTLY_FAILED)

        conn = db.get_connection(self.db_path)
        row3 = conn.execute("SELECT * FROM listings WHERE id = 'item-retry-1'").fetchone()
        self.assertEqual(row3["delivery_state"], "permanently_failed")
        self.assertIn("Exceeded max attempts", row3["last_error"])
        conn.close()

    def test_permanent_failure_direct(self):
        """Test fatal client errors immediately transition to permanently_failed."""
        item = {
            "id": "item-fatal-1",
            "source": "superteam-earn",
            "title": "Fatal Task",
            "reward": "50 USDC",
            "deadline": "2026-09-10",
            "agent_access": "AGENT_ALLOWED",
            "slug": "fatal-task",
        }
        db.store_listings([item], db_path=self.db_path)
        self.assertTrue(db.claim_delivery("item-fatal-1", db_path=self.db_path))
        db.mark_permanent_failure("item-fatal-1", "HTTP 400 Bad Request: Invalid webhook payload", db_path=self.db_path)

        conn = db.get_connection(self.db_path)
        row = conn.execute("SELECT * FROM listings WHERE id = 'item-fatal-1'").fetchone()
        self.assertEqual(row["delivery_state"], "permanently_failed")
        self.assertIn("HTTP 400", row["last_error"])
        conn.close()

    def test_crash_recovery_from_delivering_state(self):
        """Test that stalled delivering records are recovered."""
        item = {
            "id": "item-stalled-1",
            "source": "superteam-earn",
            "title": "Stalled Task",
            "reward": "100 USDC",
            "deadline": "2026-09-10",
            "agent_access": "AGENT_ALLOWED",
            "slug": "stalled-task",
        }
        db.store_listings([item], db_path=self.db_path)
        self.assertTrue(db.claim_delivery("item-stalled-1", db_path=self.db_path))

        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with db.get_connection(self.db_path) as conn:
            conn.execute("UPDATE listings SET updated_at = ? WHERE id = 'item-stalled-1'", (past_time,))

        recovered_count = db.recover_stale_delivering(timeout_seconds=300, db_path=self.db_path)
        self.assertEqual(recovered_count, 1)

        conn = db.get_connection(self.db_path)
        row = conn.execute("SELECT * FROM listings WHERE id = 'item-stalled-1'").fetchone()
        self.assertEqual(row["delivery_state"], "retry_wait")
        self.assertIn("recovered", row["last_error"])
        conn.close()

    def test_secret_redaction(self):
        """Test that tokens and secrets are sanitized from error messages."""
        err_telegram = "urllib.error.HTTPError: HTTP Error 401: Unauthorized for https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage"
        sanitized_tg = db.sanitize_error(err_telegram)
        self.assertNotIn("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", sanitized_tg)
        self.assertIn("[REDACTED_TELEGRAM_TOKEN]", sanitized_tg)

        err_discord = "HTTP 400 Bad Request: url https://discord.com/api/webhooks/123456789012345678/aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"
        sanitized_dc = db.sanitize_error(err_discord)
        self.assertNotIn("aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789", sanitized_dc)
        self.assertIn("[REDACTED_DISCORD_TOKEN]", sanitized_dc)


class TestRadarPoller(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")
        os.environ["RADAR_DB"] = self.db_path
        db.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @mock.patch.object(radar.urllib.request, "urlopen")
    def test_fetch_superteam_headers_and_parsing(self, mock_urlopen):
        raw_items = [
            {
                "id": "item-1",
                "slug": "bounty-1",
                "title": "Bounty One",
                "rewardAmount": 500,
                "token": "USDC",
                "deadline": "2026-09-01T00:00:00.000Z",
                "agentAccess": "AGENT_ALLOWED",
            },
            {
                "id": "item-2",
                "slug": "bounty-2",
                "title": "Bounty Two",
                "rewardAmount": None,
                "token": None,
                "deadline": None,
                "agentAccess": "HUMAN_ONLY",
            },
            {
                "id": "invalid-no-slug",
                "slug": None,
                "title": "No slug",
                "agentAccess": "AGENT_ALLOWED",
            },
        ]
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(raw_items).encode("utf-8")
        resp.__enter__ = lambda s: resp
        resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = resp

        items = radar.fetch_superteam()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "item-1")
        self.assertEqual(items[0]["reward"], "500 USDC")
        self.assertEqual(items[0]["deadline"], "2026-09-01")
        self.assertEqual(items[0]["url"], "https://earn.superteam.fun/listing/bounty-1")

        req_call = mock_urlopen.call_args[0][0]
        self.assertEqual(req_call.headers.get("Accept"), "application/json")
        self.assertIn("Mozilla/5.0", req_call.headers.get("User-agent"))

    @mock.patch.object(radar.urllib.request, "urlopen")
    def test_discord_delivery_user_agent_and_payload(self, mock_urlopen):
        resp = mock.MagicMock()
        resp.status = 204
        resp.__enter__ = lambda s: resp
        resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = resp

        item = {
            "title": "Test Bounty",
            "reward": "100 USDC",
            "deadline": "2026-09-05",
            "url": "https://earn.superteam.fun/listing/test-bounty",
        }
        webhook_url = "https://discord.com/api/webhooks/123/fake_token"
        radar.deliver_discord(item, webhook_url)

        req_call = mock_urlopen.call_args[0][0]
        self.assertEqual(req_call.headers.get("User-agent"), "bounty-radar/1.0")
        self.assertEqual(req_call.headers.get("Content-type"), "application/json")
        payload = json.loads(req_call.data.decode("utf-8"))
        self.assertIn("🤑 NEW bounty: Test Bounty", payload["content"])
        self.assertIn("💰 100 USDC", payload["content"])

    @mock.patch.object(radar.urllib.request, "urlopen")
    def test_telegram_delivery_payload(self, mock_urlopen):
        resp = mock.MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: resp
        resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = resp

        item = {
            "title": "Telegram Bounty",
            "reward": "300 USDC",
            "deadline": "2026-09-08",
            "url": "https://earn.superteam.fun/listing/tg-bounty",
        }
        radar.deliver_telegram(item, token="tg_token_123", chat="tg_chat_456")

        req_call = mock_urlopen.call_args[0][0]
        self.assertIn("/bottg_token_123/sendMessage", req_call.full_url)
        payload = json.loads(req_call.data.decode("utf-8"))
        self.assertEqual(payload["chat_id"], "tg_chat_456")
        self.assertIn("🤑 NEW bounty: Telegram Bounty", payload["text"])

    @mock.patch("radar.time.sleep", return_value=None)
    @mock.patch.object(radar.urllib.request, "urlopen")
    def test_batch_larger_than_10_without_data_loss(self, mock_urlopen, mock_sleep):
        """Verify that when 25 listings arrive, all 25 are delivered without slicing or loss."""
        resp = mock.MagicMock()
        resp.status = 204
        resp.__enter__ = lambda s: resp
        resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = resp

        # Create 25 items
        items = [
            {
                "id": f"batch-{i}",
                "slug": f"batch-slug-{i}",
                "source": "superteam-earn",
                "title": f"Bounty {i}",
                "reward": f"{i*10} USDC",
                "deadline": "2026-09-01",
                "agent_access": "AGENT_ALLOWED",
            }
            for i in range(25)
        ]
        db.store_listings(items, db_path=self.db_path)

        os.environ["RADAR_CHANNEL"] = "discord"
        os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/123/fake"

        delivered, transient_errs, permanent_errs = radar.deliver_pending(channel="discord")
        self.assertEqual(delivered, 25)
        self.assertEqual(transient_errs, 0)
        self.assertEqual(permanent_errs, 0)
        self.assertEqual(mock_urlopen.call_count, 25)

        # All items should now be delivered in the DB
        pending = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending), 0)

        conn = db.get_connection(self.db_path)
        delivered_count = conn.execute("SELECT COUNT(*) FROM listings WHERE delivery_state = 'delivered'").fetchone()[0]
        self.assertEqual(delivered_count, 25)
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
