from datetime import datetime
from zoneinfo import ZoneInfo
import unittest

import pandas as pd
from core.institutional_stress import evaluate

ET = ZoneInfo("America/New_York")


def bars(start, end):
    index = pd.date_range("2026-11-05 09:30", periods=4, freq="5min", tz=ET)
    return pd.DataFrame({"Open": [start]*4, "Close":[start,start,start,end], "Volume":[1000]*4}, index=index)


class StressTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 5, 9, 51, tzinfo=ET)

    def test_high_stress_not_forced(self):
        data = {"SPY":bars(100,97.8),"QQQ":bars(100,97),"XLK":bars(100,97)}
        r = evaluate(data, self.now)
        self.assertEqual(r["status"],"HIGH_SELLING_PRESSURE")
        self.assertFalse(r["forced_liquidation_confirmed"])
        self.assertEqual(r["trade_action"], "NONE")

    def test_stale_is_unavailable(self):
        r = evaluate({"SPY":bars(100,98),"QQQ":bars(100,97),"XLK":bars(100,97)},
                     datetime(2026,11,5,12,30,tzinfo=ET))
        self.assertEqual(r["status"],"UNAVAILABLE")

    def test_missing_is_unavailable(self):
        self.assertEqual(evaluate({}, self.now)["status"],"UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
