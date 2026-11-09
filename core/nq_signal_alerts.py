"""Read-only NQ/MNQ momentum alert engine. No broker integration or order methods."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SYMBOLS = {"NQ", "MNQ"}

@dataclass(frozen=True)
class Bar:
    timestamp: datetime  # UTC-aware BAR OPEN timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass(frozen=True)
class Signal:
    id: str
    symbol: str
    direction: str
    grade: str
    setup: str
    decision_at: str
    entry_trigger: float
    stop: float
    target: float
    rr: float
    relative_volume: float
    vwap: float
    data_asof: str
    status: str = "SIGNAL_ONLY_NOT_EXECUTED"

def parse_bars(raw):
    bars = []
    for item in raw:
        t = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00"))
        if t.tzinfo is None:
            raise ValueError("Timestamps must include UTC offset")
        t = t.astimezone(timezone.utc)
        vals = [float(item[k]) for k in ("open", "high", "low", "close", "volume")]
        o, h, l, c, v = vals
        if not all(math.isfinite(n) for n in vals) or min(o, h, l, c) <= 0 or v < 0:
            raise ValueError("Non-finite, nonpositive price or negative volume")
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("Invalid OHLC geometry")
        if bars and t != bars[-1].timestamp + timedelta(minutes=1):
            raise ValueError("Expected contiguous unique one-minute bars")
        bars.append(Bar(t, o, h, l, c, v))
    return bars

def market_session_open(now):
    """Approximate CME equity-index hours; holidays/early closes need licensed calendar."""
    local = now.astimezone(NY)
    day, hour = local.weekday(), local.hour + local.minute / 60
    if day == 5 or (day == 4 and hour >= 17) or (day == 6 and hour < 18):
        return False
    return not (17 <= hour < 18)

def _ema(prices, period):
    value = prices[0]
    alpha = 2 / (period + 1)
    for price in prices[1:]:
        value = alpha * price + (1 - alpha) * value
    return value

def evaluate(symbol, raw_bars, now=None, max_stale_seconds=90, min_rr=1.5):
    if symbol not in SYMBOLS:
        raise ValueError("Only NQ and MNQ are supported")
    if max_stale_seconds <= 0 or min_rr < 1.5 or not math.isfinite(min_rr):
        raise ValueError("Invalid alert parameters")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not market_session_open(now):
        return None
    bars = parse_bars(raw_bars)
    if len(bars) < 75:
        return None
    last = bars[-1]
    asof = last.timestamp + timedelta(minutes=1)
    age = (now - asof).total_seconds()
    if age < 0 or age > max_stale_seconds:
        return None  # no forming-bar signals or stale alerting
    # Require all context bars to exist and be completed. No future candles.
    window = bars[-75:]
    # Session VWAP reset at 18:00 New York, not a lifetime rolling VWAP.
    def session_key(b):
        local = b.timestamp.astimezone(NY)
        return (local - timedelta(hours=18)).date() if local.hour < 18 else local.date()
    key = session_key(last)
    session = [b for b in bars if session_key(b) == key]
    volume = sum(b.volume for b in session)
    if volume <= 0 or len(session) < 20:
        return None
    vwap = sum(((b.high + b.low + b.close) / 3) * b.volume for b in session) / volume
    previous = window[-21:-1]
    avg_volume = sum(b.volume for b in previous) / len(previous)
    if avg_volume <= 0 or last.volume < avg_volume * 1.2:
        return None
    high, low = max(b.high for b in previous), min(b.low for b in previous)
    closes = [b.close for b in window]
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    bullish = last.close > high and last.close > vwap and ema20 > ema50
    bearish = last.close < low and last.close < vwap and ema20 < ema50
    if not (bullish or bearish):
        return None
    direction = "LONG" if bullish else "SHORT"
    entry = last.close  # alert threshold, NOT a simulated fill
    stop = min(b.low for b in window[-6:]) if bullish else max(b.high for b in window[-6:])
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target = entry + min_rr * risk if bullish else entry - min_rr * risk
    if target <= 0:
        return None
    # Grade is a deterministic heuristic, not a calibrated win probability.
    rv = last.volume / avg_volume
    grade = "A" if rv >= 1.8 and abs(entry - vwap) > risk * 0.25 else "B"
    timestamp = asof.isoformat()
    digest = hashlib.sha256(f"{symbol}|{direction}|{timestamp}|momentum_breakout_v1".encode()).hexdigest()[:24]
    return Signal(digest, symbol, direction, grade, "momentum_breakout_v1",
                  timestamp, entry, stop, target, min_rr, round(rv, 3),
                  round(vwap, 4), timestamp)

def signal_payload(signal):
    return asdict(signal)

def signal_message(signal):
    return (f"KST {signal.symbol} {signal.direction} | Grade {signal.grade}\n"
            f"Setup: {signal.setup}\n"
            f"Trigger (not fill): {signal.entry_trigger:.2f}\n"
            f"Stop: {signal.stop:.2f} | Target: {signal.target:.2f} | RR: {signal.rr:.2f}\n"
            f"RVOL: {signal.relative_volume:.2f} | VWAP: {signal.vwap:.2f}\n"
            f"Bar closed: {signal.data_asof}\n"
            "RESEARCH ALERT ONLY — manually verify live quotes; no orders placed.")
