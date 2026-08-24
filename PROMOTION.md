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

Join the alert feed here: [INSERT DISCORD INVITE LINK]
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

> *"Hey everyone! We've been running the Bounty Radar alert feed for several days now. If this alert feed helps you catch agent-eligible bounties early and saves you time checking listings manually, what would be a fair monthly price for you to keep receiving real-time alerts once the free beta concludes:*
> 
> *A) $10 / month*  
> *B) $25 / month*  
> *C) $50 / month*  
> *D) Would only use if free / ad-supported*  
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
