import unittest
from datetime import datetime, timezone
from kst_options.universe import scan_symbols,priority_index_symbols
from kst_options.market_pulse import classify_snapshots, tracked_symbols, SECTOR_ETFS

NOW=datetime(2026,11,5,15,0,tzinfo=timezone.utc)
def snapshot(price,prev,volume=1000):
    return {"latestTrade":{"p":price,"t":"2026-11-05T14:59:30Z"},
            "dailyBar":{"c":price,"v":volume,"t":"2026-11-05T14:58:00Z"},
            "prevDailyBar":{"c":prev,"v":2500}}
class SPXPriorityMarketPulseTests(unittest.TestCase):
    def test_priority_spx_nonrotating_and_disable_switch(self):
        self.assertEqual(priority_index_symbols("true"),["SPX"])
        self.assertEqual(priority_index_symbols("false"),[])
        self.assertEqual(scan_symbols(["AAPL","SPY","SPX"],["SPX"]),["SPX","AAPL","SPY"])
    def test_sector_coverage_not_just_tech(self):
        self.assertTrue(set(SECTOR_ETFS).issubset(set(tracked_symbols(""))))
    def test_bull_bear_and_sector_relative_strength(self):
        report=classify_snapshots({"SPY":snapshot(102,100),"XLK":snapshot(110,100),
                                  "XLE":snapshot(96,100),"AAPL":snapshot(120,100),
                                  "NVDA":snapshot(90,100)},NOW,["SPY","XLK","XLE","AAPL","NVDA"])
        self.assertEqual(report["biggest_bulls"][0]["symbol"],"AAPL")
        self.assertEqual(report["biggest_bears"][0]["symbol"],"NVDA")
        self.assertEqual(report["sector_leaders"][0]["vs_spy_percentage_points"],8)
        self.assertIsNone(report["institutional_net_flows"])
        self.assertEqual(report["market_drivers"]["status"],"UNVERIFIED")
    def test_stale_and_broken_quotes_do_not_claim_leadership(self):
        old=snapshot(200,100);old["latestTrade"]["t"]="2026-11-05T13:30:00Z"
        report=classify_snapshots({"SPY":old,"AAPL":snapshot(0,100)},NOW,["SPY","AAPL"])
        self.assertEqual(report["coverage"]["valid"],0)
        self.assertEqual(report["biggest_bulls"],[])
if __name__=="__main__":unittest.main()
