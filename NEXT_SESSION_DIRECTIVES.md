# 🚀 Next Session Agent Handoff & Directives

**Document Purpose:** Complete operational context, system credentials, verified proofs, and tomorrow's prioritized tasks for the incoming AI agent.

---

## 1. System & Identity Context

* **Project Workspace:** `C:\Users\fyou1\.gemini\antigravity-ide\scratch\bounty-radar`
* **GitHub Repository:** [https://github.com/fliptrigga13/bounty-radar](https://github.com/fliptrigga13/bounty-radar) (Branch: `master`, up-to-date)
* **Live Cloud Run URL:** `https://bounty-radar-294065295112.us-central1.run.app`
* **Agent Card Endpoint:** `https://bounty-radar-294065295112.us-central1.run.app/.well-known/agent-card.json`
* **User Accounts:**
  * **Google:** `laurenflipo1300@gmail.com`
  * **X (Twitter):** [`https://x.com/FlipLorn88622`](https://x.com/FlipLorn88622) (`@FlipLorn88622`)
  * **Steve Runtime Handle:** `@martian`
  * **Steve Runtime URL:** `https://steve.oobeprotocol.ai/#agent`
  * **Agent Solana Address:** `7uxsUjTRxYfgRh9L2tYy2io64t6EAjae5LXCaGok5egV`
  * **Current Wallet Balances:** `0.0375 SOL` (~$3.92) + `0.00 USDC`
  * **Funding Wallet:** `Fmh2ejKKzk2z9cMHbrMXAMZCfp48Y3FyAwQj8uNFLTrz`

---

## 2. Competition Submissions Status ($1,000 USD Active)

### Submission #1: Steve Agent Arena (500 USDC)
* **Superteam Earn Listing:** [https://earn.superteam.fun/listing/steve-agent-arena-launch-your-agent-and-win-500-usdc/](https://earn.superteam.fun/listing/steve-agent-arena-launch-your-agent-and-win-500-usdc/)
* **Status:** **SUBMITTED (#1 Pioneer Submission in the Competition)**
* **On-Chain Trade #1 Proof:** [Solscan 48ezq8...SLC3m7](https://solscan.io/tx/48ezq8NFEJGB1tp7LM7GnZu335GKCaSrBEQyDZHFaGJvRQo2B7HdCBvobedLKEPpZtuuJcYPJp6N1rMpDrSLC3m7) (Whirlpool SOL → USDC)
* **On-Chain Trade #2 Proof:** [Solscan 23wcHb...BoCqn5](https://solscan.io/tx/23wcHb3C8xVKkURc8LF4rFaF7g8pDSxtC72xEBmn8uApt3hP29jMF89w4TD55qK2HFbinZLRw76kqhRsbiBoCqn5) (Whirlpool SOL → USDC)
* **On-Chain Trade #3 Proof:** [Solscan 3xPU5N...AF99](https://solscan.io/tx/3xPU5NX7HZPPWMsZuTAbn1R84dWXVDcwibjDm4EnVHUMBHGrL8Wp32t95JfGV6ZM4E9wWjp8wbJpX3T4MWaYAF99) (Jupiter Invariant 0.40 USDC → 0.003835 SOL)
* **Social Proof:** Published 4-part Technical Thread on X with 2.0x Tech Day boost (+1,000 XP).

### Submission #2: Build and Demo a Mermail Agent Skill (500 USDC)
* **Superteam Earn Listing:** [https://earn.superteam.fun/listing/build-and-demo-a-mermail-agent-skill/](https://earn.superteam.fun/listing/build-and-demo-a-mermail-agent-skill/)
* **Status:** **SUBMITTED** (Deadline: September 23, 2026; submissions are editable until deadline).
* **Skill Definition:** [`skills/bounty-radar/SKILL.md`](https://github.com/fliptrigga13/bounty-radar/blob/master/skills/bounty-radar/SKILL.md)
* **1080p Video Demonstration:** [`bounty_radar_demo.mp4`](https://github.com/fliptrigga13/bounty-radar/blob/master/bounty_radar_demo.mp4) (3m 20s, full narration, rendered via FFmpeg, playable directly on GitHub).

---

## 3. Core Architecture & Files

| File | Purpose |
|---|---|
| `pumpfun.py` | Direct Next.js SSR hydration parser for `go.pump.fun` on-chain task escrows (`goGzNYTYk...rKiV`). |
| `market_sentinel.py` | Real-time SOL spot price (<100ms via Binance/Coinbase) with Discord alerts for oversold ($98.60–$99.20) and breakout ($101.10+) zones. |
| `radar.py` | Dual-source poller running both bounty triage and market sentinel. |
| `a2a_server.py` | A2A Protocol v0.3 JSON-RPC server with Agent Card at `/.well-known/agent-card.json`. |
| `ACTION_TRACKER.md` | Master checklist, bookmarks, and transaction receipts. |
| `test_*.py` | 48 unit & integration tests covering all modules (**48/48 Passing**). |

---

## 4. Prioritized Directives for Tomorrow's Agent

### 📌 Directive 1: Daily Steve Routine & Streak Maintenance (8:00 PM EST)
1. In Steve runtime, ensure the active model is set to **`google/gemma-4-31b-it:free`** or **`nvidia/nemotron-3.5-lightning:free`** (do NOT use `nemotron-3-ultra-550b`, which hits 503 overloads).
2. Complete the daily social mission on X for **+40 XP** to maintain `@martian`'s ranking on the Season 0 Leaderboard.

### 📌 Directive 2: Compound the 0.40 USDC Balance on a Dip
* The wallet holds **`0.4016 USDC`**.
* When Market Sentinel signals that SOL has pulled back into the **Oversold Bounce Zone ($98.60 – $99.00)**, guide the user to paste this prompt into Steve:
  ```text
  Use Orca Whirlpool direct route to swap 0.40 USDC to SOL with 50 bps slippage.
  ```
* Have the user click **Approve** in the Steve UI. This completes a profitable mean-reversion cycle and increases the wallet's SOL balance!

### 📌 Directive 3: Monitor Superteam Earn Judging & Payouts
1. Check the [Steve Agent Arena Listing](https://earn.superteam.fun/listing/steve-agent-arena-launch-your-agent-and-win-500-usdc/) for review status.
2. Confirm USDC prize delivery to `7uxsUjTRxYfgRh9L2tYy2io64t6EAjae5LXCaGok5egV`.

### 📌 Directive 4: Discord Webhook Channel Split (If Requested)
* If the user wants separate channels for bounties vs. market signals, obtain the webhook for `# trading-signals` or `# bounty` from Discord channel settings and update `DISCORD_WEBHOOK_URL` in `.env.local` and Cloud Run.
