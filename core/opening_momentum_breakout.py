"""Opening Momentum Reclaim & Breakout research strategy.

Completed, timezone-aware OHLCV bars only; paper plans, no broker actions.
Opening impulse + constrained pullback + close-confirmed volume breakout.
Signal decisions use no future bars, and underlying targets are NOT option prices.
"""
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from core.alpaca_option_quotes import OCC, QuoteError, validate_quote

ET = ZoneInfo("America/New_York")
STRATEGY_ID = "opening_momentum_reclaim_breakout_v1"


def _reject(reason):
    return {"status": "REJECTED", "execution": "NONE", "simulation_only": True,
            "strategy": STRATEGY_ID, "reason": reason}


def _parse(bars):
    if not isinstance(bars, list) or not 5 <= len(bars) <= 500:
        raise ValueError("Require 5-500 completed OHLCV bars")
    out = []
    for bar in bars:
        if not isinstance(bar, dict) or bar.get("complete") is not True:
            raise ValueError("Unconfirmed or malformed candle")
        dt = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00"))
        if dt.tzinfo is None or (out and dt <= out[-1]["t"]):
            raise ValueError("Candles require ordered timezone-aware timestamps")
        x = {k: float(bar[k]) for k in ("o", "h", "l", "c", "v")}
        if not all(math.isfinite(v) for v in x.values()):
            raise ValueError("Nonfinite candle")
        if not 0 < x["l"] <= min(x["o"], x["c"]) <= max(x["o"], x["c"]) <= x["h"] or x["v"] < 0:
            raise ValueError("Invalid OHLCV candle")
        out.append(dict(x, t=dt))
    return out


def detect(bars, *, min_relative_volume=1.30, max_retrace=0.60,
           min_impulse_pct=0.002, max_pullback_bars=6):
    """Detect breakout on last *completed* bar only, no multi-timeframe gate.

    Bars are expected to be consecutive session candles with the first candle
    at/after 09:30 ET. Requires exactly one opening impulse candle (first),
    2-6 pullback candles, then a confirmed breakout.
    """
    try:
        if not (1 <= float(min_relative_volume) <= 10 and 0 < float(max_retrace) < 1
                and 0 < float(min_impulse_pct) <= 0.1
                and isinstance(max_pullback_bars, int) and 2 <= max_pullback_bars <= 30):
            return _reject("Invalid strategy parameters")
        data = _parse(bars)
        if len(data) < 5 or len(data) > max_pullback_bars + 2:
            return _reject("Opening setup length outside allowed pullback window")
        local = [x["t"].astimezone(ET) for x in data]
        if len({t.date() for t in local}) != 1 or any(t.weekday() > 4 for t in local):
            return _reject("Bars must belong to one weekday session")
        if (local[0].hour, local[0].minute) != (9, 30):
            return _reject("Opening bar must start at 09:30 ET")
        if any(t.hour * 60 + t.minute < 570 or t.hour * 60 + t.minute >= 960 for t in local):
            return _reject("Outside regular session")
        if len({(local[i+1]-local[i]).total_seconds() for i in range(len(local)-1)}) != 1:
            return _reject("Inconsistent candle cadence")
        cadence = (local[1] - local[0]).total_seconds()
        if cadence <= 0 or cadence > 300:
            return _reject("Expected consistent 1-5 minute candles")
        if any((local[i+1]-local[i]).total_seconds() != cadence for i in range(len(local)-1)):
            return _reject("Missing candles")
        first, pull, last = data[0], data[1:-1], data[-1]
        if not 2 <= len(pull) <= max_pullback_bars:
            return _reject("Need 2-6 pullback candles")
        body_pct = abs(first["c"] / first["o"] - 1)
        if body_pct < min_impulse_pct:
            return _reject("Opening impulse too small")
        bullish = first["c"] > first["o"]
        direction = "BULLISH" if bullish else "BEARISH"
        opening_range = first["h"] - first["l"]
        if opening_range <= 0:
            return _reject("Zero opening range")
        if bullish:
            retracement = (first["h"] - min(x["l"] for x in pull)) / opening_range
            clean = all(x["c"] <= first["h"] for x in pull)
            breakout = last["c"] > first["h"] and last["c"] > last["o"]
            stop = min(x["l"] for x in pull)
            risk = last["c"] - stop
            target = last["c"] + 1.5 * risk
        else:
            retracement = (max(x["h"] for x in pull) - first["l"]) / opening_range
            clean = all(x["c"] >= first["l"] for x in pull)
            breakout = last["c"] < first["l"] and last["c"] < last["o"]
            stop = max(x["h"] for x in pull)
            risk = stop - last["c"]
            target = last["c"] - 1.5 * risk
        if retracement < 0 or retracement > max_retrace or not clean:
            return _reject("Pullback failed to hold opening structure")
        if not breakout or risk <= 0 or target <= 0:
            return _reject("Breakout not confirmed on candle close")
        baseline = sum(x["v"] for x in pull) / len(pull)
        if baseline <= 0 or last["v"] < baseline * float(min_relative_volume):
            return _reject("Breakout relative volume insufficient")
        # Reject weak closes near the wrong extreme (avoid wick-only triggers).
        candle_range = last["h"] - last["l"]
        if candle_range <= 0 or (last["c"]-last["l"])/candle_range < (0.65 if bullish else 0.0):
            if bullish:
                return _reject("Weak breakout close")
        if not bullish and (last["h"]-last["c"])/candle_range < 0.65:
            return _reject("Weak breakout close")
        return {"status": "PAPER_SIGNAL", "execution": "NONE", "simulation_only": True,
                "strategy": STRATEGY_ID, "direction": direction,
                "signal_timestamp": last["t"].isoformat(),
                "breakout_close": last["c"], "underlying_stop": stop,
                "underlying_target_1_5rr": target,
                "relative_volume": round(last["v"]/baseline, 4),
                "opening_retracement": round(retracement, 4),
                "note": "Underlying research levels, not option premium stops/targets"}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _reject(str(exc))


