"""Market Sentinel Module for Bounty Radar.

Continuously monitors live SOL/USD spot price against algorithmic entry zones
(Oversold Bounce: <= $99.20 | Breakout: >= $101.10) and automatically dispatches
actionable trading alerts with pre-filled Steve commands to Discord.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple

logger = logging.getLogger("bounty-radar.market-sentinel")

# Thresholds identified by Steve Runtime technical indicators
OVERSOLD_THRESHOLD = 99.20
BREAKOUT_THRESHOLD = 101.10

# Cooldown between duplicate alerts for the same zone (in seconds)
ALERT_COOLDOWN_SECS = 1800  # 30 minutes

_LAST_ALERT_TIME = 0.0
_LAST_ALERT_ZONE = ""


def get_sol_price(timeout: int = 5) -> Optional[float]:
    """Fetch live SOL/USD price from Binance with Coinbase fallback."""
    # 1. Try Binance
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT"
        req = urllib.request.Request(url, headers={"User-Agent": "BountyRadar/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return float(data["price"])
    except Exception as e:
        logger.debug(f"Binance ticker failed: {e}, attempting Coinbase fallback...")

    # 2. Try Coinbase
    try:
        url = "https://api.coinbase.com/v2/prices/SOL-USD/spot"
        req = urllib.request.Request(url, headers={"User-Agent": "BountyRadar/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return float(data["data"]["amount"])
    except Exception as e:
        logger.warning(f"Coinbase ticker fallback failed: {e}")

    return None


def evaluate_market_condition(price: float) -> Tuple[Optional[str], Optional[str]]:
    """Evaluate whether current price is within a key trading action zone."""
    if price <= OVERSOLD_THRESHOLD:
        zone = "OVERSOLD_BOUNCE"
        desc = f"Oversold Bounce Zone (${price:.2f} <= ${OVERSOLD_THRESHOLD:.2f})"
        return zone, desc
    elif price >= BREAKOUT_THRESHOLD:
        zone = "BREAKOUT_CONTINUATION"
        desc = f"Breakout Continuation Zone (${price:.2f} >= ${BREAKOUT_THRESHOLD:.2f})"
        return zone, desc
    return None, None


def send_discord_market_alert(price: float, zone: str, desc: str, webhook_url: str) -> bool:
    """Send formatted market entry alert with one-click Steve prompt to Discord."""
    embed = {
        "title": "🎯 SOL ENTRY SIGNAL TRIGGERED!",
        "description": (
            f"**Current SOL Price:** `${price:.2f} USD`\n"
            f"**Trigger:** {desc}\n\n"
            f"**👉 Action Required:** Open Steve and paste:\n"
            f"```text\nCheck SOL RSI and prepare the 0.002 SOL trade if in the entry zone.\n```\n"
            f"[Open Steve Runtime](https://steve.oobeprotocol.ai)"
        ),
        "color": 0x10B981 if zone == "OVERSOLD_BOUNCE" else 0x3B82F6,
        "footer": {"text": "Bounty Radar Sentinel • Steve Runtime Integration"},
    }

    payload = {
        "content": "⚡ **Autonomous Market Signal Triggered for @martian** ⚡",
        "embeds": [embed],
    }

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "BountyRadar-Sentinel/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 204)
    except Exception as err:
        logger.warning(f"Failed to deliver Discord market alert: {err}")
        return False


def check_market_triggers(webhook_url: Optional[str] = None) -> Optional[str]:
    """Check market price and fire Discord alert if trigger conditions are met."""
    global _LAST_ALERT_TIME, _LAST_ALERT_ZONE

    price = get_sol_price()
    if price is None:
        return None

    zone, desc = evaluate_market_condition(price)
    if not zone or not desc:
        return f"SOL at ${price:.2f} (Neutral / No trigger)"

    now = time.time()
    # Check cooldown
    if zone == _LAST_ALERT_ZONE and (now - _LAST_ALERT_TIME) < ALERT_COOLDOWN_SECS:
        return f"SOL at ${price:.2f} ({zone} active, alert in cooldown)"

    # Deliver alert if webhook provided
    if not webhook_url:
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if webhook_url:
        success = send_discord_market_alert(price, zone, desc, webhook_url)
        if success:
            _LAST_ALERT_TIME = now
            _LAST_ALERT_ZONE = zone
            return f"SOL at ${price:.2f} ({zone} alert dispatched to Discord!)"

    return f"SOL at ${price:.2f} ({zone} triggered, no webhook configured)"
