import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.nq_signal_alerts import evaluate, market_session_open, parse_bars
from core.nq_signal_worker import enqueue, init_db, run_once, deliver

def sample(now, direction="LONG", stale=False):
    # Synthetic continuous 1m bars. No claims about market performance.
    end = now - timedelta(minutes=2 if stale else 1)
    start = end - timedelta(minutes=79)
    rows = []
    for i in range(80):
        p = (100 + i * 0.1) if direction == "LONG" else (200 - i * 0.1)
        rows.append(dict(timestamp=(start + timedelta(minutes=i)).isoformat(),
                         open=p, high=p + 0.2, low=p - 0.2,
                         close=p + (0.1 if direction == "LONG" else -0.1), volume=100))
    rows[-1]["volume"] = 500
    rows[-1]["close"] = 112 if direction == "LONG" else 188
    rows[-1]["high"] = max(rows[-1]["high"], rows[-1]["close"] + 0.2)
    rows[-1]["low"] = min(rows[-1]["low"], rows[-1]["close"] - 0.2)
    return rows

class NQAlertsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 15, 1, tzinfo=timezone.utc)
    def test_long_and_short_and_symbols(self):
        for direction in ("LONG", "SHORT"):
            for symbol in ("NQ", "MNQ"):
                with self.subTest(direction=direction, symbol=symbol):
                    result = evaluate(symbol, sample(self.now, direction), now=self.now)
                    self.assertIsNotNone(result)
                    self.assertEqual(result.direction, direction)
                    self.assertEqual(result.status, "SIGNAL_ONLY_NOT_EXECUTED")
                    self.assertGreaterEqual(result.rr, 1.5)
    def test_stale_and_forming_bars_suppressed(self):
        self.assertIsNone(evaluate("NQ", sample(self.now, stale=True), now=self.now))
        future = sample(self.now)
        future[-1]["timestamp"] = (self.now + timedelta(minutes=1)).isoformat()
        with self.assertRaises(ValueError):
            parse_bars(future)
    def test_gaps_and_invalid_ohlc_rejected(self):
        rows = sample(self.now)
        rows[10]["timestamp"] = (datetime.fromisoformat(rows[10]["timestamp"])+timedelta(minutes=1)).isoformat()
        with self.assertRaises(ValueError):
            parse_bars(rows)
        rows = sample(self.now)
        rows[3]["high"] = 0
        with self.assertRaises(ValueError):
            evaluate("NQ", rows, now=self.now)
    def test_closed_market_and_no_future(self):
        self.assertFalse(market_session_open(datetime(2026, 11, 7, 15, tzinfo=timezone.utc)))
        self.assertIsNone(evaluate("NQ", sample(self.now), now=datetime(2026, 11, 7, 15, tzinfo=timezone.utc)))
    def test_deterministic_and_outbox_dedup(self):
        a = evaluate("NQ", sample(self.now), now=self.now)
        b = evaluate("NQ", sample(self.now), now=self.now)
        self.assertEqual(a.id, b.id)
        with sqlite3.connect(":memory:") as db:
            init_db(db)
            enqueue(db, a, ("telegram", "website"))
            enqueue(db, a, ("telegram", "website"))
            self.assertEqual(db.execute("SELECT count(*) FROM nq_alert_outbox").fetchone()[0], 2)
            deliver(db)  # absent credentials => queue stays pending
            self.assertEqual(db.execute("SELECT count(*) FROM nq_alert_outbox WHERE sent=1").fetchone()[0], 0)
    def test_no_live_data_returns_no_alert(self):
        with sqlite3.connect(":memory:") as db:
            init_db(db)
            self.assertEqual(run_once(db, {}, self.now)["status"], "NO_LIVE_FEED")
    def test_provider_rejection_suppresses_alert(self):
        with sqlite3.connect(":memory:") as db:
            init_db(db)
            with patch("core.nq_signal_worker.fetch_bars", side_effect=ValueError("bad provider")):
                self.assertEqual(run_once(db, {"KST_NQ_DATA_URL": "https://example.invalid"}, self.now)["alerts"], 0)
                self.assertEqual(db.execute("SELECT count(*) FROM nq_alert_outbox").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
