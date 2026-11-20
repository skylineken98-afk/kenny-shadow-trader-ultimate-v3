import pandas as pd
import pytest

from core.day_trader.replay import opening_replay


def candles():
    index = pd.date_range("2026-11-17 09:30", periods=30, freq="min", tz="America/New_York")
    frame = pd.DataFrame([[100, 100.10, 99.90, 100, 100]] * 30, index=index,
                         columns=["Open", "High", "Low", "Close", "Volume"], dtype=float)
    frame.iloc[1] = [100, 100.35, 100, 100.30, 200]
    frame.iloc[2] = [100.40, 101.10, 99.99, 100.10, 100]
    return frame


def test_enters_at_next_open_and_counts_ambiguous_bar_as_stop():
    result = opening_replay(candles(), "SPY")
    trade, = result["trades"]
    assert trade["entry_time"].startswith("2026-11-17T09:32")
    assert trade["entry"] == 100.40
    assert trade["outcome"] == "stop"
    assert trade["net_pct"] == pytest.approx(-0.40 / 100.40 * 100 - 0.04)
    assert result["simulation"] is None


def test_incomplete_opening_window_is_skipped():
    result = opening_replay(candles().drop(candles().index[12]), "SPY")
    assert result == {"sessions": 0, "trades": [], "simulation": None}
