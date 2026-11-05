from datetime import datetime, timedelta, timezone
import pandas as pd
from core.sector_rotation import SECTORS, screen_sector_data

def _candles(price=100, negative=False):
    days = pd.bdate_range(end="2026-11-04", periods=45)
    values = [price * (1 + (-0.002 if negative else 0.002) * i) for i in range(45)]
    return pd.DataFrame({"Open": values, "Close": values,
                         "High": [p*1.01 for p in values],
                         "Low": [p*.99 for p in values],
                         "Volume": [1000000]*45}, index=days)

def test_sector_ranking_and_provenance():
    now = datetime(2026, 11, 5, 15, tzinfo=timezone.utc)
    def load(symbol, **kwargs):
        return _candles(negative=symbol=="XLK")
    rows, notices = screen_sector_data(load=load, now=now)
    assert len(rows) == len(SECTORS)
    assert rows[-1]["ETF"] == "XLK"
    assert all(r["As of (session)"] == "2026-11-04" for r in rows)
    assert all("vs SPY 20d (pp)" in r for r in rows)
    assert not notices

def test_missing_data_is_not_replaced():
    def load(symbol, **kwargs):
        if symbol=="XLV": return pd.DataFrame()
        return _candles()
    rows, notices = screen_sector_data(load=load, now=datetime(2026,11,5,15,tzinfo=timezone.utc))
    assert not any(r["ETF"]=="XLV" for r in rows)
    assert any("XLV" in n for n in notices)

def test_benchmark_absence_suppresses_ranking():
    def load(symbol, **kwargs):
        return pd.DataFrame() if symbol=="SPY" else _candles()
    rows, notices = screen_sector_data(load=load, now=datetime(2026,11,5,15,tzinfo=timezone.utc))
    assert not rows
    assert "benchmark unavailable" in notices[0]
