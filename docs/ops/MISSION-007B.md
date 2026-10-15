# MISSION 007B — FIRST TESTER ACQUISITION (Day 1)

## Context

Bounty Radar is live. The full pipeline is verified:
Superteam API → AGENT_ALLOWED filter → SQLite dedup → Discord webhook → alerts delivered and visually confirmed in the private channel.

The bottleneck is no longer technical. It is HUMAN EVIDENCE.
Zero external members have joined the validation channel.

## YOUR TASK

Prepare a complete, ready-to-execute tester-acquisition kit for the human operator. This is preparation only — do not post anywhere, do not message anyone, do not create accounts.

### DELIVERABLE 1 — `ACQUISITION.md` in the repository root

Write a single markdown file containing:

**A. Three ready-to-post invitations**, each tailored to its venue:

1. **Superteam Discord** (`#dev-chat` / `#tools-and-resources`) — casual developer tone, 2-4 sentences max, references that it filters for AGENT_ALLOWED specifically
2. **Reddit r/solana or r/SuperteamDAO** — slightly longer "built this thing" post format, includes what it does + why you built it + invite link placeholder; must comply with typical self-promotion rules (transparent, non-spammy)
3. **X/Twitter post** — under 280 characters, one hook line + one feature line + link placeholder

Each invitation must include:
- `[DISCORD_INVITE_LINK]` placeholder
- Honest framing: independent tool, free during testing, not affiliated with Superteam, no earnings guarantee
- A specific ask: "join the channel and tell me if the alerts are useful"

**B. Best posting time recommendations** based on when Solana/developer audiences are most active on each platform (general knowledge is fine).

**C. What to track after posting** — a mini checklist:
- members joined (count before/after posting)
- reactions to alerts
- questions asked
- complaints
- unprompted usefulness comments

**D. Escalation rule**: If zero members join within 48 hours of posting in one venue, try the next venue. If all three fail, report back for strategy revision.

## CONSTRAINTS

- Analysis and writing only. No posting, messaging, account creation, or spending.
- Do not modify radar.py, a2a_server.py, enrich.py, db.py, or any production code.
- Do not change the polling daemon.
- Output must be immediately usable real markdown, not descriptions of documents.

State at the top: which venue you recommend posting in FIRST and why.
