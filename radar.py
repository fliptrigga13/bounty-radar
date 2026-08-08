import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone

SOURCES = {
    "superteam-earn": "https://earn.superteam.fun/api/listings?type=bounty&filter=agents",
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ.get("RADAR_DB", "radar.db"))
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    with _conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS listings ("
            "id TEXT PRIMARY KEY, source TEXT, title TEXT, reward TEXT, "
            "deadline TEXT, agent_access TEXT, url TEXT, seen_at TEXT)"
        )


def fetch_superteam() -> list[dict]:
    import urllib.request

    req = urllib.request.Request(
        SOURCES["superteam-earn"],
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    out = []
    for j in data:
        out.append(
            {
                "id": j.get("id"),
                "source": "superteam-earn",
                "title": j.get("title"),
                "reward": f"{j.get('rewardAmount')} {j.get('token')}" if j.get("rewardAmount") else None,
                "deadline": (j.get("deadline") or "")[:10],
                "agent_access": j.get("agentAccess"),
                "url": f"https://earn.superteam.fun/listing/{j.get('slug')}",
            }
        )
    return out


def store(listings: list[dict]) -> list[dict]:
    new = []
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        for l in listings:
            cur = conn.execute("SELECT 1 FROM listings WHERE id = ?", (l["id"],)).fetchone()
            if cur is None:
                conn.execute(
                    "INSERT INTO listings (id, source, title, reward, deadline, agent_access, url, seen_at) VALUES (?,?,?,?,?,?,?,?)",
                    (l["id"], l["source"], l["title"], l["reward"], l["deadline"], l["agent_access"], l["url"], now),
                )
                new.append(l)
    return new


def telegram_alert(items: list[dict]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    import urllib.request

    for it in items[:10]:
        msg = f"🤑 NEW bounty: {it['title']}\n💰 {it['reward']} | ⏳ {it['deadline']}\n🔗 {it['url']}"
        data = json.dumps({"chat_id": chat, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15)


def main() -> None:
    _init()
    all_items = fetch_superteam()
    truly_agent = [i for i in all_items if i.get("agent_access") == "AGENT_ALLOWED"]
    new = store(all_items)
    agent_new = [i for i in new if i.get("agent_access") == "AGENT_ALLOWED"]
    print(f"{datetime.now(timezone.utc).isoformat()} | total={len(all_items)} agent_allowed={len(truly_agent)} new={len(new)} agent_new={len(agent_new)}")
    for i in new[:5]:
        print(f"  NEW [{i['agent_access']}] {i['title']} | {i['reward']} | {i['deadline']}")
    if agent_new:
        telegram_alert(agent_new)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    main()
    if not args.once:
        while True:
            time.sleep(int(os.environ.get("RADAR_INTERVAL_SEC", "3600")))
            main()
