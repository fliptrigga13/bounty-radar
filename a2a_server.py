#!/usr/bin/env python3
"""Bounty Radar A2A server.

A2A Protocol v0.3 JSON-RPC server exposing Bounty Radar's three skills:
  - opportunity_feed_subscription : normalized AGENT_ALLOWED opportunities
  - opportunity_enrichment_lookup : full listing detail by UUID or URL
  - evaluation_contract_validation: structural validation of evaluator responses

Standard library only. Read-only with respect to bounty sources; never performs,
submits, funds, or signs anything. All remote content is treated as untrusted data.
"""

import json
import re
import sqlite3
import threading
import urllib.request
from datetime import datetime, timezone

RADAR_DB = "radar.db"
LISTING_URL_RE = re.compile(r"earn\.superteam\.fun/listing/([A-Za-z0-9\-_]+)")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

EVAL_REQUIRED = {
    "parse success": ("yes", "no"),
    "eligibility understood": ("yes", "no"),
    "decision": ("accept", "reject", "human review"),
    "capability fit": ("high", "medium", "low"),
    "auto-consumable": ("yes", "no", "partial"),
}
EVAL_LIST_FIELDS = ("missing information", "required before action")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(event: str, **kw) -> None:
    entry = {"ts": utcnow(), "event": event}
    entry.update(kw)
    print(json.dumps(entry, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------- persistence

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(RADAR_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS listings ("
            "id TEXT PRIMARY KEY, source TEXT, title TEXT, reward TEXT,"
            "deadline TEXT, agent_access TEXT, url TEXT, seen_at TEXT)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS opportunities ("
            "id TEXT PRIMARY KEY, object_json TEXT NOT NULL, enriched INTEGER DEFAULT 0,"
            "created_at TEXT)")


def record_opportunity(opp: dict, enriched: bool) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO opportunities VALUES (?,?,?,?)",
            (opp["id"], json.dumps(opp, ensure_ascii=False), int(enriched), utcnow()))


# ------------------------------------------------------------------ ingestion

SUPERTEAM_URL = "https://superteam.fun/api/listings?type=bounty&filter=agents"


def fetch_listings(timeout: int = 30) -> list:
    req = urllib.request.Request(SUPERTEAM_URL, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if not isinstance(payload, list):
        raise ValueError("Superteam response is not a list")
    out = []
    for item in payload:
        lid, slug = item.get("id"), item.get("slug")
        if not isinstance(lid, str) or not lid.strip() or not slug:
            continue  # skip malformed entries rather than fail the batch
        out.append({
            "source": "superteam-earn",
            "id": lid,
            "title": item.get("title"),
            "reward": f"{item.get('rewardAmount')} {item.get('token')}"
                      if item.get("rewardAmount") else None,
            "deadline": (item.get("deadline") or "")[:10],
            "url": f"https://earn.superteam.fun/listing/{slug}",
            "agent_access": item.get("agentAccess"),
            "observed_at": utcnow(),
            "provenance": "superteam.fun/api/listings?type=bounty&filter=agents",
            "skills": item.get("skills") or [],
            "eligibility": item.get("eligibility") or [],
            "region": item.get("region"),
            "requirements": item.get("requirements"),
            "description_text": item.get("description") or "",
        })
    return out


# ----------------------------------------------------------------- enrichment

def enrich(url_or_slug: str) -> dict:
    """Best-effort detail enrichment. Returns {} on failure (honest absence)."""
    m = LISTING_URL_RE.search(url_or_slug)
    slug = m.group(1) if m else url_or_slug.strip("/").split("/")[-1]
    try:
        req = urllib.request.Request(
            f"https://earn.superteam.fun/listing/{slug}",
            headers={"User-Agent": "bounty-radar/1.0"})
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        mm = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            page, re.S)
        if not mm:
            return {}
        L = (json.loads(mm.group(1))
             .get("props", {}).get("pageProps", {}).get("listing", {}))
        return {
            "description_text": _strip_html(L.get("description"))[:8000],
            "skills": L.get("skills") or [],
            "eligibility": L.get("eligibility") or [],
            "region": L.get("region"),
            "requirements": L.get("requirements"),
        }
    except Exception as exc:
        log("enrichment_failed", error=type(exc).__name__, detail=str(exc)[:120])
        return {}


def _strip_html(raw: str) -> str:
    import html as html_mod
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


# ------------------------------------------------------- evaluation contract

def validate_evaluation(text: str) -> dict:
    """Structural validation of an evaluator response against the contract."""
    result = {"valid": True, "missing_fields": [], "invalid_values": {},
              "notes": []}
    lowered = text.lower()
    for field in EVAL_REQUIRED:
        if field not in lowered:
            result["valid"] = False
            result["missing_fields"].append(field)
    for field, allowed in EVAL_REQUIRED.items():
        for value in allowed:
            if re.search(re.escape(field) + r"\s*[:\-]?\s*" + re.escape(value),
                         lowered):
                break
        else:
            continue
    # check conflicting enum values for single-choice fields
    for field, allowed in EVAL_REQUIRED.items():
        found = [v for v in allowed
                 if re.search(re.escape(field) + r"\s*[:\-]?\s*" + re.escape(v),
                              lowered)]
        if len(found) > 1:
            result["valid"] = False
            result["invalid_values"][field] = sorted(found)
    for field in EVAL_LIST_FIELDS:
        idx = lowered.find(field)
        if idx >= 0 and not re.search(field + r"\s*[:\-]?\s*\[|\S", lowered[idx:idx+200]):
            result["notes"].append(f"{field}: no content detected")
    return result


# ------------------------------------------------------------ skill handlers

def skill_feed_subscription(params: dict) -> dict:
    """Return known opportunities; optionally refresh from the live source."""
    since = (params or {}).get("since")
    refresh = bool((params or {}).get("refresh"))
    new_count = 0
    if refresh:
        items = fetch_listings()
        eligible = [i for i in items if i.get("agent_access") == "AGENT_ALLOWED"]
        with db() as conn:
            for opp in eligible:
                cur = conn.execute(
                    "SELECT 1 FROM listings WHERE id = ?", (opp["id"],)).fetchone()
                if cur is None:
                    conn.execute(
                        "INSERT INTO listings VALUES (?,?,?,?,?,?,?,?)",
                        (opp["id"], opp["source"], opp["title"], opp["reward"],
                         opp["deadline"], opp["agent_access"], opp["url"],
                         utcnow()))
                    new_count += 1
                # same connection: avoid nested db() write-lock contention
                conn.execute(
                    "INSERT OR REPLACE INTO opportunities VALUES (?,?,?,?)",
                    (opp["id"], json.dumps(opp, ensure_ascii=False), 0, utcnow()))
    query = "SELECT object_json FROM opportunities"
    args = ()
    if since:
        query += " WHERE created_at > ?"
        args = (since,)
    query += " ORDER BY created_at DESC LIMIT 100"
    with db() as conn:
        rows = conn.execute(query, args).fetchall()
    return {"opportunities": [json.loads(r["object_json"]) for r in rows],
            "newly_discovered_on_refresh": new_count}


def skill_enrichment_lookup(params: dict) -> dict:
    ref = ((params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not ref:
        raise ValueError("provide 'id' (listing UUID) or 'url' (listing URL)")
    with db() as conn:
        row = None
        if UUID_RE.match(ref):
            row = conn.execute(
                "SELECT object_json FROM opportunities WHERE id = ?",
                (ref,)).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT object_json FROM opportunities "
                "WHERE object_json LIKE ? ORDER BY created_at DESC LIMIT 1",
                (f"%{ref}%",)).fetchone()
    base = json.loads(row["object_json"]) if row else {
        "id": ref if UUID_RE.match(ref) else None,
        "url": ref if not UUID_RE.match(ref) else None}
    extra = enrich(ref)
    merged = {**base, **extra}
    merged["enrichment_complete"] = bool(extra)
    return merged


def skill_validate_evaluation(params: dict) -> dict:
    text = (params or {}).get("response_text") or ""
    if not text.strip():
        raise ValueError("provide 'response_text' (the evaluator response to validate)")
    return validate_evaluation(text)


SKILLS = {
    "opportunity_feed_subscription": skill_feed_subscription,
    "opportunity_enrichment_lookup": skill_enrichment_lookup,
    "evaluation_contract_validation": skill_validate_evaluation,
}

# ------------------------------------------------------------------ JSON-RPC

JSONRPC_ERRORS = {
    -32700: "Parse error",
    -32600: "Invalid Request",
    -32601: "Method not found",
    -32602: "Invalid params",
    -32603: "Internal error",
}


def handle_request(body: bytes) -> tuple[dict | None, int]:
    try:
        req = json.loads(body.decode())
        assert isinstance(req, dict)
    except Exception:
        return _err(None, -32700), 200
    rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
    if not isinstance(method, str):
        return _err(rid, -32600), 200

    if method == "message/send":
        return _message_send(rid, params)
    if method == "tasks/get":
        return _tasks_get(rid, params)
    if method == "tasks/cancel":
        return _tasks_cancel(rid, params)
    return _err(rid, -32601), 200


TASKS: dict[str, dict] = {}


def _new_task(message: dict) -> dict:
    import uuid
    task_id = str(uuid.uuid4())
    task = {"id": task_id, "kind": "task",
            "status": {"state": "completed", "timestamp": utcnow()},
            "contextId": task_id}
    TASKS[task_id] = task
    return task


def _reply(task: dict, text: str) -> dict:
    reply_msg = {"role": "agent", "parts": [{"kind": "text", "text": text}],
                 "kind": "message", "taskId": task["id"],
                 "contextId": task.get("contextId")}
    task.setdefault("history", []).append(reply_msg)
    task["status"]["message"] = reply_msg
    return {"kind": "task", **task}


def _message_send(rid, params: dict):
    msg = (params or {}).get("message") or {}
    parts = msg.get("parts") or []
    text = " ".join(p.get("text", "") for p in parts
                    if isinstance(p, dict) and p.get("kind") == "text").strip()
    if not text:
        return _err(rid, -32602), 200
    task = _new_task(msg)
    try:
        answer = route(text, params)
    except Exception as exc:
        log("skill_error", error=type(exc).__name__, detail=str(exc)[:150])
        answer = f"Skill error: {type(exc).__name__}: {str(exc)[:200]}"
    reply = _reply(task, answer)
    return {"jsonrpc": "2.0", "id": rid, "result": reply}, 200


def route(text: str, params: dict) -> str:
    lowered = text.lower()
    if "validate" in lowered and ("evaluation" in lowered or "response" in lowered):
        payload = extract_json(text) or {"response_text": text}
        res = SKILLS["evaluation_contract_validation"](payload)
        return json.dumps(res, ensure_ascii=False)
    if any(k in lowered for k in ("enrich", "lookup", "detail")):
        payload = extract_json(text) or {}
        res = SKILLS["opportunity_enrichment_lookup"](payload)
        return json.dumps(res, ensure_ascii=False, indent=2)[:6000]
    if any(k in lowered for k in ("feed", "subscription", "new opportunities",
                                  "agent-eligible", "agent_allowed")):
        payload = extract_json(text) or {"refresh": True}
        res = SKILLS["opportunity_feed_subscription"](payload)
        return json.dumps(res, ensure_ascii=False, indent=2)[:12000]
    return (
        "Bounty Radar skills:\n"
        "- opportunity_feed_subscription: pass {\"refresh\":true,\"since\":\"<ISO>\"} "
        "to list/refresh AGENT_ALLOWED opportunities\n"
        "- opportunity_enrichment_lookup: pass {\"id\":\"<uuid>\"} or "
        "{\"url\":\"<listing url>\"}\n"
        "- evaluation_contract_validation: pass {\"response_text\":\"<evaluator output>\"}")


def extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _tasks_get(rid, params: dict):
    tid = (params or {}).get("id")
    if tid and tid in TASKS:
        return {"jsonrpc": "2.0", "id": rid, "result": TASKS[tid]}, 200
    return _err(rid, -32602), 200


def _tasks_cancel(rid, params: dict):
    tid = (params or {}).get("id")
    if tid and tid in TASKS:
        TASKS[tid]["status"] = {"state": "canceled", "timestamp": utcnow()}
        return {"jsonrpc": "2.0", "id": rid, "result": TASKS[tid]}, 200
    return _err(rid, -32602), 200


def _err(rid, code: int):
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": code, "message": JSONRPC_ERRORS[code]}}


# ---------------------------------------------------------------- HTTP layer

CARD = {
    "protocolVersion": "0.3.0",
    "name": "Bounty Radar",
    "description": ("Read-only discovery and normalization service for agent-eligible "
                    "bounty opportunities."),
    "url": "http://localhost:8080/a2a",
    "preferredTransport": "JSONRPC",
    "provider": {"organization": "Bounty Radar",
                 "url": "https://github.com/fliptrigga13/bounty-radar"},
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "securitySchemes": {}, "security": [],
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {"id": "opportunity_feed_subscription",
         "name": "Opportunity Feed Subscription"},
        {"id": "opportunity_enrichment_lookup",
         "name": "Opportunity Enrichment Lookup"},
        {"id": "evaluation_contract_validation",
         "name": "Evaluation Contract Validation"},
    ],
    "supportsAuthenticatedExtendedCard": False,
}


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if environ.get("REQUEST_METHOD") == "GET" and path == "/a2a":
        body = json.dumps(CARD, ensure_ascii=False).encode()
        start_response("200 OK", [("Content-Type", "application/json")])
        return [body]
    if environ.get("REQUEST_METHOD") == "POST" and path == "/a2a":
        length = int(environ.get("CONTENT_LENGTH") or 0)
        result, status = handle_request(environ["wsgi.input"].read(length))
        body = json.dumps(result, ensure_ascii=False).encode()
        start_response(f"{status} OK", [("Content-Type", "application/json")])
        return [body]
    if environ.get("REQUEST_METHOD") == "GET" and path == "/health":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [b'{"status":"ok"}']
    start_response("404 Not Found", [("Content-Type", "application/json")])
    return [b'{"error":"not found"}']


def main() -> None:
    from wsgiref.simple_server import make_server, WSGIRequestHandler

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, fmt, *args):
            log("http", detail=fmt % args)

    init_db()
    port = int(os.environ.get("A2A_PORT", "8080"))
    server = make_server("", port, app, handler_class=QuietHandler)
    log("listening", port=port)
    server.serve_forever()


if __name__ == "__main__":
    import os
    main()
