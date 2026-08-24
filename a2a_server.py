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
import os
import re
import signal
import sys
import threading
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import db
import enrich


def _load_env() -> None:
    """Load key-value pairs from .env.local or .env if present in current directory."""
    for filename in (".env.local", ".env"):
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("\"'")
                        if k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


_load_env()

MAX_REQUEST_SIZE = 1024 * 1024  # 1 MB

EVAL_REQUIRED = {
    "parse success": ("yes", "no"),
    "eligibility understood": ("yes", "no"),
    "decision": ("accept", "reject", "human review"),
    "capability fit": ("high", "medium", "low"),
    "auto-consumable": ("yes", "no", "partial"),
}
EVAL_LIST_FIELDS = ("missing information", "required before action")

TASKS: Dict[str, Dict[str, Any]] = {}
SERVER_INSTANCE = None


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(event: str, **kw) -> None:
    sanitized_kw = {k: db.sanitize_error(v) if isinstance(v, str) else v for k, v in kw.items()}
    entry = {"ts": utcnow(), "event": event}
    entry.update(sanitized_kw)
    print(json.dumps(entry, ensure_ascii=False), flush=True)


# ------------------------------------------------------------------ Ingestion


def fetch_listings(timeout: int = 30) -> list:
    """Fetch and normalize listings from Superteam Earn API."""
    import radar
    return radar.fetch_superteam(timeout=timeout)


# ------------------------------------------------------- Evaluation Contract


def validate_evaluation(text: str) -> dict:
    """Structural validation of an evaluator response against the 8-field Evaluation Contract."""
    result = {"valid": True, "missing_fields": [], "invalid_values": {}, "notes": []}
    lowered = text.lower()

    # Check presence of required single-value enum fields
    for field in EVAL_REQUIRED:
        if field not in lowered:
            result["valid"] = False
            result["missing_fields"].append(field)

    # Check presence of 'reason' field
    if "reason" not in lowered:
        result["valid"] = False
        result["missing_fields"].append("reason")

    # Check valid values
    for field, allowed in EVAL_REQUIRED.items():
        for value in allowed:
            if re.search(re.escape(field) + r"\s*[:\-]?\s*" + re.escape(value), lowered):
                break
        else:
            if field in lowered:
                result["valid"] = False
                result["invalid_values"][field] = "unrecognized value"

    # Check conflicting enum values for single-choice fields
    for field, allowed in EVAL_REQUIRED.items():
        found = [
            v
            for v in allowed
            if re.search(re.escape(field) + r"\s*[:\-]?\s*" + re.escape(v), lowered)
        ]
        if len(found) > 1:
            result["valid"] = False
            result["invalid_values"][field] = sorted(found)

    for field in EVAL_LIST_FIELDS:
        idx = lowered.find(field)
        if idx < 0:
            result["notes"].append(f"{field}: missing header")
        elif not re.search(field + r"\s*[:\-]?\s*(\[|\S)", lowered[idx : idx + 200]):
            result["notes"].append(f"{field}: no content detected")

    return result


# ------------------------------------------------------------ Skill Handlers


def skill_feed_subscription(params: dict) -> dict:
    """Return known opportunities; optionally refresh from the live source."""
    since = (params or {}).get("since")
    refresh = bool((params or {}).get("refresh"))
    new_count = 0

    if refresh:
        items = fetch_listings()
        eligible = [i for i in items if i.get("agent_access") == "AGENT_ALLOWED"]
        new_stored = db.store_listings(items)
        new_count = len([i for i in new_stored if i.get("agent_access") == "AGENT_ALLOWED"])

        for opp in eligible:
            contract_opp = {
                "source": "superteam-earn",
                "id": opp["id"],
                "title": opp.get("title"),
                "reward": opp.get("reward"),
                "deadline": opp.get("deadline"),
                "url": opp.get("url"),
                "agent_access": opp.get("agent_access"),
                "observed_at": utcnow(),
                "provenance": "superteam.fun/api/listings?type=bounty&filter=agents",
                "skills": opp.get("skills") or [],
                "eligibility": opp.get("eligibility") or [],
                "region": opp.get("region"),
                "requirements": opp.get("requirements"),
                "description_text": opp.get("description_text") or "",
            }
            db.record_opportunity(contract_opp, enriched=False)

    query = "SELECT object_json FROM opportunities"
    args: Tuple[Any, ...] = ()
    if since:
        query += " WHERE created_at > ?"
        args = (since,)
    query += " ORDER BY created_at DESC LIMIT 100"

    with db.get_connection() as conn:
        rows = conn.execute(query, args).fetchall()

    return {
        "opportunities": [json.loads(r["object_json"]) for r in rows],
        "newly_discovered_on_refresh": new_count,
    }


