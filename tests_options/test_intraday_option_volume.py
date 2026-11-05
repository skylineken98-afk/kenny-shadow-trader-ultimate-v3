import unittest
from datetime import datetime,timezone
from kst_options.provider import Provider
from kst_options.universe import enrichment_shortlist

class OptionVolumeTest(unittest.TestCase):
 def test_dated_intraday_bars_match_clock_and_do_not_include_future(self):
  p=Provider.__new__(Provider);p.feed="indicative";calls=[]
  def fake_get(path,params):
   calls.append((path,dict(params)))
   return {"bars":{"AAPL261113C00350000":[
      {"t":"2026-11-02T14:30:00Z","v":20},
      {"t":"2026-11-02T20:30:00Z","v":999},
      {"t":"2026-11-03T14:30:00Z","v":22},
      {"t":"2026-11-03T20:30:00Z","v":999},
      {"t":"2026-11-04T14:30:00Z","v":24},
      {"t":"2026-11-04T20:30:00Z","v":999},
      {"t":"2026-11-05T14:30:00Z","v":40},
      {"t":"2026-11-05T20:30:00Z","v":999}]},"next_page_token":None}
  p.get=fake_get
  row=p.daily_volumes(["AAPL261113C00350000"],
           datetime(2026,11,5,20,0,tzinfo=timezone.utc))["AAPL261113C00350000"]
  self.assertEqual(row["volume"],40)
  self.assertEqual(row["historical_volume"],[20,22,24])
  self.assertTrue(row["delayed"])
  self.assertEqual(calls[0][1]["timeframe"],"1Hour")
  self.assertEqual(calls[0][1]["end"],"2026-11-05T19:40:00+00:00")
 def test_affordable_published_contracts_are_enrichment_priority(self):
  def c(sym,score,ask,cat):
   return {"underlying":sym,"contract":sym+str(score)+cat,"category":cat,
           "entry_ask":ask,"score":score,"quality_label":"QUALIFIED",
           "context_label":"BEARISH_SETUP_ALIGNED"}
  rows=[c("IWM",99,20.0,"Swings"),
        c("IWM",90,1.0,"Swings"),
        c("XOM",87,1.5,"Swings"),
        c("AAPL",80,2.0,"Swings"),
        c("AAPL",99,30.0,"Swings")]
  picked=enrichment_shortlist(rows,limit=8)
  self.assertEqual(len({r["contract"] for r in picked}),len(picked))
  self.assertIn("IWM90Swings",[x["contract"] for x in picked])
  self.assertIn("XOM87Swings",[x["contract"] for x in picked])
  self.assertLessEqual(len(picked),8)

if __name__=="__main__":unittest.main()
