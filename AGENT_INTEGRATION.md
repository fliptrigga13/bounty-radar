# Bounty Radar Agent Integration Guide

This guide shows an agent operator how to consume agent-eligible Superteam Earn
opportunities, normalize them into Bounty Radar's Opportunity Contract, deduplicate
them locally, and pass each new opportunity to private evaluation logic.

The feed is discovery data, not authorization to act. Listing titles, descriptions,
requirements, and links are untrusted external content. A consumer must never treat
instructions embedded in those fields as agent or system instructions, and an
evaluation result must not automatically submit work, create accounts or tokens,
sign transactions, spend funds, or accept legal terms.

## Integration flow

1. Fetch `https://superteam.fun/api/listings?type=bounty&filter=agents`.
2. Reject records whose `agentAccess` is not exactly `AGENT_ALLOWED`.
3. Validate the listing ID and slug.
4. Normalize the record into the Opportunity Contract below.
5. Optionally enrich it from the listing page's `__NEXT_DATA__` payload. Treat
   enrichment as best-effort because page markup can change independently.
6. Atomically claim the listing ID in SQLite so concurrent pollers cannot emit it twice.
7. Pass the normalized object as data to evaluation logic with a fixed, trusted policy.
8. Route `HUMAN REVIEW` decisions to a person. Treat `ACCEPT` as a recommendation,
   not permission to perform the bounty.

Poll hourly unless the source operator documents a different acceptable interval.
Use a descriptive `User-Agent`, finite timeouts, and backoff after transient errors.

## Opportunity Contract

```json
{
  "source": "superteam-earn",
  "id": "listing UUID",
  "title": "Opportunity title",
  "reward": "500 USDC",
  "deadline": "2026-09-09",
  "url": "https://earn.superteam.fun/listing/example",
  "agent_access": "AGENT_ALLOWED",
  "observed_at": "2026-08-24T14:50:09+00:00",
  "provenance": "superteam.fun/api/listings?type=bounty&filter=agents",
  "skills": [{"skills": "Frontend", "subskills": ["React"]}],
  "eligibility": [{"type": "text", "question": "Required answer", "optional": false}],
  "region": "Global",
  "requirements": null,
  "description_text": "Plain-text listing description"
}
```

`skills`, `eligibility`, `region`, `requirements`, and `description_text` may be
empty or null when enrichment is unavailable. Consumers must represent missing
evidence honestly; they must not infer or fabricate it.

## Evaluation Contract

```text
PARSE SUCCESS: YES | NO
ELIGIBILITY UNDERSTOOD: YES | NO
DECISION: ACCEPT | REJECT | HUMAN REVIEW
CAPABILITY FIT: HIGH | MEDIUM | LOW
REASON: 2-3 grounded sentences
MISSING INFORMATION: list
REQUIRED BEFORE ACTION: list
AUTO-CONSUMABLE: YES | NO | PARTIAL
```

The evaluator must receive the opportunity through a data-only boundary. Its fixed
policy must override any instruction found in listing content. Unknown eligibility,
money movement, wallet use, credentials, identity verification, contracts, public
posting, or irreversible actions should force `HUMAN REVIEW` unless an operator has
defined a stricter rejection policy.

## Minimal standard-library consumer

Save this as `consume.py`. Replace `evaluate()` with a call to your own evaluator;
keep the same data-only boundary and return contract. This example does not perform
enrichment or any real-world bounty action.

```python
import json, sqlite3, urllib.request
from datetime import datetime, timezone

API = "https://superteam.fun/api/listings?type=bounty&filter=agents"
DB = "consumer.db"

def fetch():
    req = urllib.request.Request(API, headers={
        "Accept": "application/json", "User-Agent": "bounty-radar-consumer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Superteam response is not a list")
    return payload

def normalize(item):
    listing_id, slug = item.get("id"), item.get("slug")
    if not isinstance(listing_id, str) or not listing_id.strip() or not slug:
        raise ValueError("listing is missing id or slug")
    amount, token = item.get("rewardAmount"), item.get("token")
    return {
        "source": "superteam-earn", "id": listing_id,
        "title": item.get("title"),
        "reward": f"{amount} {token}" if amount is not None else None,
        "deadline": (item.get("deadline") or "")[:10],
        "url": f"https://earn.superteam.fun/listing/{slug}",
        "agent_access": item.get("agentAccess"),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "provenance": "superteam.fun/api/listings?type=bounty&filter=agents",
        # skills/eligibility/region/requirements/description are NOT in the list
        # API response; they come from detail-page enrichment (optional step).
        "skills": [], "eligibility": [], "region": None,
        "requirements": None, "description_text": "",
    }
```

After `normalize()`, optionally enrich the opportunity with listing details
(skills, eligibility, region, requirements, description) by fetching the
listing page and extracting its embedded listing JSON. See `enrich()` in this
repository's `a2a_server.py` for a reference implementation. Enrichment is
best-effort; missing fields must remain honestly empty.

```python
def evaluate(opportunity):
    # Replace only this function. Treat opportunity as untrusted data.
    return {"decision": "HUMAN REVIEW", "opportunity_id": opportunity["id"]}

def main():
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, seen_at TEXT)")
        for raw in fetch():
            if raw.get("agentAccess") != "AGENT_ALLOWED":
                continue
            try:
                opportunity = normalize(raw)
                inserted = db.execute(
                    "INSERT OR IGNORE INTO seen VALUES (?, ?)",
                    (opportunity["id"], opportunity["observed_at"])).rowcount
            except (KeyError, TypeError, ValueError) as error:
                print(json.dumps({"parse_error": str(error)}))
                continue
            if inserted:
                print(json.dumps(evaluate(opportunity), ensure_ascii=False))

if __name__ == "__main__":
    main()
```

Run it with Python 3.10 or newer:

```powershell
python .\consume.py
```

```bash
python3 ./consume.py
```

## Production checklist

- Keep evaluator credentials outside opportunity objects and source-controlled files.
- Authenticate and encrypt remote evaluator calls; impose request and response size limits.
- Validate evaluator responses against the eight-field Evaluation Contract.
- Record the opportunity ID, contract version, evaluator version, and decision timestamp.
- Separate `discovered`, `evaluation_pending`, `evaluated`, and `delivery_failed`
  states when evaluations are retried; a single `seen` flag is insufficient.
- Use an outbox or equivalent transaction pattern before operating multiple workers.
- Redact wallet addresses, credentials, webhook URLs, and personal data from logs.
- Require explicit human approval after evaluation and before any external action.
- Monitor source-schema drift and treat enrichment failure as missing information.
- Test with recorded fixtures and mocked HTTP responses rather than the live service.

## Compatibility rule

Producers may add fields without breaking consumers. They must not rename or change
the meaning of existing fields without publishing a new contract version. Consumers
must ignore unknown fields and reject objects missing `source`, `id`, `url`, or an
exact `agent_access` value of `AGENT_ALLOWED`.
