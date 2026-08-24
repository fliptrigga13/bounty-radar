def enrich_listing(listing_url: str) -> dict:
    """Agent-feed only: fetch a Superteam listing page and extract its detail fields.

    Adds description/skills/eligibility/region/requirements to an opportunity object.
    Read-only. Never raises - returns {} on any failure so callers can fall back
    to metadata-only objects (honest INSUFFICIENT EVIDENCE, not fabricated data).
    Not used by the polling daemon or Discord delivery path.
    """
    import urllib.request, json as _json, re
    slug = listing_url.rstrip("/").split("/")[-1]
    if not slug:
        return {}
    try:
        req = urllib.request.Request(
            f"https://earn.superteam.fun/listing/{slug}",
            headers={"User-Agent": "bounty-radar/1.0"})
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
        if not m:
            return {}
        L = _json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("listing", {})
        return {
            "description": L.get("description") or "",
            "skills": L.get("skills") or [],
            "eligibility": L.get("eligibility") or [],
            "region": L.get("region"),
            "requirements": L.get("requirements"),
        }
    except Exception:
        return {}
