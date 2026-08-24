"""Shared database persistence, schema migration, and delivery state lifecycle.

Provides WAL-mode SQLite connection management, safe non-destructive migrations,
atomic worker claims, crash recovery, bounded exponential backoff, and secret
redaction for Bounty Radar (radar.py and a2a_server.py).
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# Delivery lifecycle states
STATE_DISCOVERED = "discovered"
STATE_PENDING = "pending"
STATE_DELIVERING = "delivering"
STATE_DELIVERED = "delivered"
STATE_RETRY_WAIT = "retry_wait"
STATE_PERMANENTLY_FAILED = "permanently_failed"

VALID_STATES = {
    STATE_DISCOVERED,
    STATE_PENDING,
    STATE_DELIVERING,
    STATE_DELIVERED,
    STATE_RETRY_WAIT,
    STATE_PERMANENTLY_FAILED,
}

# Regex validation
SLUG_RE = re.compile(r"^[A-Za-z0-9\-_]+$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)

# Secret redaction patterns
REDACT_PATTERNS = [
    (re.compile(r"api\.telegram\.org/bot([^/]+)/", re.I), r"api.telegram.org/bot[REDACTED_TELEGRAM_TOKEN]/"),
    (re.compile(r"discord\.com/api/webhooks/(\d+)/([A-Za-z0-9_\-]+)", re.I), r"discord.com/api/webhooks/\1/[REDACTED_DISCORD_TOKEN]"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-_.]+", re.I), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(token=)[A-Za-z0-9\-_.]+", re.I), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(api[-_]?key[=:\s]+)[A-Za-z0-9\-_.]+", re.I), r"\1[REDACTED_KEY]"),
    (re.compile(r"(secret[=:\s]+)[A-Za-z0-9\-_.]+", re.I), r"\1[REDACTED_SECRET]"),
    (re.compile(r"(password[=:\s]+)[A-Za-z0-9\-_.]+", re.I), r"\1[REDACTED_PASSWORD]"),
]


def utcnow() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def sanitize_error(error_text: Any) -> str:
    """Redact tokens, webhook URLs, and secrets from error strings."""
    if error_text is None:
        return ""
    text = str(error_text)
    for pattern, replacement in REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:500]


def get_db_path() -> str:
    """Resolve active database path from environment."""
    return os.environ.get("RADAR_DB", "radar.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a WAL-mode SQLite connection with busy timeout and Row factory."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and run non-destructive migrations."""
    with get_connection(db_path) as conn:
        # Create legacy base table if not existing
        conn.execute(
            """CREATE TABLE IF NOT EXISTS listings (
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
            """CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                object_json TEXT NOT NULL,
                enriched INTEGER DEFAULT 0,
                created_at TEXT
            )"""
        )

        # Inspect columns in listings table for migration
        cur = conn.execute("PRAGMA table_info(listings)")
        existing_cols = {row["name"] for row in cur.fetchall()}

        # Safe non-destructive column additions
        new_columns = [
            ("delivery_state", "TEXT NOT NULL DEFAULT 'discovered'"),
            ("delivery_attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("next_retry_at", "TEXT"),
            ("delivered_at", "TEXT"),
            ("last_error", "TEXT"),
            ("updated_at", "TEXT"),
        ]

        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE listings ADD COLUMN {col_name} {col_def}")

        # For historical rows that had seen_at but no delivery_state recorded,
        # set them to delivered so upgrading doesn't re-deliver historical listings
        conn.execute(
            """UPDATE listings
               SET delivery_state = 'delivered',
                   delivered_at = seen_at,
                   updated_at = seen_at
               WHERE (delivery_state IS NULL OR delivery_state = 'discovered')
                 AND seen_at IS NOT NULL AND seen_at != ''
                 AND delivered_at IS NULL"""
        )

        # Create indices for fast lookup
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listings_delivery ON listings(delivery_state, next_retry_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_opportunities_created ON opportunities(created_at)"
        )


def validate_listing_id(listing_id: Any) -> bool:
    """Validate that listing ID is a non-empty, non-whitespace string."""
    if not isinstance(listing_id, str):
        return False
    lid = listing_id.strip()
    return len(lid) > 0 and len(lid) <= 128


def validate_slug(slug: Any) -> bool:
    """Validate that slug contains only safe URL characters."""
    if not isinstance(slug, str):
        return False
    s = slug.strip()
    return bool(s and SLUG_RE.match(s))


def store_listings(listings: List[Dict[str, Any]], db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Store newly discovered listings and queue AGENT_ALLOWED items for delivery.

    Returns the list of newly inserted listings.
    """
    now = utcnow()
    new_items: List[Dict[str, Any]] = []

    with get_connection(db_path) as conn:
        for item in listings:
            lid = item.get("id")
            if not validate_listing_id(lid):
                continue
            lid = str(lid).strip()

            slug = item.get("slug")
            if slug and not validate_slug(slug):
                continue

            existing = conn.execute(
                "SELECT id, delivery_state FROM listings WHERE id = ?", (lid,)
            ).fetchone()

            if existing is None:
                is_agent = item.get("agent_access") == "AGENT_ALLOWED"
                initial_state = STATE_PENDING if is_agent else STATE_DISCOVERED
                
                url = item.get("url")
                if not url and slug:
                    url = f"https://earn.superteam.fun/listing/{slug}"

                conn.execute(
                    """INSERT INTO listings (
                        id, source, title, reward, deadline, agent_access, url,
                        seen_at, delivery_state, delivery_attempts, next_retry_at,
                        delivered_at, last_error, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL, ?)""",
                    (
                        lid,
                        item.get("source", "superteam-earn"),
                        item.get("title"),
                        item.get("reward"),
                        item.get("deadline"),
                        item.get("agent_access"),
                        url,
                        now,
                        initial_state,
                        now,
                    ),
                )
                new_items.append(item)

    return new_items


