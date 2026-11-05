import unittest
from kst_options.evidence_ranking import activity,relative_strength,rank_with_evidence

class EvidenceRankingTest(unittest.TestCase):
 def test_volume_is_not_latest_trade_size(self):
  a=activity(contract_volume=350,open_interest=120,
    historical_volume=[50,100,90,110,100],as_of="2026-11-05T19:00:00Z",
    oi_date="2026-11-04",source="provider")
  self.assertEqual(a["contract_volume"],350)
  self.assertEqual(a["open_interest"],120)
  self.assertEqual(a["relative_contract_volume"],3.889)
  self.assertTrue(a["unusual_volume_proxy"])
  self.assertGreater(a["volume_oi_ratio"],2.9)
  self.assertFalse(a["is_institutional_flow"])
 def test_missing_is_unknown_not_zero(self):
  a=activity(historical_volume=[10,20,30])
  self.assertIsNone(a["contract_volume"])
  self.assertIsNone(a["unusual_volume_proxy"])
  self.assertIsNone(a["open_interest"])
 def test_missing_keeps_base_rank(self):
  c=dict(score=83.4,option_type="PUT",risk_snapshot={})
  ranked=rank_with_evidence(c)
  self.assertAlmostEqual(ranked["score"],83.4,places=2)
  self.assertEqual(ranked["risk_snapshot"]["ranking_evidence"]["measured_evidence_items"],0)
  self.assertFalse(ranked["risk_snapshot"]["ranking_evidence"]["score_is_probability"])
 def test_real_liquidity_changes_score(self):
  c=dict(score=70.,option_type="CALL",risk_snapshot={})
  strong=rank_with_evidence(c,activity(contract_volume=800,open_interest=3500,
     historical_volume=[100,100,100,100,100]),
     {"relative_strength_pct_points":5})
  weak=rank_with_evidence(c,activity(contract_volume=5,open_interest=10,
     historical_volume=[100,100,100,100,100]),
     {"relative_strength_pct_points":-5})
  self.assertGreater(strong["score"],weak["score"])
  self.assertLessEqual(strong["score"],100)
 def test_bearish_sector_adjustment(self):
  c=dict(score=75.,option_type="PUT",risk_snapshot={})
  bearish=rank_with_evidence(c,sector_data={"relative_strength_pct_points":-4})
  bullish=rank_with_evidence(c,sector_data={"relative_strength_pct_points":4})
  self.assertGreater(bearish["score"],bullish["score"])
 def test_relative_strength_from_returns(self):
  rs=relative_strength("AAPL","XLK",100,105,100,102,as_of="2026-11-04")
  self.assertEqual(rs["relative_strength_pct_points"],3.)
  self.assertEqual(rs["as_of"],"2026-11-04")

if __name__=="__main__":unittest.main()