def paper_option_plan(underlying, bars, contract, quote, *, equity,
                      day_start_equity, open_cost=0, open_positions=0,
                      budget=100, now=None):
    """Read-only option candidate. Never places or simulates a filled order."""
    signal = detect(bars)
    if signal["status"] != "PAPER_SIGNAL":
        return signal
    try:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            return _reject("Timezone-aware clock required")
        stamp = datetime.fromisoformat(signal["signal_timestamp"])
        if not 0 <= (now - stamp).total_seconds() <= 120:
            return _reject("Stale underlying confirmation")
        local = now.astimezone(ET)
        if local.weekday() > 4 or not 570 <= local.hour*60+local.minute < 960:
            return _reject("Market closed")
        capital, start, reserved, cap = map(lambda v: Decimal(str(v)),
                                             (equity, day_start_equity, open_cost, budget))
        if not all(v.is_finite() for v in (capital, start, reserved, cap)):
            return _reject("Nonfinite risk input")
        if capital <= 0 or start <= 0 or reserved < 0 or cap <= 0:
            return _reject("Invalid account values")
        if capital <= start * Decimal(".90"):
            return _reject("10% daily loss guard")
        if type(open_positions) is not int or not 0 <= open_positions < 3:
            return _reject("Three-position paper limit")
        symbol = str(contract)
        if not OCC.fullmatch(symbol):
            return _reject("Invalid OCC symbol")
        root = symbol[:-15]
        if root not in ({underlying, underlying+"W"} if underlying == "SPX" else {underlying}):
            return _reject("Underlying/contract mismatch")
        if symbol[-9] != ("C" if signal["direction"] == "BULLISH" else "P"):
            return _reject("Wrong contract direction")
        if datetime.strptime(symbol[-15:-9], "%y%m%d").date() < local.date():
            return _reject("Expired option")
        q = validate_quote(symbol, quote, now=now)
        ask, bid = Decimal(q["ask"]), Decimal(q["bid"])
        cost = ask*100
        if cost > cap or cost > capital*Decimal(".10") or reserved+cost > capital:
            return _reject("Budget, 10% allocation or available-capital guard")
        return dict(signal, status="PAPER_CANDIDATE", contract=symbol,
                    underlying=underlying, option_ask=str(ask), option_bid=str(bid),
                    estimated_one_contract_cost=str(cost), quote_timestamp=q["quote_timestamp"],
                    premium_initial_stop=str((ask*Decimal(".75")).quantize(Decimal(".0001"))),
                    premium_first_actionable_target=str((ask*Decimal("1.40")).quantize(Decimal(".0001"))),
                    note="No fill. Use fresh bid-based mark/exit; underlying targets do not price options.")
    except (QuoteError, ValueError, TypeError, OverflowError, ArithmeticError) as exc:
        return _reject(str(exc))


