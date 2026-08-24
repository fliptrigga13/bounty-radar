# Bounty Radar

Discovers new agent-eligible bounties on Superteam Earn, deduplicates them,
enriches them with listing details, and delivers structured alerts — plus an
A2A (Agent-to-Agent) v0.3 server that serves the same data to other agents.

Standard library only. No third-party dependencies.

## Components

| File | Purpose |
|---|---|
| `radar.py` | Poller: fetch → filter AGENT_ALLOWED → dedup → Discord/Telegram alert |
| `a2a_server.py` | A2A JSON-RPC server (card + 3 skills) on port 8080 |
| `enrich.py` | Listing detail enrichment (agent-feed use) |
| `AGENT_INTEGRATION.md` | How another agent consumes the feed |
| `.well-known/agent-card.json` | A2A Agent Card |
| `test_a2a_server.py` | Offline tests (mocked HTTP; no live calls) |

## Environment variables

| Variable | Used by | Required | Default |
|---|---|---|---|
| `RADAR_CHANNEL` | radar.py | no | `telegram` (`discord` or `telegram`) |
| `DISCORD_WEBHOOK_URL` | radar.py | if discord | — |
| `TELEGRAM_BOT_TOKEN` | radar.py | if telegram | — |
| `TELEGRAM_CHAT_ID` | radar.py | if telegram | — |
| `RADAR_DB` | both | no | `radar.db` |
| `RADAR_INTERVAL_SEC` | radar.py | no | `3600` |
| `A2A_PORT` | a2a_server.py | no | `8080` |

Copy `.env.example` and fill in real values. Never commit `.env.local`.

## Run the poller (one-shot)

WINDOWS POWERSHELL
```powershell
python .\radar.py --once
```

LINUX
```bash
python3 ./radar.py --once
```

## Run the poller (daemon)

WINDOWS POWERSHELL
```powershell
$env:RADAR_CHANNEL="discord"
$env:DISCORD_WEBHOOK_URL="<your webhook>"
python .\radar.py
```

LINUX
```bash
export RADAR_CHANNEL=discord
export DISCORD_WEBHOOK_URL="<your webhook>"
python3 ./radar.py
```

Stop with `Ctrl+C`. The SQLite database persists across restarts; already-seen
listings are never re-sent.

## Run the A2A server

WINDOWS POWERSHELL
```powershell
python .\a2a_server.py
```

Verify:
```powershell
curl.exe http://localhost:8080/health
curl.exe http://localhost:8080/a2a          # Agent Card
```

Example A2A call (feed subscription):
```powershell
$body = '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"show new opportunities from the feed"}],"kind":"message","messageId":"m1"}}}'
Invoke-RestMethod -Uri http://localhost:8080/a2a -Method Post -Body $body -ContentType "application/json"
```

## Run tests

```powershell
python -m unittest test_a2a_server -v
```
All tests are offline: HTTP is mocked, databases are temporary files.

## Docker

```bash
docker build -t bounty-radar .
docker run --rm -p 8080:8080 \
  -e RADAR_CHANNEL=discord \
  -e DISCORD_WEBHOOK_URL="<webhook>" \
  bounty-radar
```

The container runs the A2A server. To run the poller instead:
```bash
docker run --rm -e RADAR_CHANNEL=discord -e DISCORD_WEBHOOK_URL="<wh>" bounty-radar python radar.py
```

## Safety model

The service is read-only with respect to bounty sources. It never performs,
submits, funds, signs, or accepts bounties. All remote content (Superteam API,
listing pages, evaluator responses) is treated as untrusted external data.
