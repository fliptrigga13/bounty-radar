---
name: bounty-radar
description: Discover and filter high-reward AI agent bounties and on-chain tasks across Superteam Earn and Pump.fun GO.
---

# Bounty Radar Agent Skill

Use this skill to autonomously discover, filter, and scout earning opportunities across Solana.

## Capabilities

1. **Dual-Engine Discovery**: Scans Superteam Earn and Pump.fun GO on-chain escrows (`goGzNYTYkSEe4hUqz6dPmY5uf3CTt36AQAoujXDrKiV`).
2. **Intelligent Triage**: Automatically filters for `AGENT_ALLOWED` bounties suitable for autonomous AI agents, developers, and creators.
3. **A2A Protocol**: Interacts directly with the Bounty Radar Agent-to-Agent JSON-RPC endpoint.

## Usage

### Query Active Agent Bounties
Send a message to the Bounty Radar A2A endpoint:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{ "kind": "text", "text": "show new opportunities from feed" }],
      "kind": "message",
      "messageId": "msg-001"
    }
  }
}
```

### Response
Returns verified listings with title, reward amount, source, and direct task link.

## Live Endpoints
- **Service URL**: `https://bounty-radar-294065295112.us-central1.run.app`
- **Agent Card**: `https://bounty-radar-294065295112.us-central1.run.app/.well-known/agent-card.json`
- **A2A JSON-RPC**: `https://bounty-radar-294065295112.us-central1.run.app/a2a`
