"""Evidence-gated intraday institutional selling pressure monitor.

Price/volume proxies CANNOT identify involuntary hedge-fund liquidations.
No direct execution, no autonomous order modifications.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

ET = ZoneInfo("America/New_York")
SYMBOLS = ("SPY", "QQQ", "XLK")


def evaluate(frames, now=None):
    """Evaluate fetched 5m bars; require fresh, COMPLETED market-hours bars."""
    import pandas as pd
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = now.astimezone(ET)
    result = {
        "status": "UNAVAILABLE", "forced_liquidation_confirmed": False,
        "evidence_class": "MARKET_PROXY_ONLY",
        "as_of": now.isoformat(), "symbols": {},
        "warning": "Market candles do not establish margin calls or forced hedge-fund liquidation.",
        "trade_action": "NONE",
    }
    if local_now.weekday() >= 5 or not (9 <= local_now.hour <= 16):
        result["reason"] = "outside regular market monitoring window"
        return result
    for symbol in SYMBOLS:
        df = frames.get(symbol)
        if df is None or df.empty or not {"Open", "Close", "Volume"}.issubset(df.columns):
            result["reason"] = f"missing {symbol} candles"
            return result
        idx = pd.to_datetime(df.index)
        if idx.tz is None:
            result["reason"] = f"{symbol} timestamps must be timezone-aware"
            return result
        idx = idx.tz_convert(ET)
        df = df.copy()
        df.index = idx
        df = df.sort_index()
        # yfinance intraday timestamps mark bar OPEN; exclude active candle.
        cutoff = local_now - pd.Timedelta(minutes=5)
        df = df[(df.index.date == local_now.date()) &
                (df.index.time >= datetime.strptime("09:30", "%H:%M").time()) &
                (df.index.time < datetime.strptime("16:00", "%H:%M").time()) &
                (df.index <= cutoff)]
        if len(df) < 3 or (local_now - df.index[-1]).total_seconds() > 20 * 60:
            result["reason"] = f"{symbol} does not have three fresh completed bars"
            return result
        try:
            start, end = float(df["Open"].iloc[0]), float(df["Close"].iloc[-1])
            volume = float(df["Volume"].sum())
            if not all(math.isfinite(v) for v in (start, end, volume)) or start <= 0 or end <= 0 or volume < 0:
                raise ValueError("nonfinite/invalid candle values")
            change = round((end / start - 1.0) * 100, 3)
            result["symbols"][symbol] = {
                "session_change_pct": change,
                "last_completed_bar": df.index[-1].isoformat(),
            }
        except (ValueError, TypeError, OverflowError):
            result["reason"] = f"invalid {symbol} price/volume data"
            return result
    spy = result["symbols"]["SPY"]["session_change_pct"]
    qqq = result["symbols"]["QQQ"]["session_change_pct"]
    xlk = result["symbols"]["XLK"]["session_change_pct"]
    # Conservative warning thresholds, NOT a statistical liquidation classifier.
    if spy <= -2.0 and qqq <= -2.5 and xlk <= -2.5:
        result["status"] = "HIGH_SELLING_PRESSURE"
    elif spy <= -1.0 and (qqq <= -1.5 or xlk <= -1.5):
        result["status"] = "ELEVATED_SELLING_PRESSURE"
    else:
        result["status"] = "NO_BROAD_STRESS_SIGNAL"
    result["reason"] = "intraday ETF price proxies; not verified institutional flow"
    return result


def snapshot(load=None, now=None):
    """Read-only one-shot fetch; failure is explicit, never interpreted as calm."""
    if load is None:
        from core.market import history
        load = history
    frames = {}
    for sym in SYMBOLS:
        try:
            frames[sym] = load(sym, period="1d", interval="5m")
        except Exception:
            frames[sym] = None
    return evaluate(frames, now=now)
