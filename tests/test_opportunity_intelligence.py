import unittest
from core.opportunity_intelligence import score_opportunity, rank_opportunities

class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.call={'ticker':'ABC','contract':'ABC260101C00005000','right':'CALL','direction':'BULLISH','category':'Swings','base_contract_score':70,'cost':45}
        self.put={'ticker':'XYZ','contract':'XYZ260101P00005000','right':'PUT','direction':'BEARISH','category':'Swings','base_contract_score':60,'cost':20}
    def test_missing_data_does_not_create_inflow(self):
        result=score_opportunity(self.call)
        self.assertEqual(result['score'],59.5)
        self.assertFalse(result['evidence'])
        self.assertFalse(result['executable'])
    def test_direction_mismatch_rejected(self):
        with self.assertRaises(ValueError): score_opportunity({**self.call,'right':'PUT'})
    def test_bullish_and_bearish_ranking(self):
        ranked=rank_opportunities([self.call,self.put], {'ABC':{'flow':{'direction':'BULLISH','relative_volume':3.2,'chaikin_money_flow':.2}}})
        self.assertEqual(len(ranked['top_calls']),1)
        self.assertEqual(len(ranked['top_puts']),1)
        self.assertTrue(any(x['kind']=='ohlcv_pressure' for x in ranked['top_calls'][0]['evidence']))
    def test_invalid_valuation_does_not_boost(self):
        score=score_opportunity(self.call,fundamentals={'estimated_fair_value':100,'market_price':10})
        self.assertEqual(score['score'],59.5)
    def test_short_interest_not_directional(self):
        score=score_opportunity(self.put,finra={'short_interest_pct_float':25,'as_of':'2026-10-01','source':'FINRA'})
        self.assertEqual(score['score'],51)
        self.assertEqual(score['evidence'][0]['points'],0)
    def test_valuation_directionality(self):
        facts={'estimated_fair_value':70,'market_price':100,'method':'scenario model','as_of':'2026-10-01'}
        self.assertGreater(score_opportunity(self.put,fundamentals=facts)['score'],51)
        self.assertEqual(score_opportunity(self.call,fundamentals=facts)['score'],59.5)

if __name__=='__main__':unittest.main()
