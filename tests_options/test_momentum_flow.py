import unittest
from datetime import datetime
from kst_options.momentum import momentum_decision
from kst_options.strike_volume import strike_activity
from kst_options.darkpool import delayed_ats_report

def candles():
    c=[]
    for i in range(8):
        close=100+i*.05
        c.append({"t":f"2026-11-05T14:{30+i:02d}:00Z","c":close,
                  "h":close+.10,"l":close-.10,
                  "v":100 if i<5 else 500,"complete":True})
    c[-1]["c"]=102.0;c[-1]["h"]=102.1
    return c

class FlowAndMomentumTests(unittest.TestCase):
    def test_breakout_research_is_never_an_execution(self):
        r=momentum_decision("SPY",candles())
        self.assertEqual(r["action"],"PAPER_CANDIDATE")
        self.assertEqual(r["direction"],"BULLISH")
        self.assertEqual(r["execution"],"NONE")
    def test_open_candle_no_trade(self):
        data=candles();data[-1]["complete"]=False
        self.assertEqual(momentum_decision("SPY",data)["action"],"NO_TRADE")
    def test_strike_volume_only_current_session(self):
        cs=["SPXW261105C06000000","SPXW261105P06000000","AAPL261106C00250000"]
        observations={cs[0]:{"volume":250,"current_session":True},
                      cs[1]:{"volume":300,"current_session":True},
                      cs[2]:{"volume":100000,"current_session":False}}
        r=strike_activity(cs,observations)
        self.assertEqual(r["highest_volume_strikes"][0]["combined_volume"],550)
        self.assertEqual(r["highest_volume_strikes"][0]["strike"],6000)
        self.assertEqual(r["highest_volume_strikes"][0]["net_buying_pressure"],"UNKNOWN")
        self.assertEqual(r["coverage"]["contracts_with_verified_session_volume"],2)
    def test_darkpool_requires_official_delayed_source(self):
        rows=[{"symbol":"AAPL","shares":1000,"trades":10,"week_ending":"2026-10-16"}]
        self.assertEqual(delayed_ats_report(rows,source_url="https://wrong.site/",published_at="2026-11-05")["status"],"UNAVAILABLE")
        result=delayed_ats_report(rows,source_url="https://www.finra.org/finra-data/browse-catalog/alternative-trading-system-ats-transparency-data",published_at="2026-11-05")
        self.assertEqual(result["status"],"HISTORICAL_DELAYED")
        self.assertEqual(result["rows"][0]["shares"],1000)
if __name__=="__main__": unittest.main()
