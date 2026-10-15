# Bounty Radar - Tester Acquisition Kit (Day 1)

This kit provides ready-to-execute copy, posting schedules, tracking metrics, and escalation rules for acquiring initial human testers during the 7-day validation experiment.

---

## 0. Recommended Posting Priority

**Post in Superteam Community Discord FIRST.**

**Why:** 
1. **Highest Concentration of Target Users:** Members in the Superteam Discord already participate in Superteam Earn bounties and understand what `AGENT_ALLOWED` means without needing background education.
2. **Immediate Feedback Loop:** Real-time chat allows rapid qualitative feedback, instant bug reports, and direct interaction with the operator.
3. **Lowest Acquisition Friction:** Community members are already on Discord, eliminating cross-platform onboarding friction to join the alert channel.

---

## 1. Venue-Tailored Invitation Copy

### Venue 1: Superteam Discord (`#dev-chat` or `#tools-and-resources`)
*Tone: Casual developer, concise, focused on AGENT_ALLOWED filter.*

```text
Hey devs! 👋 Built a small open-source poller called Bounty Radar that watches Superteam Earn and sends instant Discord alerts whenever a new bounty tagged `AGENT_ALLOWED` drops. It’s an independent, 100% free tool during testing (no affiliation with Superteam, no earnings guarantee). 

Jump into the alert channel and tell me if the alerts are useful for your workflow: https://discord.gg/BmQZAMVShc
```

---

### Venue 2: Reddit (`r/solana` or `r/SuperteamDAO`)
*Tone: "I built this thing" community builder style, transparent, compliant with self-promotion rules.*

**Post Title:**
```text
I built an open-source Discord bot that alerts when agent-eligible (AGENT_ALLOWED) bounties drop on Superteam Earn
```

**Post Body:**
```text
Hey r/solana!

With more AI agents and automated tools launching on Solana, Superteam Earn started tagging select bounties as `AGENT_ALLOWED`. However, checking the site manually throughout the day is friction-heavy.

I built **Bounty Radar** — a lightweight, open-source poller that checks Superteam listings hourly, filters specifically for agent-eligible bounties, deduplicates them, and sends structured Discord alerts with title, reward amount, deadline, and direct listing links.

**Transparency & Disclaimers:**
- 🛡️ **Independent:** This is a solo community utility, not affiliated with or endorsed by Superteam.
- 🆓 **100% Free:** Free to test during this validation phase; zero token gates or paywalls.
- ⚠️ **No Earnings Guarantee:** Discovery tool only; it helps you spot listings earlier.

I've set up a dedicated Discord feed for the experiment. If you're building agents or looking for Solana bounties, join the channel and tell me if the alerts are useful:

🔗 **Discord Alert Feed:** https://discord.gg/BmQZAMVShc  
💻 **GitHub Repository:** https://github.com/fliptrigga13/bounty-radar
```

---

### Venue 3: X / Twitter
*Tone: Fast hook, feature highlight, strictly under 280 characters.*

```text
Tired of refreshing Superteam Earn for AI-friendly bounties? 🤖

I built Bounty Radar — an open-source bot that sends instant Discord alerts whenever an AGENT_ALLOWED bounty drops. Free & independent.

Join the alert feed & let me know if it helps: https://discord.gg/BmQZAMVShc
```

*(Character count: ~255 chars with placeholder)*

---

## 2. Best Posting Time Recommendations (UTC / EST)

Solana and crypto developer audiences are global, with peak activity overlapping US mornings and European afternoons:

| Platform | Recommended Day | Optimal Time Window (UTC) | Optimal Time Window (EST) | Rationale |
|---|---|---|---|---|
| **Superteam Discord** | Tuesday – Thursday | **13:00 – 16:00 UTC** | 9:00 AM – 12:00 PM EST | Active timezone bridge between Europe, India, and Americas developer communities. |
| **Reddit (`r/solana`)** | Tuesday or Wednesday | **14:00 – 17:00 UTC** | 10:00 AM – 1:00 PM EST | Reddit tech subreddits peak during US morning working hours. |
| **X / Twitter** | Monday – Thursday | **15:00 – 18:00 UTC** | 11:00 AM – 2:00 PM EST | High engagement window for Solana dev discussions and tech announcements. |

---

## 3. Post-Launch Tracking Checklist

Track these indicators within 24–48 hours of posting:

- [ ] **Member Inflow:** Record total Discord members before and 24h after posting.
- [ ] **Alert Reactions:** Track emoji reactions (e.g., 👍, 🚀, 👀) on delivered bounty notifications.
- [ ] **Questions Asked:** Note questions regarding alert frequency, data sources, or custom filters.
- [ ] **Complaints / False Positives:** Log any complaints regarding delivery lag or irrelevant listings.
- [ ] **Unprompted Utility Signals:** Record unprompted comments (e.g., *"this saved me 2 hours"*, *"just claimed one"*).

---

## 4. 48-Hour Escalation Rule

Execute venues sequentially to measure channel effectiveness:

1. **Stage 1 (Hour 0):** Post in **Superteam Discord** (`#dev-chat` / `#tools-and-resources`).
2. **Evaluation (Hour 48):**
   - If **≥ 3 members join**: Continue monitoring engagement; do not flood other venues immediately.
   - If **0 members join within 48 hours**: Escalate to **Stage 2 (Reddit `r/solana`)**.
3. **Stage 2 (Hour 48 – 96):** Post on Reddit.
   - If **0 members join within 48 hours**: Escalate to **Stage 3 (X / Twitter)**.
4. **Stage 3 (Hour 96 – 144):** Post on X / Twitter.
   - If all three venues result in **0 members after 6 days**: Halt posting and report back for value proposition / distribution strategy revision.
