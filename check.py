#!/usr/bin/env python3
"""Operational readiness and health check for Bounty Radar."""

import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request

import db

RADAR_DB = os.environ.get("RADAR_DB", "radar.db")
A2A_PORT = int(os.environ.get("A2A_PORT", "8080"))


def check_process_running(target: str) -> bool:
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Select-Object -ExpandProperty CommandLine",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return any(target in line for line in out.splitlines() if "check.py" not in line)
        else:
            out = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.DEVNULL)
            return any(target in line for line in out.splitlines() if "check.py" not in line)
    except Exception:
        return False


def check_a2a_health(port: int) -> str:
    url = f"http://127.0.0.1:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bounty-radar-check/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return f"OK (HTTP {resp.status}) - {resp.read().decode('utf-8').strip()}"
    except urllib.error.URLError as e:
        return f"NOT RESPONDING ({e.reason})"
    except Exception as e:
        return f"ERROR ({type(e).__name__}: {e})"


def main() -> None:
    print("=== Bounty Radar Operational Readiness Check ===")

    # 1. Daemon process status
    has_radar = check_process_running("radar.py")
    has_a2a = check_process_running("a2a_server.py")
    if has_radar and has_a2a:
        radar_desc = "YES (both radar.py + a2a_server.py running)"
    elif has_a2a:
        radar_desc = "YES (unified: a2a_server.py with embedded discovery poller)"
    elif has_radar:
        radar_desc = "YES (standalone: radar.py)"
    else:
        radar_desc = "NO (stopped/idle)"
    print(f"1. Discovery Poller:      {radar_desc}")

    # 2. A2A Server HTTP health
    a2a_status = check_a2a_health(A2A_PORT)
    print(f"2. A2A Server Health:     {a2a_status}")

    # 3. Database metrics
    if not os.path.exists(RADAR_DB):
        print(f"3. Database File:         NOT FOUND ({RADAR_DB})")
        return

    print(f"3. Database Path:         {RADAR_DB} (found)")
    try:
        # Ensure schema migrations are applied
        db.init_db(RADAR_DB)
        conn = db.get_connection(RADAR_DB)

        # Last poll / observation timestamp
        row = conn.execute(
            "SELECT MAX(seen_at) as last_seen, MAX(updated_at) as last_updated FROM listings"
        ).fetchone()
        last_poll = (
            (row["last_seen"] or row["last_updated"]) if row else None
        ) or "None (no records yet)"
        print(f"4. Last Ingested Listing: {last_poll}")

        # Counts by delivery state
        cur = conn.execute(
            "SELECT delivery_state, COUNT(*) as cnt FROM listings GROUP BY delivery_state ORDER BY cnt DESC"
        )
        counts = {r["delivery_state"]: r["cnt"] for r in cur.fetchall()}
        total = sum(counts.values())
        print(f"5. Listings Total:        {total}")
        if counts:
            for state, count in counts.items():
                print(f"   - {state}: {count}")
        else:
            print("   - (database is empty, no listings observed yet)")

        # Problematic records (retry_wait or permanently_failed)
        issues = conn.execute(
            "SELECT id, title, delivery_state, delivery_attempts, last_error FROM listings WHERE delivery_state IN ('retry_wait', 'permanently_failed')"
        ).fetchall()
        print(f"6. Delivery Issues:       {len(issues)} item(s)")
        for iss in issues:
            err = db.sanitize_error(iss["last_error"] or "none")[:120]
            print(
                f"   ! [{iss['delivery_state']}] ID: {iss['id']} (Attempts: {iss['delivery_attempts']}) Error: {err}"
            )

        conn.close()
    except Exception as e:
        print(f"   Database Error: {type(e).__name__}: {e}")

    print("================================================")


if __name__ == "__main__":
    main()
