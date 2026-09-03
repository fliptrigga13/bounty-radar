"""Pump.fun GO Bounties Ingestion Module.

Fetches active bounties from Pump.fun GO (https://go.pump.fun),
extracts the Next.js Server-Side Rendered (SSR) hydration state,
and normalizes records into Bounty Radar's standard listing schema.
"""

import logging
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bounty-radar.pumpfun")

# Keywords that indicate a bounty is suitable for AI agents, developers, or digital creators
AGENT_KEYWORDS = [
    "agent",
    "ai",
    "bot",
    "script",
    "automate",
    "automation",
    "code",
    "coder",
    "dev",
    "developer",
    "github",
    "software",
    "api",
    "meme",
    "design",
    "video",
    "content",
    "graphic",
    "website",
    "app",
    "token",
    "chart",
]

PUMPFUN_URL = "https://go.pump.fun"
PUMPFUN_PROGRAM_ID = "goGzNYTYkSEe4hUqz6dPmY5uf3CTt36AQAoujXDrKiV"


def classify_agent_access(title: str, body: str, criteria: Optional[List[str]] = None) -> str:
    """Classify whether a bounty is AGENT_ALLOWED or HUMAN_ONLY based on deliverables."""
    text_parts = [title or "", body or ""]
    if criteria:
        text_parts.extend(criteria)
    corpus = " ".join(text_parts).lower()

    if any(re.search(r"\b" + re.escape(kw) + r"\b", corpus) for kw in AGENT_KEYWORDS):
        return "AGENT_ALLOWED"
    return "HUMAN_ONLY"


def parse_bounties_from_payload(payload_text: str) -> List[Dict[str, Any]]:
    """Parse bounty items from unescaped Next.js hydration payload text."""
    listings: List[Dict[str, Any]] = []
    
    # Locate each bounty block in initialTrendingFeed or general feed
    task_starts = [m.start() for m in re.finditer(r'\{"type":"bounty"', payload_text)]
    if not task_starts:
        # Fallback: search for taskId occurrences directly
        task_starts = [m.start() for m in re.finditer(r'"taskId":"[0-9a-f-]{36}"', payload_text)]

    for i, s_pos in enumerate(task_starts):
        e_pos = task_starts[i + 1] if i + 1 < len(task_starts) else s_pos + 12000
        chunk = payload_text[s_pos:e_pos]

        task_id_m = re.search(r'"taskId":"([0-9a-f-]+)"', chunk)
        if not task_id_m:
            continue
        task_id = task_id_m.group(1).strip()

        title_m = re.search(r'"title":"(.*?)"(?=,"bodyMarkdown"|,"criteria"|,"attachments"|,"amountToPayAtomic")', chunk)
        body_m = re.search(r'"bodyMarkdown":"(.*?)"(?=,"criteria"|,"attachments"|,"coinAddress"|,"status")', chunk)
        creator_m = re.search(r'"creatorAddress":"([A-Za-z0-9]{32,44})"', chunk)
        reward_m = re.search(r'"rewardTotalUsd":([0-9.]+)', chunk)
        status_m = re.search(r'"status":"([A-Z_]+)"', chunk)
        vault_m = re.search(r'"rewardVaultAddress":"([A-Za-z0-9]{32,44})"', chunk)
        prog_m = re.search(r'"pumpBountiesProgramId":"([A-Za-z0-9]{32,44})"', chunk)
        on_chain_id_m = re.search(r'"onChainBountyId":"([A-Za-z0-9_]+)"', chunk)

        # Title formatting and unescaping
        raw_title = title_m.group(1) if title_m else f"Pump.fun Bounty {task_id[:8]}"
        title = raw_title.replace(r'\"', '"').replace(r"\\", "\\").strip()

        # Body formatting
        raw_body = body_m.group(1) if body_m else ""
        body = raw_body.replace(r"\n", "\n").replace(r'\"', '"').strip()

        reward_usd = float(reward_m.group(1)) if reward_m else 0.0
        status = status_m.group(1) if status_m else "ACTIVE"
        creator = creator_m.group(1) if creator_m else ""
        vault = vault_m.group(1) if vault_m else ""
        program_id = prog_m.group(1) if prog_m else PUMPFUN_PROGRAM_ID
        on_chain_id = on_chain_id_m.group(1) if on_chain_id_m else None

        # Format reward string
        if reward_usd > 0:
            reward_str = f"${reward_usd:,.2f} USD"
        else:
            reward_str = "See Listing"

        # Determine agent eligibility
        agent_access = classify_agent_access(title, body)

        listing_id = f"pumpfun-{task_id}"
        slug = task_id

        item = {
            "id": listing_id,
            "slug": slug,
            "source": "pumpfun",
            "title": title,
            "reward": reward_str,
            "deadline": status,
            "agent_access": agent_access,
            "url": f"https://go.pump.fun/bounties/{task_id}",
            "description": body[:500],
            "creator_address": creator,
            "reward_vault": vault,
            "program_id": program_id,
            "on_chain_id": on_chain_id,
        }
        listings.append(item)

    return listings


def fetch_pumpfun_bounties(url: str = PUMPFUN_URL, timeout: int = 20) -> List[Dict[str, Any]]:
    """Fetch bounties from Pump.fun GO and parse the SSR hydration state."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            html = res.read().decode("utf-8", errors="ignore")
    except Exception as err:
        logger.warning(f"Failed to fetch Pump.fun GO HTML: {err}")
        return []

    pushes = re.findall(r'self\.__next_f\.push\(\[([0-9]+),\s*"(.*?)"\]\)', html)
    if not pushes:
        logger.debug("No self.__next_f.push hydration items found on page")
        return []

    all_listings: List[Dict[str, Any]] = []
    seen_ids = set()

    for num, payload in pushes:
        if "initialTrendingFeed" in payload or "taskId" in payload or "initialOpenFeed" in payload:
            unescaped = payload.encode("utf-8").decode("unicode_escape", errors="ignore")
            parsed = parse_bounties_from_payload(unescaped)
            for item in parsed:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    all_listings.append(item)

    return all_listings
