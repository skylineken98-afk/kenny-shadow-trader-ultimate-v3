import unittest
from kst_options.universe import universe,diverse_choices,DEFAULT_SYMBOLS
from kst_options.engine import requested_choices

def c(ticker,score,kind="PUT",quality="QUALIFIED",context="BEARISH_SETUP_ALIGNED"):
    return dict(underlying=ticker,contract=ticker+"-"+str(score)+"-"+kind,
                score=score,quality_label=quality,context_label=context,
                category="Swings",entry_ask=1.5,option_type=kind)

class DiversificationTest(unittest.TestCase):
    def test_default_covers_multiple_sectors(self):
        self.assertIn("AAPL",DEFAULT_SYMBOLS)
        self.assertIn("XOM",DEFAULT_SYMBOLS)
        self.assertIn("JPM",DEFAULT_SYMBOLS)
        self.assertIn("LLY",DEFAULT_SYMBOLS)
        self.assertIn("IWM",DEFAULT_SYMBOLS)
        self.assertGreaterEqual(len(universe()),20)
    def test_env_validates_caps_dedup(self):
        self.assertEqual(universe(" aapl, AAPL, nVda, bad$",),["AAPL","NVDA"])
    def test_diverse_choices_prevent_one_ticker_domination(self):
        rows=[c("IWM",99),c("IWM",98),c("IWM",97),c("AAPL",91),c("XOM",90)]
        got=diverse_choices(rows)
        self.assertEqual([x["underlying"] for x in got],["IWM","AAPL","XOM"])
    def test_alignment_before_raw_score(self):
        rows=[c("IWM",99,context="COUNTER_TREND_RESEARCH"),c("NVDA",90)]
        self.assertEqual(diverse_choices(rows,1)[0]["underlying"],"NVDA")
    def test_sparse_scan_does_not_invent_tickers(self):
        got=diverse_choices([c("IWM",99),c("IWM",98)])
        self.assertEqual(len(got),2)
    def test_personal_requests_diversify_tickers(self):
        rows=[c("IWM",99),c("IWM",98),c("SPY",90),c("AAPL",87)]
        got=requested_choices(rows,"Swings",200)
        self.assertEqual({x["underlying"] for x in got},{"IWM","SPY","AAPL"})
    def test_budget_does_not_override_validation(self):
        rows=[c("IWM",99),c("AAPL",90)]
        self.assertEqual(requested_choices(rows,"Swings",30),[])

if __name__=="__main__":unittest.main()