def record_opportunity(opp: Dict[str, Any], enriched: bool, db_path: Optional[str] = None) -> None:
    """Record an Opportunity Contract object in opportunities table."""
    now = utcnow()
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO opportunities (id, object_json, enriched, created_at)
               VALUES (?, ?, ?, ?)""",
            (opp["id"], json.dumps(opp, ensure_ascii=False), int(enriched), now),
        )


def recover_stale_delivering(timeout_seconds: int = 300, db_path: Optional[str] = None) -> int:
    """Reset delivering records that crashed or timed out back to pending/retry_wait."""
    now_dt = datetime.now(timezone.utc)
    cutoff = (now_dt - timedelta(seconds=timeout_seconds)).isoformat()
    now_iso = now_dt.isoformat()

    with get_connection(db_path) as conn:
        cur = conn.execute(
            """UPDATE listings
               SET delivery_state = CASE
                   WHEN delivery_attempts >= 5 THEN 'permanently_failed'
                   ELSE 'retry_wait'
               END,
               next_retry_at = ?,
               last_error = 'Worker timeout/crash recovered',
               updated_at = ?
               WHERE delivery_state = 'delivering'
                 AND (updated_at IS NULL OR updated_at < ?)""",
            (now_iso, now_iso, cutoff),
        )
        return cur.rowcount


def get_pending_deliveries(limit: Optional[int] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all listings ready for notification delivery (pending or retry_wait due)."""
    now = utcnow()
    query = """
        SELECT id, source, title, reward, deadline, agent_access, url,
               delivery_state, delivery_attempts, next_retry_at, last_error
        FROM listings
        WHERE agent_access = 'AGENT_ALLOWED'
          AND (
              delivery_state = 'pending'
              OR (delivery_state = 'retry_wait' AND (next_retry_at IS NULL OR next_retry_at <= ?))
          )
        ORDER BY seen_at ASC, id ASC
    """
    params: List[Any] = [now]
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]


def claim_delivery(listing_id: str, db_path: Optional[str] = None) -> bool:
    """Atomically claim a listing for delivery attempt.

    Returns True if successfully claimed, False if already claimed or not in claimable state.
    """
    now = utcnow()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """UPDATE listings
               SET delivery_state = 'delivering',
                   delivery_attempts = delivery_attempts + 1,
                   updated_at = ?
               WHERE id = ?
                 AND delivery_state IN ('pending', 'retry_wait')""",
            (now, listing_id),
        )
        return cur.rowcount == 1


def mark_delivered(listing_id: str, timestamp: Optional[str] = None, db_path: Optional[str] = None) -> None:
    """Mark a listing as successfully delivered."""
    now = timestamp or utcnow()
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE listings
               SET delivery_state = 'delivered',
                   delivered_at = ?,
                   last_error = NULL,
                   updated_at = ?
               WHERE id = ?""",
            (now, now, listing_id),
        )


def mark_transient_failure(
    listing_id: str,
    error_msg: str,
    max_attempts: int = 5,
    base_backoff_sec: int = 30,
    max_backoff_sec: int = 3600,
    db_path: Optional[str] = None,
) -> str:
    """Record a transient failure and schedule next retry with bounded exponential backoff.

    Returns the new state: 'retry_wait' or 'permanently_failed'.
    """
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    clean_error = sanitize_error(error_msg)

    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT delivery_attempts FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()

        attempts = row["delivery_attempts"] if row else 1

        if attempts >= max_attempts:
            conn.execute(
                """UPDATE listings
                   SET delivery_state = 'permanently_failed',
                       last_error = ?,
                       updated_at = ?
                   WHERE id = ?""",
                (f"Exceeded max attempts ({max_attempts}): {clean_error}", now_iso, listing_id),
            )
            return STATE_PERMANENTLY_FAILED

        # Bounded exponential backoff: base * 2^(attempts-1)
        delay_sec = min(max_backoff_sec, base_backoff_sec * (2 ** (attempts - 1)))
        next_retry = (now_dt + timedelta(seconds=delay_sec)).isoformat()

        conn.execute(
            """UPDATE listings
               SET delivery_state = 'retry_wait',
                   next_retry_at = ?,
                   last_error = ?,
                   updated_at = ?
               WHERE id = ?""",
            (next_retry, clean_error, now_iso, listing_id),
        )
        return STATE_RETRY_WAIT


def mark_permanent_failure(listing_id: str, error_msg: str, db_path: Optional[str] = None) -> None:
    """Mark a listing as permanently failed (fatal HTTP 4xx, bad auth, etc.)."""
    now = utcnow()
    clean_error = sanitize_error(error_msg)
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE listings
               SET delivery_state = 'permanently_failed',
                   last_error = ?,
                   updated_at = ?
               WHERE id = ?""",
            (clean_error, now, listing_id),
        )
