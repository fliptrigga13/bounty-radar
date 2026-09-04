# @martian Season 0 policy

Machine-readable file: `policy.json`.

Steve pipeline: intent → data → analysis → **policy** → simulate → **user sign (Flip)** → journal.

Policy-check is step 04. User-sign is step 06. Auto-execute stays off.

## Fail closed

| Check | Fail if |
|---|---|
| `never_sign` | any unsigned broadcast, “just send it”, or key in git/chat/memory |
| `requires_human_approve` | Approve is skipped or auto-execute is on |
| `perps` / `adrena` | `sap_adrena_build_open_long` or any perp / funding / leverage path |
| `phoenix` | open-orders or market accounts (rent) |
| `bridge` | any bridge, including “bridge 0.2 SOL” |
| `halt_below_sol` | SOL `< 0.008` → HALT and HOLD |
| `gas_reserve_sol` | post-trade SOL would drop below `0.012` |
| `max_trade_sol` | size `> 0.002` SOL |
| `spectrumfi` | Trade/Tweet/Earn form (SKIP prize) |
| `docker_autonomy` | Cloud Run / Docker deploy to “fix” missing A2A skills tonight |
| model | `nvidia/nemotron-3-ultra-550b-a55b:free` (503s; switch to Gemma) |

A Jupiter quote is a quote. A router is not a permission slip. Radar ACCEPT is not permission.

Jupiter receipts on this wallet are Jupiter (or Jupiter-routed AMM) fills, not Spectrum fills. Do not submit them to Spectrumfi.

## What this policy allows tonight

- Read-only balance / health / feed scout.
- Files in this folder.
- HUMAN: X thread as `@FlipLorn88622`, Steve prompt 1 (streak), Arena file of the thread URL.
- Flip clicks Approve even if spend is zero.

## What this policy forbids tonight

- Prompt 3 (0.002 SOL quote) unless Flip explicitly says to **and** reserve survives.
- SAP registry spend unless rent is counted and post-tx SOL ≥ 0.012.
- MagicBlock spend.
- Phoenix seats, Adrena, perps, leverage, bridge, extra capital.