def skill_enrichment_lookup(params: dict) -> dict:
    """Look up an opportunity by UUID or URL and enrich with listing details."""
    ref = ((params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not ref:
        raise ValueError("provide 'id' (listing UUID) or 'url' (listing URL)")

    with db.get_connection() as conn:
        row = None
        if db.UUID_RE.match(ref):
            row = conn.execute(
                "SELECT object_json FROM opportunities WHERE id = ?", (ref,)
            ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT object_json FROM opportunities WHERE object_json LIKE ? ORDER BY created_at DESC LIMIT 1",
                (f"%{ref}%",),
            ).fetchone()

    base = (
        json.loads(row["object_json"])
        if row
        else {
            "source": "superteam-earn",
            "id": ref if db.UUID_RE.match(ref) else None,
            "url": ref if not db.UUID_RE.match(ref) else None,
            "observed_at": utcnow(),
            "provenance": "superteam.fun/api/listings?type=bounty&filter=agents",
            "agent_access": "AGENT_ALLOWED",
            "skills": [],
            "eligibility": [],
            "region": None,
            "requirements": None,
            "description_text": "",
        }
    )

    extra = enrich.enrich_listing(ref)
    merged = {**base, **extra}
    merged["enrichment_complete"] = bool(extra)
    return merged


def skill_validate_evaluation(params: dict) -> dict:
    """Validate evaluator response against the Evaluation Contract."""
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


def _err(rid: Any, code: int, data: Optional[Any] = None) -> dict:
    err_obj: Dict[str, Any] = {"code": code, "message": JSONRPC_ERRORS.get(code, "Error")}
    if data is not None:
        err_obj["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": err_obj}


def handle_request(body: bytes) -> Tuple[dict, int]:
    """Handle JSON-RPC request according to A2A v0.3 protocol."""
    if len(body) > MAX_REQUEST_SIZE:
        return _err(None, -32600, "Payload exceeds size limit"), 200

    try:
        req = json.loads(body.decode("utf-8"))
    except Exception:
        return _err(None, -32700), 200

    if not isinstance(req, dict):
        return _err(None, -32600), 200

    rid = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    if not isinstance(method, str) or req.get("jsonrpc") != "2.0":
        return _err(rid, -32600), 200

    if not isinstance(params, (dict, list)):
        return _err(rid, -32602, "params must be an object or array"), 200

    if isinstance(params, list):
        params_dict = params[0] if params and isinstance(params[0], dict) else {}
    else:
        params_dict = params

    try:
        if method == "message/send":
            return _message_send(rid, params_dict)
        if method == "tasks/get":
            return _tasks_get(rid, params_dict)
        if method == "tasks/cancel":
            return _tasks_cancel(rid, params_dict)
        return _err(rid, -32601), 200
    except Exception as exc:
        log("jsonrpc_internal_error", error=type(exc).__name__, detail=str(exc)[:150])
        return _err(rid, -32603, f"Internal server error: {type(exc).__name__}"), 200


def _new_task(message: dict) -> dict:
    import uuid

    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "kind": "task",
        "status": {"state": "completed", "timestamp": utcnow()},
        "contextId": task_id,
        "history": [],
    }
    TASKS[task_id] = task
    return task


def _reply(task: dict, text: str) -> dict:
    reply_msg = {
        "role": "agent",
        "parts": [{"kind": "text", "text": text}],
        "kind": "message",
        "taskId": task["id"],
        "contextId": task.get("contextId"),
    }
    task.setdefault("history", []).append(reply_msg)
    task["status"]["message"] = reply_msg
    return {"kind": "task", **task}


def _message_send(rid: Any, params: dict) -> Tuple[dict, int]:
    msg = (params or {}).get("message") or {}
    if not isinstance(msg, dict):
        return _err(rid, -32602, "message must be an object"), 200

    parts = msg.get("parts") or []
    if not isinstance(parts, list):
        return _err(rid, -32602, "message.parts must be a list"), 200

    text = " ".join(
        p.get("text", "")
        for p in parts
        if isinstance(p, dict) and p.get("kind") == "text"
    ).strip()

    if not text:
        return _err(rid, -32602, "message text is required in parts"), 200

    task = _new_task(msg)
    try:
        answer = route(text, params)
    except Exception as exc:
        log("skill_error", error=type(exc).__name__, detail=str(exc)[:150])
        answer = f"Skill error: {type(exc).__name__}: {str(exc)[:200]}"

    reply = _reply(task, answer)
    return {"jsonrpc": "2.0", "id": rid, "result": reply}, 200


def route(text: str, params: dict) -> str:
    """Route natural language or structured requests to skill handlers."""
    lowered = text.lower()
    if "validate" in lowered and ("evaluation" in lowered or "response" in lowered):
        payload = extract_json(text) or {"response_text": text}
        res = SKILLS["evaluation_contract_validation"](payload)
        return json.dumps(res, ensure_ascii=False)
    if any(k in lowered for k in ("enrich", "lookup", "detail")):
        payload = extract_json(text) or {}
        res = SKILLS["opportunity_enrichment_lookup"](payload)
        return json.dumps(res, ensure_ascii=False, indent=2)[:6000]
    if any(
        k in lowered
        for k in ("feed", "subscription", "new opportunities", "agent-eligible", "agent_allowed")
    ):
        payload = extract_json(text) or {"refresh": True}
        res = SKILLS["opportunity_feed_subscription"](payload)
        return json.dumps(res, ensure_ascii=False, indent=2)[:12000]

    return (
        "Bounty Radar skills:\n"
        '- opportunity_feed_subscription: pass {"refresh":true,"since":"<ISO>"} to list/refresh AGENT_ALLOWED opportunities\n'
        '- opportunity_enrichment_lookup: pass {"id":"<uuid>"} or {"url":"<listing url>"}\n'
        '- evaluation_contract_validation: pass {"response_text":"<evaluator output>"}'
    )


def extract_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _tasks_get(rid: Any, params: dict) -> Tuple[dict, int]:
    tid = (params or {}).get("id") or (params or {}).get("taskId")
    if tid and isinstance(tid, str) and tid in TASKS:
        return {"jsonrpc": "2.0", "id": rid, "result": TASKS[tid]}, 200
    return _err(rid, -32602, f"Task not found: {tid}"), 200


def _tasks_cancel(rid: Any, params: dict) -> Tuple[dict, int]:
    tid = (params or {}).get("id") or (params or {}).get("taskId")
    if tid and isinstance(tid, str) and tid in TASKS:
        TASKS[tid]["status"] = {"state": "canceled", "timestamp": utcnow()}
        return {"jsonrpc": "2.0", "id": rid, "result": TASKS[tid]}, 200
    return _err(rid, -32602, f"Task not found: {tid}"), 200


# ---------------------------------------------------------------- HTTP Layer


def get_agent_card() -> dict:
    """Generate dynamic A2A v0.3 Agent Card."""
    card_path = os.path.join(os.path.dirname(__file__), ".well-known", "agent-card.json")
    if os.path.exists(card_path):
        try:
            with open(card_path, "r", encoding="utf-8") as f:
                card = json.load(f)
        except Exception:
            card = {}
    else:
        card = {}

    port = int(os.environ.get("A2A_PORT", "8080"))
    public_url = (
        os.environ.get("A2A_PUBLIC_URL")
        or os.environ.get("PUBLIC_URL")
        or f"http://localhost:{port}/a2a"
    )

    card["protocolVersion"] = "0.3.0"
    card["name"] = "Bounty Radar"
    card["description"] = (
        "Read-only discovery and normalization service for agent-eligible bounty opportunities. "
        "It provides structured opportunity data and validates consumer evaluation responses; "
        "it does not perform, submit, fund, sign, or accept bounties."
    )
    card["url"] = public_url
    card["preferredTransport"] = "JSONRPC"
    card["provider"] = {
        "organization": "Bounty Radar",
        "url": "https://github.com/fliptrigga13/bounty-radar",
    }
    card["version"] = "1.0.0"
    card["capabilities"] = {"streaming": False, "pushNotifications": False}
    card["skills"] = [
        {
            "id": "opportunity_feed_subscription",
            "name": "Opportunity Feed Subscription",
            "description": "Creates or inspects a pull-based feed subscription for newly observed Superteam Earn listings whose agentAccess value is exactly AGENT_ALLOWED.",
            "tags": ["bounties", "opportunities", "feed", "subscription", "superteam", "read-only"],
        },
        {
            "id": "opportunity_enrichment_lookup",
            "name": "Opportunity Enrichment Lookup",
            "description": "Looks up a known Superteam Earn listing by its listing UUID or canonical listing URL and returns the normalized Opportunity Contract.",
            "tags": ["bounties", "enrichment", "lookup", "normalization", "provenance", "read-only"],
        },
        {
            "id": "evaluation_contract_validation",
            "name": "Evaluation Contract Validation",
            "description": "Validates whether an independent evaluator response contains the required 8 fields with allowed enum values.",
            "tags": ["evaluation", "validation", "contract", "safety", "interoperability", "read-only"],
        },
    ]
    return card


def app(environ: dict, start_response: Any):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if method == "GET" and path == "/":
        welcome = {
            "service": "Bounty Radar A2A Server",
            "version": "1.0.0",
            "status": "online",
            "endpoints": {
                "health": "/health",
                "agent_card": "/a2a",
                "well_known_card": "/.well-known/agent-card.json",
                "jsonrpc_endpoint": "POST /a2a",
            },
            "docs": "https://github.com/fliptrigga13/bounty-radar",
        }
        body = json.dumps(welcome, ensure_ascii=False, indent=2).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json")])
        return [body]

    if method == "GET" and path == "/health":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [b'{"status":"ok"}']

    if method == "GET" and path in ("/.well-known/agent-card.json", "/a2a"):
        body = json.dumps(get_agent_card(), ensure_ascii=False, indent=2).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json")])
        return [body]

    if method == "POST" and path == "/a2a":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0

        if length > MAX_REQUEST_SIZE:
            err_body = json.dumps(_err(None, -32600, "Payload too large"), ensure_ascii=False).encode("utf-8")
            start_response("413 Payload Too Large", [("Content-Type", "application/json")])
            return [err_body]

        raw_input = environ["wsgi.input"].read(length) if length > 0 else b""
        result, status = handle_request(raw_input)
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json")])
        return [body]

    start_response("404 Not Found", [("Content-Type", "application/json")])
    return [b'{"error":"not found"}']


def shutdown_server():
    global SERVER_INSTANCE
    if SERVER_INSTANCE:
        log("shutting_down", message="Stopping A2A WSGI server")
        SERVER_INSTANCE.shutdown()


def main() -> None:
    global SERVER_INSTANCE
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, fmt, *args):
            log("http", detail=fmt % args)

    db.init_db()
    port = int(os.environ.get("A2A_PORT", "8080"))
    SERVER_INSTANCE = make_server("", port, app, handler_class=QuietHandler)

    def _sig_handler(signum, frame):
        threading.Thread(target=shutdown_server).start()

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    log("listening", port=port)
    try:
        SERVER_INSTANCE.serve_forever()
    except Exception as e:
        log("server_stopped", error=type(e).__name__)


if __name__ == "__main__":
    main()