def backtest(bars, *, holding_bars=5, fee_bps=5, slippage_bps=5):
    """Chronological next-bar-open underlying-only replay; no option P&L implied."""
    data = _parse(bars)
    vals = (holding_bars, fee_bps, slippage_bps)
    if type(holding_bars) is not int or not 1 <= holding_bars <= 50:
        raise ValueError("Invalid holding bars")
    if any(not math.isfinite(float(x)) or not 0 <= float(x) <= 500 for x in vals[1:]):
        raise ValueError("Invalid cost assumptions")
    records = []
    # Find contiguous 09:30 session sequences. Each day yields at most one signal.
    dates = sorted({x["t"].astimezone(ET).date() for x in data})
    for day in dates:
        session = [x for x in data if x["t"].astimezone(ET).date() == day]
        if not session or session[0]["t"].astimezone(ET).strftime("%H:%M") != "09:30":
            continue
        for j in range(5, min(len(session), 9)):
            sig = detect([dict(x, t=x["t"].isoformat(), complete=True) for x in session[:j]])
            if sig["status"] != "PAPER_SIGNAL":
                continue
            if j + holding_bars > len(session):
                break
            entry = session[j]["o"]
            exit_at = session[j+holding_bars-1]["c"]
            direction = 1 if sig["direction"] == "BULLISH" else -1
            gross = direction * (exit_at/entry - 1)
            net = gross - 2*(float(fee_bps)+float(slippage_bps))/10000
            records.append({"strategy": STRATEGY_ID, "decision_at":sig["signal_timestamp"],
                            "entry_at":session[j]["t"].isoformat(),
                            "exit_at":session[j+holding_bars-1]["t"].isoformat(),
                            "direction":sig["direction"], "entry":entry, "exit":exit_at,
                            "net_underlying_return":net, "relative_volume":sig["relative_volume"],
                            "simulation_only":True, "option_fill_verified":False})
            break
    returns = [r["net_underlying_return"] for r in records]
    return {"strategy":STRATEGY_ID, "status":"DESCRIPTIVE_SIMULATION",
            "trades":len(records), "win_rate":sum(x>0 for x in returns)/len(returns) if returns else None,
            "expectancy_underlying":sum(returns)/len(returns) if returns else None,
            "records":records, "research_only":True, "option_returns":False,
            "auto_promote":False,
            "assumptions":{"holding_bars":holding_bars,"fee_bps":fee_bps,
                           "slippage_bps":slippage_bps, "entry":"next bar open"}}


def append_performance(path, result, *, dataset_id, phase):
    """Append auditable JSONL snapshots; never invent fills or win rates."""
    if phase not in ("historical", "holdout", "paper") or not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("Valid phase and immutable dataset ID required")
    if result.get("strategy") != STRATEGY_ID:
        raise ValueError("Unexpected strategy")
    event = dict(result, dataset_id=dataset_id, phase=phase,
                 logged_at=datetime.now(timezone.utc).isoformat())
    with Path(path).open("a",encoding="utf-8") as fh:
        fh.write(json.dumps(event, allow_nan=False, sort_keys=True)+"\n")
