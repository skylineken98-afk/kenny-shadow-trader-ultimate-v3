"""Opening-momentum SPX paper-trade decision rules. No broker access or scheduler.

Caller supplies completed 1m SPX bars, independently confirmed 1H/15m
trend/zone, and real timestamped option quotes. A decision is NOT a fill.
All clock times use America/New_York (DST-aware).
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import math

ET = ZoneInfo("America/New_York")
OPEN = time(9, 30)
FIRST_ENTRY = time(9, 32)
CUTOFF = time(10, 0)


def _clock(now):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return now.astimezone(ET)


def _valid_positive(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (ValueError, TypeError):
        return False


def opening_entry(now, *, bars, hourly_trend, zone_side, reward_risk,
                  current_positions=0, daily_loss_pct=0, fresh_quote=False):
    """Return direction and reason; never asserts a paper or broker fill.

    bars: >= 22 completed 1m candle dicts with high/low/close/volume/vwap.
    hourly_trend and zone_side: 'BULLISH' or 'BEARISH', calculated by
    independent completed 1H and 15m data producers.
    """
    now = _clock(now)
    if now.weekday() >= 5 or not FIRST_ENTRY <= now.time().replace(tzinfo=None) < CUTOFF:
        return {"action": "SKIP", "reason": "outside_0932_1000_ET"}
    if current_positions >= 3:
        return {"action": "SKIP", "reason": "max_positions"}
    if daily_loss_pct >= 10:
        return {"action": "SKIP", "reason": "daily_loss_limit"}
    if not fresh_quote:
        return {"action": "SKIP", "reason": "missing_fresh_option_quote"}
    if not _valid_positive(reward_risk) or float(reward_risk) < 1.5:
        return {"action": "SKIP", "reason": "insufficient_reward_risk"}
    if len(bars) < 22:
        return {"action": "SKIP", "reason": "insufficient_completed_bars"}
    recent = bars[-22:]
    for bar in recent:
        if not all(_valid_positive(bar.get(k)) for k in ("high", "low", "close", "vwap")):
            return {"action": "SKIP", "reason": "invalid_bar"}
        if not math.isfinite(float(bar.get("volume", -1))) or float(bar["volume"]) < 0:
            return {"action": "SKIP", "reason": "invalid_volume"}
        if float(bar["low"]) > float(bar["high"]):
            return {"action": "SKIP", "reason": "invalid_bar"}
    prior = recent[-2]
    curr = recent[-1]
    closes = [float(b["close"]) for b in recent]
    def ema(xs, n):
        a = 2 / (n + 1)
        value = sum(xs[:n]) / n
        for x in xs[n:]:
            value = a*x+(1-a)*value
        return value
    fast = ema(closes, 9)
    slow = ema(closes, 21)
    bullish = (hourly_trend == zone_side == "BULLISH"
               and fast > slow and closes[-1] > float(curr["vwap"])
               and closes[-1] > float(prior["high"]))
    bearish = (hourly_trend == zone_side == "BEARISH"
               and fast < slow and closes[-1] < float(curr["vwap"])
               and closes[-1] < float(prior["low"]))
    if bullish:
        return {"action": "ENTRY_CANDIDATE", "side": "CALL", "reason": "confirmed_bull_momentum"}
    if bearish:
        return {"action": "ENTRY_CANDIDATE", "side": "PUT", "reason": "confirmed_bear_momentum"}
    return {"action": "SKIP", "reason": "momentum_unconfirmed"}


def opening_exit(now, *, side, entry_ask, latest_bid, fast_ema, slow_ema,
                 underlying_close, vwap, last_1m_close, previous_1m_close):
    """Paper exit decision using BID; stale/missing data must not invent a fill.

    Exit instruction means caller must request a real fresh option quote and
    simulate an exit at its verified bid, recording the timestamp/spread.
    """
    now = _clock(now)
    if side not in ("CALL", "PUT"):
        raise ValueError("side must be CALL or PUT")
    if now.time().replace(tzinfo=None) >= CUTOFF:
        return {"action": "EXIT_REQUIRED", "reason": "1000_ET_hard_cutoff"}
    values = (entry_ask, latest_bid, fast_ema, slow_ema, underlying_close,
              vwap, last_1m_close, previous_1m_close)
    if not all(_valid_positive(x) for x in values):
        return {"action": "HOLD_REQUIRES_DATA", "reason": "invalid_or_missing_fresh_quote_or_bar"}
    if float(latest_bid) <= float(entry_ask) * 0.75:
        return {"action": "EXIT_REQUIRED", "reason": "premium_stop_25pct"}
    weakening = ((float(fast_ema) <= float(slow_ema) or
                  float(underlying_close) < float(vwap) or
                  float(last_1m_close) < float(previous_1m_close))
                 if side == "CALL" else
                 (float(fast_ema) >= float(slow_ema) or
                  float(underlying_close) > float(vwap) or
                  float(last_1m_close) > float(previous_1m_close)))
    if weakening:
        return {"action": "EXIT_REQUIRED", "reason": "momentum_weakening"}
    return {"action": "HOLD", "reason": "momentum_intact"}
