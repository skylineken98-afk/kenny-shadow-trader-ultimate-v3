"""Fail-closed, research-only momentum scalper planner.

Produces no broker orders and no paper fills. Only completed underlying candles
and fresh, contract-specific OPRA quotes can yield an eligible paper candidate.
A separate approved, durable paper executor must apply the plan.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from core.alpaca_option_quotes import OCC, QuoteError, validate_quote

ET = ZoneInfo("America/New_York")
TARGET_PCTS = (Decimal(".30"), Decimal(".40"), Decimal(".50"),
               Decimal(".75"), Decimal("1.00"))


def _confirmed_momentum(underlying, bars):
    """Follow price/volume impulse without a 1H/15m/5m alignment requirement.

    Works with any consistent cadence of completed OHLCV bars. Requires at
    least two completed bars, a close through the prior high/low, directional
    change and expanding volume. Never calls this a predictive probability.
    """
    if not isinstance(bars, list) or len(bars) < 2:
        return _reject("At least two completed candles required")
    recent = bars[-8:]
    values = []
    try:
        for bar in recent:
            if bar.get("complete") is not True:
                return _reject("Unconfirmed candle")
            stamp = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00"))
            if stamp.tzinfo is None or (values and stamp <= values[-1][0]):
                return _reject("Unsorted or timezone-naive candles")
            c, h, l, v = map(_d, (bar["c"], bar["h"], bar["l"], bar["v"]))
            if not 0 < l <= c <= h or v < 0:
                return _reject("Invalid underlying OHLCV")
            values.append((stamp, c, h, l, v))
    except (TypeError, ValueError, KeyError, InvalidOperation):
        return _reject("Invalid underlying OHLCV")
    previous, current = values[-2:]
    baseline = sum(row[4] for row in values[:-1]) / (len(values) - 1)
    if baseline <= 0 or current[4] < baseline * Decimal("1.20"):
        return _reject("Momentum volume expansion not confirmed")
    move = (current[1] - previous[1]) / previous[1]
    if move >= Decimal(".0015") and current[1] > previous[2]:
        direction = "BULLISH"
    elif move <= Decimal("-.0015") and current[1] < previous[3]:
        direction = "BEARISH"
    else:
        return _reject("No confirmed directional momentum impulse")
    return {
        "status": "PAPER_CANDIDATE",
        "direction": direction,
        "observed_at": current[0].isoformat(),
        "volume_expansion_proxy": str((current[4] / baseline).quantize(Decimal(".01"))),
        "method": "completed-candle price breakout and expanding volume; no fixed candle timeframe",
    }


def _d(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("non-finite")
        return result
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError("invalid numeric risk input")


def _reject(reason, **info):
    return {"status": "REJECTED", "execution": "NONE",
            "simulation_only": True, "reason": reason, **info}


def plan_momentum_scalp(underlying, bars, contract, quote, *,
                        equity, day_start_equity, open_cost=0, open_positions=0,
                        budget=100, now=None, max_age_seconds=60):
    """Review a single-long-call/put scalp whenever confirmed momentum develops.

    Bars: chronological, completed *underlying* candles at a consistent
    data cadence; no mandated multi-timeframe consensus. quote: actual option
    bid/ask/timestamp, not index/ETF price.
    Budget is the premium cap for one standard 100-share option contract.
    """
    try:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            return _reject("Timezone-aware clock required")
        local = now.astimezone(ET)
        # No 9:32 entry rule, opening-only cutoff, or mandatory alignment.
        # Keep ordinary market hours as an execution-data safety boundary.
        minutes = local.hour * 60 + local.minute
        if local.weekday() > 4 or not 570 <= minutes < 960:
            return _reject("Outside regular US equity option market hours")
        capital, start, reserved, cap = map(_d, (equity, day_start_equity, open_cost, budget))
        if capital <= 0 or start <= 0 or reserved < 0 or cap <= 0:
            return _reject("Invalid account or budget")
        if capital <= start * Decimal(".90"):
            return _reject("10% daily loss guard")
        if not isinstance(open_positions, int) or isinstance(open_positions, bool) or open_positions >= 3 or open_positions < 0:
            return _reject("Maximum three concurrent paper positions")
        signal = _confirmed_momentum(underlying, bars)
        if signal["status"] != "PAPER_CANDIDATE":
            return signal
        # Fail closed if the underlying chart is no longer current.
        observed = datetime.fromisoformat(signal["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 120:
            return _reject("Stale or future-dated underlying candle")
        symbol = str(contract)
        if not OCC.fullmatch(symbol):
            return _reject("Invalid option OCC contract")
        right = symbol[-9]
        if (signal["direction"] == "BULLISH" and right != "C"
                or signal["direction"] == "BEARISH" and right != "P"):
            return _reject("Option right disagrees with confirmed direction")
        # Never allow wrong underlyings, stale expirations or near-expired
        # unquoted instruments to pass contract selection.
        root = symbol[:-15]
        if root not in ({underlying, underlying + "W"} if underlying == "SPX" else {underlying}):
            return _reject("Contract and underlying mismatch")
        expiry = datetime.strptime(symbol[-15:-9], "%y%m%d").date()
        if expiry < local.date():
            return _reject("Expired option")
        valid = validate_quote(symbol, quote, now=now, max_age_seconds=max_age_seconds)
        ask, bid = _d(valid["ask"]), _d(valid["bid"])
        total = ask * 100
        if total > cap:
            return _reject("Contract exceeds selected budget", premium_cost=str(total))
        if total > capital * Decimal(".10"):
            return _reject("10% per-trade allocation cap", premium_cost=str(total))
        if reserved + total > capital:
            return _reject("Insufficient unreserved paper capital")
        stop = (ask * Decimal(".75")).quantize(Decimal(".0001"))
        # +40% first executable target satisfies >= 1.5 reward/risk
        # relative to the 25% initial premium stop; +30% is a milestone.
        first_target = (ask * Decimal("1.40")).quantize(Decimal(".0001"))
        rr = (first_target - ask) / (ask - stop)
        if rr < Decimal("1.5"):
            return _reject("Reward/risk threshold not met")
        return {
            "status": "PAPER_CANDIDATE", "execution": "NONE",
            "simulation_only": True, "underlying": underlying,
            "contract": symbol, "direction": signal["direction"],
            "side": "BUY_TO_OPEN", "premium_ask": str(ask),
            "premium_bid": str(bid), "estimated_contract_cost": str(total),
            "initial_stop_premium": str(stop),
            "first_actionable_target_premium": str(first_target),
            "minimum_reward_risk": str(rr.quantize(Decimal(".01"))),
            "profit_milestones_pct": [30, 40, 50, 75, 100],
            "quote_timestamp": valid["quote_timestamp"],
            "signal_timestamp": signal["observed_at"],
            "momentum_method": signal["method"],
            "volume_expansion_proxy": signal["volume_expansion_proxy"],
            "data_note": "Option quote, not executed fill; volume signal is candle-derived, not order flow",
            "next_step": "Durable, separately enabled paper executor with bid-based exits and audit ledger",
        }
    except (QuoteError, ValueError, TypeError, OverflowError) as exc:
        return _reject(str(exc))


def evaluate_scalp_exit(entry_ask, current_bid, *, peak_bid, momentum_confirmed,
                        position_open=True):
    """Advisory EXIT/HOLD on a verified bid; caller must validate quote freshness.

    Never assume a target fills at the touch. Trailing stop ratchets upward
    from the original -25% as peak executable bid reaches milestone levels.
    """
    try:
        entry, bid, peak = map(_d, (entry_ask, current_bid, peak_bid))
        if not position_open or min(entry, bid, peak) <= 0 or peak < bid:
            return _reject("Invalid open position or premium marks")
        gain = peak / entry - 1
        stop = entry * Decimal(".75")
        if gain >= Decimal(".30"):
            stop = max(stop, entry)  # protect break-even, before fees
        if gain >= Decimal(".40"):
            stop = max(stop, entry * Decimal("1.15"))
        if gain >= Decimal(".50"):
            stop = max(stop, entry * Decimal("1.30"))
        if gain >= Decimal(".75"):
            stop = max(stop, entry * Decimal("1.50"))
        if gain >= Decimal("1.00"):
            stop = max(stop, peak * Decimal(".75"))
        if bid <= stop:
            action, reason = "EXIT_CANDIDATE", "Bid at or below progressive stop"
        elif momentum_confirmed is False:
            action, reason = "EXIT_CANDIDATE", "Confirmed momentum weakened"
        elif momentum_confirmed is not True:
            action, reason = "NO_TRADE", "Momentum confirmation unavailable"
        else:
            action, reason = "HOLD_CANDIDATE", "Momentum intact"
        return {"status": action, "execution": "NONE", "simulation_only": True,
                "stop_premium": str(stop.quantize(Decimal(".0001"))),
                "current_bid": str(bid), "reason": reason,
                "note": "No fill implied; revalidate quote and persist an actual paper exit"}
    except (ValueError, TypeError) as exc:
        return _reject(str(exc))
