"""No live quotes or Robinhood connection required for market-chat tests."""
import unittest
from datetime import datetime,timezone,timedelta
from kst_chat.market_research import market_research

NOW=datetime(2026,11,5,19,40,tzinfo=timezone.utc)
def ts(mins):
    return (NOW-timedelta(minutes=mins)).isoformat()

class Store:
    def __init__(self):
        self.calls=[]
    def rows(self,table,**kwargs):
        self.calls.append((table,kwargs))
        if table=="kst_option_signals":
            return [
                dict(created_at=ts(1),underlying="IWM",contract="IWM-P",option_type="PUT",
                     score=94,context_label="BEARISH_SETUP_ALIGNED",feed="indicative",
                     quote_at=ts(2),entry_ask=4.2),
                dict(created_at=ts(3),underlying="IWM",contract="IWM-P",option_type="PUT",
                     score=93,context_label="BEARISH_SETUP_ALIGNED",feed="indicative",
                     quote_at=ts(3),entry_ask=4.1),
                dict(created_at=ts(1),underlying="SPY",contract="SPY-C",option_type="CALL",
                     score=99,context_label="COUNTER_TREND_RESEARCH",feed="indicative",
                     quote_at=ts(40),entry_ask=3.1)]
        if table=="ultimate_signals":
            return [dict(symbol="IWM",created_at=ts(1),status="SETUP",side="BEARISH",
                entry=271,stop=272,target=269,details={"frames":{
                    "4h":{"trend":"BEARISH","rvol":2.1},
                    "1h":{"trend":"BEARISH"},"5m":{"trend":"BEARISH"}}})]
        raise AssertionError("Unexpected table")

class MarketResearchTest(unittest.TestCase):
    def test_swing_filters_deduplicates_and_marks_quote(self):
        s=Store()
        context,sources=market_research(s,"best swing trades",NOW)
        candidates=context["contract_candidates"]
        self.assertEqual(len(candidates),2)
        self.assertEqual(candidates[0]["contract"],"IWM-P")
        self.assertEqual(candidates[0]["quote_status"],"RECENT_INDICATIVE")
        self.assertFalse(candidates[0]["broker_executable_quote_verified"])
        self.assertEqual(candidates[1]["quote_status"],"STALE")
        self.assertEqual(context["technical_setups"][0]["side"],"BEARISH")
        self.assertTrue(any(row["id"]=="KOPT1" for row in sources))
    def test_broad_recommendations_diversify_underlyings(self):
        class Broad(Store):
            def rows(self,table,**kwargs):
                if table=="kst_option_signals":
                    names=["IWM","IWM","IWM","IWM","IWM","NVDA","AAPL","XOM"]
                    return [dict(created_at=ts(i),underlying=name,
                        contract=name+"-"+str(i),option_type="PUT",score=99-i,
                        context_label="BEARISH_SETUP_ALIGNED",feed="indicative",
                        quote_at=ts(1),entry_ask=2) for i,name in enumerate(names)]
                return super().rows(table,**kwargs)
        context,_=market_research(Broad(),"best swing trades",NOW)
        names=[x["underlying"] for x in context["contract_candidates"][:4]]
        self.assertEqual(names,["IWM","NVDA","AAPL","XOM"])
        self.assertEqual(context["coverage"]["unique_option_underlyings"],4)
        self.assertFalse(context["coverage"]["quotes_are_volume_verified"])
    def test_explicit_symbol_filters(self):
        c,_=market_research(Store(),"Apple bullish swing idea",NOW)
        self.assertEqual(c["contract_candidates"],[])
    def test_no_trade_request_does_not_query(self):
        s=Store()
        self.assertEqual(market_research(s,"Good morning!",NOW),({},[]))
        self.assertFalse(s.calls)
    def test_failure_is_not_no_signal(self):
        class Broken:
            def rows(self,*a,**k):raise RuntimeError("provider down")
        c,_=market_research(Broken(),"best swing",NOW)
        self.assertEqual(c["contract_candidates"]["status"],"UNAVAILABLE")
        self.assertEqual(c["technical_setups"]["status"],"UNAVAILABLE")

if __name__=="__main__":unittest.main()
