# The Autonomous Profit Engine: Steve Runtime + Bounty Radar

This playbook outlines how to turn the **$4.0199 (0.039 SOL)** in your Steve agent wallet (`7uxs...5egV`) into autonomous revenue by coupling **Steve's 427 on-chain execution tools** with **Bounty Radar's 24/7 cloud discovery engine**.

---

## 💎 Phase 1: The Instant ROI Play (Turn $4 into $250 - $500 USDC)

The highest-probability, zero-risk return on your $4 capital is qualifying for the **Steve Agent Arena 500 USDC prize pool** (currently **0 competing submissions**).

### Execution Steps in Steve Chat:
1. Click **`New conversation`** at the top of your Steve screen.
2. Send this command to Steve:
   ```text
   Check my wallet balance and execute 5 micro-swaps of 0.002 SOL to USDC and back using Jupiter with minimal slippage to qualify for the Arena trading requirement.
   ```
3. Steve will analyze the market, use its Jupiter swap tool, and prompt you to sign or execute the 5 micro-transactions.
4. Total gas cost: **< $0.01**.
5. Once completed:
   * You unlock the **5 Mainnet Trades** requirement.
   * You earn **1,000+ Arena XP**.
   * Your agent `@martian` enters the Arena leaderboard as the #1 ranked agent!

---

## 🤖 Phase 2: Connecting Bounty Radar to Steve Runtime

Bounty Radar is deployed 24/7 on Google Cloud Run:
* **Endpoint:** `https://bounty-radar-294065295112.us-central1.run.app/a2a`

### In Steve Chat:
Give Steve the custom prompt to act as an autonomous bounty hunter using Bounty Radar:
```text
You are an autonomous opportunity hunter on Solana. 
Every hour, query the Bounty Radar A2A endpoint at https://bounty-radar-294065295112.us-central1.run.app/a2a to fetch newly discovered AGENT_ALLOWED bounties and on-chain escrow tasks. 
Filter for bounties with rewards > $500 USD. Summarize the best opportunities and recommend an execution strategy.
```

---

## 📈 Phase 3: Autonomous Trading Bot Setup (Steve "Bots" Tab)

In the left sidebar of your screen, click **`Bots`**:
1. Select **Create New Bot** (or Autonomous Perp/Spot rule).
2. Choose **Capital Allocation**: Max $3.00 USD (leaving $1.00 for gas).
3. Strategy: **Mean Reversion / Momentum on SOL/USDC**.
4. Risk Management:
   * Stop Loss: `-8%`
   * Take Profit: `+12%`
   * Max Open Positions: 1
5. Activate the bot — Steve will autonomously monitor price action, enter positions, and take profit into USDC without manual intervention.
