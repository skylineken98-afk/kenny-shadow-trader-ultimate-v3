import unittest
from datetime import datetime, timedelta, timezone
from core.fvg_gap_backtest import signals, backtest, validate


def row(t, o, h, l, c):
    return dict(timestamp=t.isoformat(), open=o, high=h, low=l, close=c)


def fixture():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    context = [row(t, 116, 118, 114, 116), row(t+timedelta(hours=4), 110, 112, 100, 102),
               row(t+timedelta(hours=8), 102, 104, 100, 102)]
    start = t+timedelta(hours=12)
    bars = [row(start+timedelta(minutes=i), 100, 101, 99, 100) for i in range(30)]
    bars[20] = row(start+timedelta(minutes=20), 100, 101, 98, 100)
    bars[21] = row(start+timedelta(minutes=21), 100, 103, 99, 102)
    bars[22] = row(start+timedelta(minutes=22), 102, 110, 97, 105)
    return context, bars


class GapTests(unittest.TestCase):
    def test_next_open_and_stop_first(self):
        h, b = fixture()
        r = backtest(h, b)['records'][0]
        self.assertEqual(r['entry'], 102)
        self.assertEqual(r['reason'], 'stop')
        self.assertEqual(r['exit'], 98)
        self.assertGreater(r['entry_at'], r['sweep_at'])

    def test_prefix_invariance_and_context_availability(self):
        h, b = fixture()
        self.assertEqual(signals(h, b[:22]), signals(h, b))
        shifted = [dict(x, timestamp=(datetime.fromisoformat(x['timestamp'])+timedelta(days=1)).isoformat()) for x in h]
        self.assertEqual(signals(shifted, b), [])

    def test_bearish_mirror(self):
        h, b = fixture()
        def mirror(rows):
            return [dict(x, open=220-x['open'], high=220-x['low'], low=220-x['high'], close=220-x['close']) for x in rows]
        r = backtest(mirror(h), mirror(b))['records'][0]
        self.assertEqual(r['side'], -1)
        self.assertEqual(r['reason'], 'stop')

    def test_gap_open_rechecks_rr_and_costs(self):
        h, b = fixture()
        b[22].update(open=106, high=108, low=105, close=106)
        self.assertEqual(backtest(h, b)['trades'], 0)
        with self.assertRaises(ValueError):
            backtest(h, b, fee_bps=float('nan'))
        with self.assertRaises(ValueError):
            validate([b[0], b[0]], 1)


if __name__ == '__main__':
    unittest.main()
