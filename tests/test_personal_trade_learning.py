import unittest
from datetime import datetime, timedelta, timezone

from core.personal_trade_learning import normalize_closed_trade, research_summary, persist_verified_trade

class PersonalTradeLearningTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.trade = {
            "provider": "ROBINHOOD", "broker_trade_id": "example-001",
            "symbol": "SPX", "asset_type": "OPTION_LONG_PUT", "quantity": "1",
            "entry_time": (now - timedelta(hours=2)).isoformat(),
            "exit_time": (now - timedelta(hours=1)).isoformat(),
            "entry_total": "200", "exit_total": "350", "fees_total": "1",
            "closed": True, "fill_verified": True,
        }

    def test_net_pnl_and_dedup(self):
        a=normalize_closed_trade(self.trade)
        b=normalize_closed_trade(self.trade)
        self.assertEqual(a["trade_id"], b["trade_id"])
        self.assertEqual(a["net_pnl"], "149")
        self.assertEqual(a["net_return_pct"], 74.5)
        self.assertFalse(a["execution_enabled"])
        self.assertEqual(research_summary([a])["verified_closed_trades"],1)

    def test_unverified_rejected(self):
        with self.assertRaises(ValueError):
            normalize_closed_trade({**self.trade,"fill_verified":False})

    def test_future_feature_rejected(self):
        with self.assertRaises(ValueError):
            normalize_closed_trade(self.trade, {"spx_trend":"BEARISH"})

        with self.assertRaises(ValueError):
            normalize_closed_trade({**self.trade,"feature_available_at":self.trade["exit_time"]},
                                   {"spx_trend":"BEARISH"})

    def test_unsupported_short_rejected(self):
        with self.assertRaises(ValueError):
            normalize_closed_trade({**self.trade,"asset_type":"EQUITY_SHORT"})

    def test_disabled_has_no_writes(self):
        with self.assertRaises(PermissionError):
            persist_verified_trade("00000000-0000-0000-0000-000000000001", self.trade)
if __name__ == "__main__":
    unittest.main()
