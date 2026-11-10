"""Synthetic momentum/volume scanner regression tests — not performance results."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import pandas as pd
from core.momentum_volume import qualify
from core.market import confluence


def candles(direction=1, last_volume=250, last_close=None):
    idx = pd.date_range("2026-11-10T14:00:00Z", periods=65, freq="min")
    closes = [100 + direction * i * 0.015 for i in range(65)]
    if last_close is not None:
        closes[-1] = last_close
    else:
        closes[-1] += direction * 0.35
    return pd.DataFrame({
        "Open": [x-0.05 for x in closes],
        "High": [x+0.10 for x in closes],
        "Low": [x-0.10 for x in closes],
        "Close": closes,
        "Volume": [100]*64+[last_volume],
    }, index=idx)

class MomentumTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 15, 5, tzinfo=timezone.utc)

    def test_long_and_short(self):
        for d, expected in [(1, "BULLISH"),(-1,"BEARISH")]:
            s = qualify(candles(d), symbol="IWM", now=self.now)
            self.assertEqual(s["status"], "SETUP", s)
            self.assertEqual(s["side"], expected)
            self.assertEqual(s["strategy"], "MOMENTUM_VOLUME")
            self.assertGreaterEqual(s["rvol"], 1.2)

    def test_volume_missing_blocks_setup(self):
        s = qualify(candles(last_volume=1), now=self.now)
        self.assertEqual(s["status"],"WAIT")

    def test_stale_candles_do_not_signal(self):
        s=qualify(candles(), now=datetime(2026,11,10,16,tzinfo=timezone.utc))
        self.assertEqual(s["status"],"STALE_DATA")

    def test_forming_bar_ignored(self):
        s=qualify(candles(),now=datetime(2026,11,10,15,tzinfo=timezone.utc))
        self.assertEqual(s["status"],"SETUP")
        early=qualify(candles(),now=datetime(2026,11,10,14,59,tzinfo=timezone.utc))
        self.assertNotEqual(early["status"],"SETUP")

    def test_default_kst_scanner_uses_momentum_not_timeframes(self):
        with patch("core.market.history",return_value=candles()) as feed:
            s=confluence("SPY")
        self.assertEqual(s["strategy"],"MOMENTUM_VOLUME")
        self.assertEqual(feed.call_args.kwargs["interval"],"1m")
        self.assertNotIn("liquidity_fvg",s)

if __name__=="__main__":
    unittest.main()
