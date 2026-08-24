"""Offline tests for Bounty Radar persistence, migration, delivery lifecycle, and secret redaction."""

import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

import db


class TestDatabaseMigrationAndPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_radar.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_schema_migration_without_data_loss(self):
        """Test migrating an old schema table (8 columns with seen_at) to the new 6-state schema."""
        # 1. Create a legacy table with old schema
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

        # 2. Run init_db migration
        db.init_db(self.db_path)

        # 3. Verify columns and data preservation
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

        # Legacy items should have been marked as 'delivered' so they aren't spammed
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
            
            # Count before
            conn = sqlite3.connect(copy_path)
            count_before = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            conn.close()

            # Run migration
            db.init_db(copy_path)

            # Count after
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

        # Agent item should be pending; Human item should be discovered
        pending = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], "item-agent-1")
        self.assertEqual(pending[0]["delivery_state"], "pending")

        # Claim delivery
        claimed = db.claim_delivery("item-agent-1", db_path=self.db_path)
        self.assertTrue(claimed)

        # Second claim should fail (already delivering)
        claimed_again = db.claim_delivery("item-agent-1", db_path=self.db_path)
        self.assertFalse(claimed_again)

        # Mark delivered
        db.mark_delivered("item-agent-1", db_path=self.db_path)

        # Verify delivered state
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

        # 1st attempt
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

        # Simulate time passing by manually updating next_retry_at to past
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        conn.execute("UPDATE listings SET next_retry_at = ? WHERE id = 'item-retry-1'", (past_time,))
        conn.commit()
        conn.close()

        # Should appear in pending deliveries again
        pending = db.get_pending_deliveries(db_path=self.db_path)
        self.assertEqual(len(pending), 1)

        # 2nd attempt
        self.assertTrue(db.claim_delivery("item-retry-1", db_path=self.db_path))
        state2 = db.mark_transient_failure(
            "item-retry-1", "HTTP 500 Server Error", max_attempts=3, base_backoff_sec=10, db_path=self.db_path
        )
        self.assertEqual(state2, db.STATE_RETRY_WAIT)

        # 3rd attempt (max_attempts = 3) -> should become permanently_failed
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

        # Manually set updated_at to 10 minutes ago
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with db.get_connection(self.db_path) as conn:
            conn.execute("UPDATE listings SET updated_at = ? WHERE id = 'item-stalled-1'", (past_time,))

        # Run recovery with 300s timeout
        recovered_count = db.recover_stale_delivering(timeout_seconds=300, db_path=self.db_path)
        self.assertEqual(recovered_count, 1)

        conn = db.get_connection(self.db_path)
        row = conn.execute("SELECT * FROM listings WHERE id = 'item-stalled-1'").fetchone()
        self.assertEqual(row["delivery_state"], "retry_wait")
        self.assertIn("recovered", row["last_error"])
        conn.close()

    def test_validation_rejects_missing_or_malformed_ids_and_slugs(self):
        """Test that records missing id or with malformed slugs/ids are rejected."""
        self.assertFalse(db.validate_listing_id(""))
        self.assertFalse(db.validate_listing_id("   "))
        self.assertFalse(db.validate_listing_id(None))
        self.assertTrue(db.validate_listing_id("valid-id-123"))

        self.assertFalse(db.validate_slug(""))
        self.assertFalse(db.validate_slug("invalid slug with spaces"))
        self.assertFalse(db.validate_slug("slug/with/slash"))
        self.assertFalse(db.validate_slug("../traversal"))
        self.assertTrue(db.validate_slug("valid-slug_123"))

        bad_items = [
            {"id": "", "slug": "slug1", "agent_access": "AGENT_ALLOWED"},
            {"id": "id2", "slug": "bad slug!", "agent_access": "AGENT_ALLOWED"},
            {"slug": "no-id", "agent_access": "AGENT_ALLOWED"},
        ]
        new_items = db.store_listings(bad_items, db_path=self.db_path)
        self.assertEqual(len(new_items), 0)

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

        err_bearer = "Authorization: Bearer my-secret-jwt-token-value-here"
        sanitized_b = db.sanitize_error(err_bearer)
        self.assertNotIn("my-secret-jwt-token-value-here", sanitized_b)
        self.assertIn("[REDACTED_TOKEN]", sanitized_b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
