"""Unit tests for Market Sentinel module."""

import json
import unittest
from unittest.mock import MagicMock, patch

import market_sentinel


class TestMarketSentinel(unittest.TestCase):
    def test_evaluate_market_condition_oversold(self):
        zone, desc = market_sentinel.evaluate_market_condition(99.00)
        self.assertEqual(zone, "OVERSOLD_BOUNCE")
        self.assertIn("Oversold Bounce", desc)

        zone, desc = market_sentinel.evaluate_market_condition(98.50)
        self.assertEqual(zone, "OVERSOLD_BOUNCE")

    def test_evaluate_market_condition_breakout(self):
        zone, desc = market_sentinel.evaluate_market_condition(101.15)
        self.assertEqual(zone, "BREAKOUT_CONTINUATION")
        self.assertIn("Breakout Continuation", desc)

    def test_evaluate_market_condition_neutral(self):
        zone, desc = market_sentinel.evaluate_market_condition(100.20)
        self.assertIsNone(zone)
        self.assertIsNone(desc)

    @patch("urllib.request.urlopen")
    def test_get_sol_price_binance_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"symbol": "SOLUSDT", "price": "100.50"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        price = market_sentinel.get_sol_price()
        self.assertEqual(price, 100.50)

    @patch("urllib.request.urlopen")
    def test_get_sol_price_coinbase_fallback(self, mock_urlopen):
        # 1st call fails (Binance), 2nd call succeeds (Coinbase)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": {"amount": "100.40", "base": "SOL"}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        mock_urlopen.side_effect = [Exception("Binance timeout"), mock_resp]

        price = market_sentinel.get_sol_price()
        self.assertEqual(price, 100.40)

    @patch("market_sentinel.send_discord_market_alert")
    @patch("market_sentinel.get_sol_price")
    def test_check_market_triggers_cooldown(self, mock_price, mock_send):
        mock_price.return_value = 98.90
        mock_send.return_value = True

        # Reset global state for test
        market_sentinel._LAST_ALERT_TIME = 0.0
        market_sentinel._LAST_ALERT_ZONE = ""

        # First trigger fires
        res1 = market_sentinel.check_market_triggers(webhook_url="https://discord.com/api/webhooks/test")
        self.assertIn("dispatched to Discord", res1)
        self.assertEqual(mock_send.call_count, 1)

        # Immediate second trigger is in cooldown
        res2 = market_sentinel.check_market_triggers(webhook_url="https://discord.com/api/webhooks/test")
        self.assertIn("in cooldown", res2)
        self.assertEqual(mock_send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
