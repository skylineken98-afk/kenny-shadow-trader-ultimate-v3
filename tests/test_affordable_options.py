"""Synthetic checks only. No profitability, execution or live quote claims."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from core.affordable_options import screening_policy, price_quality
from core.request_signals import rank_row
from core.v1_primary_scanner import snapshot_candidate, original_v1_score

class AffordableOptionsTests(unittest.TestCase):
    def test_budget_tiers(self):
        self.assertEqual(screening_policy(50)["max_spread_pct"],35)
        self.assertEqual(screening_policy(100)["max_spread_pct"],30)
        self.assertEqual(screening_policy(200)["max_spread_pct"],25)
        self.assertEqual(screening_policy(500)["max_spread_pct"],20)
    def test_cheap_contract_is_eligible_but_speculative(self):
        q, reason=price_quality(0.09,0.12,50,1,10)
        self.assertIsNone(reason)
        self.assertEqual(q["premium_band"],"$50")
        self.assertEqual(q["liquidity_label"],"SPECULATIVE_HIGH_FRICTION")
        self.assertAlmostEqual(q["estimated_roundtrip_spread_cost"],3)
    def test_not_every_wide_spread_passes(self):
        self.assertEqual(price_quality(0.01,0.15,50,100,500)[1],"SPREAD_TOO_WIDE")
    def test_still_enforces_total_cost(self):
        self.assertEqual(price_quality(0.49,0.51,50,100,500)[1],"INVALID_OR_OVER_BUDGET")
    def test_lower_tier_volume_and_oi_not_fabricated(self):
        self.assertEqual(price_quality(0.09,0.12,50,0,10)[1],"LOW_VOLUME")
        self.assertEqual(price_quality(0.09,0.12,50,1,0)[1],"LOW_OPEN_INTEREST")
    def test_v3_under_50_research_result(self):
        now=datetime(2026,11,10,15,tzinfo=timezone.utc)
        row={"contractSymbol":"SPY261110C00500000","strike":500,
             "bid":0.09,"ask":0.12,"volume":1,"openInterest":10,
             "lastTradeDate":now-timedelta(minutes=1)}
        result=rank_row(row,"SPY","2026-11-10","call",500,
                        "BULLISH",50,now)
        self.assertIsNotNone(result)
        self.assertEqual(result["liquidity_label"],"SPECULATIVE_HIGH_FRICTION")
        self.assertFalse(result["verified_executable"])
    def test_v1_premium_not_automatically_penalized(self):
        self.assertGreater(original_v1_score(0.12,10,None,0.5),
                           original_v1_score(0.12,20,None,0.5))
    def test_v1_option_snapshot_budget(self):
        now=datetime(2026,11,10,15,tzinfo=timezone.utc)
        snap=SimpleNamespace(
            latest_quote=SimpleNamespace(bid_price=0.09,ask_price=0.12,timestamp=now),
            latest_trade=None,greeks=None)
        r=snapshot_candidate("SPY261110C00500000",snap,50,now.date(),now=now)
        self.assertIsNotNone(r)
        self.assertEqual(r["liquidity_label"],"SPECULATIVE_HIGH_FRICTION")
        self.assertEqual(r["cost"],12.0)

if __name__=="__main__":
    unittest.main()
