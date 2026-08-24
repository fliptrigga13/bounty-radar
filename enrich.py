"""Bounty detail enrichment with SSRF protection.

Fetches listing pages only from approved Superteam hosts and extracts
embedded __NEXT_DATA__ JSON. Read-only and strictly defensive.
"""

import html as html_mod
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

# Approved domains for enrichment
APPROVED_HOSTS = {"earn.superteam.fun", "superteam.fun"}
SLUG_RE = re.compile(r"^[A-Za-z0-9\-_]+$")
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def extract_slug(url_or_slug: str) -> Optional[str]:
    """Extract and validate a listing slug from a string or URL, rejecting SSRF attempts."""
    if not isinstance(url_or_slug, str):
        return None
    raw = url_or_slug.strip()
    if not raw:
        return None

    if "://" in raw:
        try:
            parsed = urllib.parse.urlparse(raw)
            if parsed.scheme.lower() not in ("https", "http"):
                return None
            hostname = (parsed.hostname or "").lower()
            if hostname not in APPROVED_HOSTS:
                return None  # Reject SSRF attempts to external or private IPs
            path = parsed.path.rstrip("/")
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "listing":
                slug = parts[1]
            elif len(parts) == 1:
                slug = parts[0]
            else:
                return None
        except Exception:
            return None
    else:
        # Bare slug: must not contain slashes, backslashes, or path traversal
        if "/" in raw or "\\" in raw or ".." in raw:
            return None
        slug = raw

    if slug and SLUG_RE.match(slug):
        return slug
    return None


def strip_html(raw_html: Optional[str]) -> str:
    """Safely unescape HTML and remove HTML tags."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def enrich_listing(url_or_slug: str, timeout: int = 20) -> Dict[str, Any]:
    """Fetch Superteam listing page and extract detail fields with SSRF defense.

    Returns a dict with description_text, skills, eligibility, region, requirements.
    Returns {} on any error (honest missing evidence, never fabricated).
    """
    slug = extract_slug(url_or_slug)
    if not slug:
        return {}

    target_url = f"https://earn.superteam.fun/listing/{slug}"
    req = urllib.request.Request(
        target_url,
        headers={
            "User-Agent": "bounty-radar/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return {}
            # Limit read size to 2MB to prevent memory exhaustion
            raw_bytes = resp.read(2 * 1024 * 1024)
            page_text = raw_bytes.decode("utf-8", "ignore")

        match = NEXT_DATA_RE.search(page_text)
        if not match:
            return {}

        next_data = json.loads(match.group(1))
        listing = next_data.get("props", {}).get("pageProps", {}).get("listing", {})
        if not isinstance(listing, dict):
            return {}

        raw_desc = listing.get("description") or ""
        return {
            "description_text": strip_html(raw_desc)[:8000],
            "skills": listing.get("skills") or [],
            "eligibility": listing.get("eligibility") or [],
            "region": listing.get("region"),
            "requirements": listing.get("requirements"),
        }
    except Exception:
        # Honest empty dict on any network error, 404, or JSON parse error
        return {}
