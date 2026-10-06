# MISSION 007C — LAUNCH READINESS SWEEP + DAY 1 OPERATIONS

## Context

All technical work is complete. ACQUISITION.md is committed. The radar daemon
is running. The Discord channel exists with zero external members.

The human operator is about to post the Superteam Discord invitation (Venue 1
from ACQUISITION.md). Your job: make sure nothing technical blocks Day 1, and
prepare the tracking infrastructure for when members arrive.

## TASKS

### TASK 1 — Pre-flight sweep
Run and report:
- `python check.py` full output
- Confirm radar daemon state (poller process alive? last poll timestamp?)
- Confirm all 3 AGENT_ALLOWED listings are in `delivered` or `pending` state
- Confirm no `permanently_failed` rows exist
- Confirm `.env.local` / secrets are NOT committed to git (`git status` clean
  of secret files)

### TASK 2 — Fix anything broken found in Task 1
Only operational fixes. No features.

### TASK 3 — Create `DAY1-CHECKLIST.md`
A one-page checklist for the operator covering:
1. Get Discord invite link (exact clicks)
2. Post Venue 1 invitation (reference ACQUISITION.md copy)
3. What time window to post (from ACQUISITION.md recommendations)
4. Record baseline member count BEFORE posting
5. Check back at +24h and +48h; what numbers to record
6. When to escalate to Reddit (48h rule from ACQUISITION.md)

### TASK 4 — Verify the invite link placeholder flow
Confirm `ACQUISITION.md` invitations use `[DISCORD_INVITE_LINK]` placeholder
consistently and note exactly where the operator replaces it.

Commit everything. Push to origin/master.

Report: what you fixed, what you verified, commit hashes.
