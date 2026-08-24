# Bounty Radar - Day 1 Operator Execution Checklist

This one-page checklist guides the human operator through acquiring the first cohort of testers on Day 1.

---

## Step 1: Generate Never-Expiring Discord Invite Link

1. Open the Discord app / web client and navigate to your Bounty Radar alert server/channel.
2. Click the channel name or click the **Invite People** icon (person with `+` icon) next to the channel name.
3. Click **"Edit invite link"** at the bottom of the popup.
4. Set:
   - **Expire After:** `Never`
   - **Max Number of Uses:** `No limit`
5. Click **"Generate a New Link"**.
6. Click **"Copy"** (e.g. `https://discord.gg/xxxxxxxxxx`).

---

## Step 2: Post Venue 1 (Superteam Discord)

1. Open **Superteam Discord** (join if not already a member).
2. Navigate to `#dev-chat` or `#tools-and-resources` (or equivalent showcase channel).
3. Copy the **Venue 1 invitation text** from [`ACQUISITION.md`](ACQUISITION.md) (the invite link is already embedded):

```text
Hey devs! 👋 Built a small open-source poller called Bounty Radar that watches Superteam Earn and sends instant Discord alerts whenever a new bounty tagged `AGENT_ALLOWED` drops. It’s an independent, 100% free tool during testing (no affiliation with Superteam, no earnings guarantee). 

Jump into the alert channel and tell me if the alerts are useful for your workflow: https://discord.gg/BmQZAMVShc
```

4. Hit **Send**.

---

## Step 3: Optimal Posting Time Window

Post during the peak developer overlap window:
- **Optimal Time:** **13:00 – 16:00 UTC** (9:00 AM – 12:00 PM EST)
- **Target Days:** Tuesday – Thursday (highest active engagement)

---

## Step 4: Record Baseline Count (Before Posting)

Before posting in Superteam Discord, record:
- **Posting Date & Time:** `2026-08-24 18:34 UTC` (2:34 PM EST)
- **Initial Channel Member Count:** `7 members` (Baseline)
- **Venues Live:** 
  1. `Solana Tech Discord (#core-technology)` — Live at 18:34 UTC
  2. `X / Twitter (@Solana / Devs)` — Live at 18:44 UTC

---

## Step 5: Check-in & Logging Schedule

Log the metrics below in [`PROMOTION.md`](PROMOTION.md) at each milestone:

### Check-in 1: +24 Hours
- [ ] **Total Member Count:** `____` (Net new: `____`)
- [ ] **Alert Reactions / Emoji count:** `____`
- [ ] **Questions or Comments in Discord:** `____`
- [ ] **Technical issues / bugs reported:** `____`

### Check-in 2: +48 Hours
- [ ] **Total Member Count:** `____` (Net new: `____`)
- [ ] **Alert Reactions / Emoji count:** `____`
- [ ] **Unprompted utility feedback:** `____`

---

## Step 6: 48-Hour Escalation Rule

- **If ≥ 3 members joined by +48h:**  
  ✅ Milestone met. Do not post elsewhere yet. Engage testers, monitor alerts, and prepare for the Day 4/5 price question.
- **If 0 members joined by +48h:**  
  🚨 Trigger **Venue 2 (Reddit `r/solana` / `r/SuperteamDAO`)** using the Venue 2 copy from [`ACQUISITION.md`](ACQUISITION.md).
