# Bounty Radar - Operator Promotion & Validation Cheat Sheet

This one-page cheat sheet guides the operator through promoting the Bounty Radar Discord alert channel during the 7-day human validation experiment.

---

## 1. Exact Discord Invitation Copy

Copy and paste this exact text when inviting testers and developers:

```text
Hey everyone! 👋 

I built an independent, open-source bot called Bounty Radar that automatically tracks and alerts when new agent-eligible (AGENT_ALLOWED) bounties drop on Superteam Earn. 

⚡ Instant Discord alerts with bounty title, reward amount, deadline, and direct link
🆓 100% free to join and test during our 7-day validation period
🛡️ Independent community tool — not affiliated with Superteam, and no earnings guaranteed.

Join the alert feed here: https://discord.gg/BmQZAMVShc
GitHub repo & docs: https://github.com/fliptrigga13/bounty-radar
```

---

## 2. Target Venues & Posting Rules

| Venue | Channel / Location | Posting Rules & Guidelines |
|---|---|---|
| **Superteam Community Discord** | `#dev-chat`, `#tools-and-resources`, `#general` | • Post only in designated discussion or showcase channels.<br>• Do not DM users unsolicited.<br>• Be transparent: explicitly state it is an independent community project.<br>• Emphasize zero cost and open-source nature. |
| **Solana Developer Groups** (Discord / Telegram) | `#general-dev`, `#solana-dev`, `#tools` | • Frame as an agent/developer workflow productivity tool.<br>• Respect channel self-promotion rules (post only in `#resources` or when relevant).<br>• Solicit feedback on alert timeliness and formatting. |
| **X (Twitter) & Developer Reddit** | `@SolanaDevs`, `r/solana`, Solana builder threads | • Keep tweet/post concise with key value: "Never miss an AGENT_ALLOWED bounty on Superteam".<br>• Include disclaimer: Independent project, free beta.<br>• Link to Discord invite and GitHub repository. |

---

## 3. Day 4 / Day 5 Price Question (Verbatim)

Send this exact message in the Discord feedback channel on Day 4 or Day 5 of the experiment:

> *"Hey everyone! We've been running the Bounty Radar alert feed for several days now. If these alerts help you catch agent-eligible bounties and save you time checking listings manually, what would be a fair monthly price to keep receiving them after the free beta concludes:*
> 
> *A) Free / ad-supported*  
> *B) $3 / month*  
> *C) $5 / month*  
> *D) $10 / month*  
> 
> *Drop a reaction or reply with your thoughts!"*

---

## 4. Daily Scorecard Template

Log metrics daily during the 7-day experiment:

```markdown
### Daily Scorecard - Day [1..7] (Date: YYYY-MM-DD)

| Metric | Target | Actual | Notes |
|---|---|---|---|
| New Superteam Listings Detected | — | | Total listings ingested by radar.py |
| AGENT_ALLOWED Bounties Alerted | > 0 | | Count delivered to Discord channel |
| New Discord Members Joined | 5-10 | | New testers in the channel |
| User Reactions / Messages | > 0 | | Community engagement |
| Delivery Success Rate (%) | 100% | | % delivered vs failed |
| Operational Issues / Errors | 0 | | Any 429s, retry_wait, or crash recoveries |

**Key Learnings & Feedback:**
- Feedback from users:
- Pricing signals:
- Action items for tomorrow:
```

---

## 5. Live Scorecards Log

### Daily Scorecard - Day 1 (Date: 2026-09-02)

| Metric | Target | Actual | Notes |
|---|---|---|---|
| New Superteam Listings Detected | — | 4 | Total 40 listings stored in SQLite WAL database |
| AGENT_ALLOWED Bounties Alerted | > 0 | 1 | "Steve Agent Arena: Launch Your Agent & Win 500 USDC" |
| Discord Alert Channel Delivery | 100% | 100% | Successfully pushed to webhook with zero retries |
| Active Services | Both | Online | A2A JSON-RPC (port 8080) + Background Discovery Poller |
| Operational Issues / Errors | 0 | 0 | Zero 429s, zero transient failures, clean recovery |

**Key Learnings & Feedback:**
- Real-time detection verified against Superteam Earn API.
- New high-value bounty detected: 500 USDC agent competition ending 2026-09-16.
- A2A v0.3 Protocol endpoint (`/a2a`) successfully returned listing payload to agent queries.

