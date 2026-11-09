"""Offline, provider-neutral unusual options trade-print research. No network or orders.

Raw prints must come from a licensed source. Nothing here infers buyer identity or
institutional intent. Missing quotes/conditions suppress directional claims.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from math import isfinite
from collections import defaultdict
import re

OCC = re.compile(r"^([A-Z.]{1,8})(\d{6})([CP])(\d{8})$")
MIN_PREMIUM = 250_000
MAX_AGE = timedelta(minutes=2)
HORIZONS = (5, 15, 30, 60)


def _time(value):
    if isinstance(value, datetime):
        t = value
    elif isinstance(value, str):
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp required")
    if t.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return t.astimezone(timezone.utc)


def _number(value, *, positive=False):
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    n = float(value)
    if not isfinite(n) or (positive and n <= 0):
        raise ValueError("invalid finite number")
    return n


def normalize_print(raw, *, as_of, min_premium=MIN_PREMIUM):
    """Validate one trade; return None for small prints, raise on bad input.

    Expected adapter fields: id, contract (OCC), time, price, size, provider,
    and optional bid, ask, underlying_price, open_interest, conditions, delay_seconds.
    """
    match = OCC.fullmatch(str(raw["contract"]).upper())
    if not match:
        raise ValueError("invalid OCC option symbol")
    now, stamp = _time(as_of), _time(raw["time"])
    if stamp > now + timedelta(seconds=5) or now-stamp > MAX_AGE:
        raise ValueError("stale or future trade")
    size = raw["size"]
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("invalid contracts")
    price = _number(raw["price"], positive=True)
    premium = price * size * 100  # standard equity option multiplier only
    if premium < min_premium:
        return None
    if not str(raw.get("id", "")).strip() or not str(raw.get("provider", "")).strip():
        raise ValueError("missing provenance")
    bid = raw.get("bid")
    ask = raw.get("ask")
    side = "UNKNOWN"
    if bid is not None and ask is not None:
        bid, ask = _number(bid), _number(ask)
        if bid <= 0 or ask < bid:
            raise ValueError("invalid quote")
        spread = ask-bid
        if spread > 0:
            if price >= ask: side = "ASK_SIDE_PRINT"
            elif price <= bid: side = "BID_SIDE_PRINT"
            else: side = "MID_OR_INSIDE"
    else:
        bid = ask = None
    if raw.get("delayed", False) or raw.get("condition_unknown", False):
        side = "UNKNOWN"
    symbol, yymmdd, right, strike = match.groups()
    conditions = raw.get("conditions") or []
    if not isinstance(conditions, list):
        raise ValueError("conditions must be list")
    return {
        "event_id": str(raw["provider"])+":"+str(raw["id"]),
        "provider": str(raw["provider"]), "contract": str(raw["contract"]).upper(),
        "symbol": symbol, "expiration": "20"+yymmdd[:2]+"-"+yymmdd[2:4]+"-"+yymmdd[4:],
        "right": "CALL" if right == "C" else "PUT", "strike": int(strike)/1000,
        "time": stamp.isoformat(), "price": price, "size": size,
        "premium": round(premium, 2), "bid": bid, "ask": ask,
        "execution": side, "conditions": conditions,
        "delayed": bool(raw.get("delayed", False)), "license_scope": "INTERNAL_ONLY",
        "open_interest": raw.get("open_interest"),
        "underlying_price": raw.get("underlying_price"),
        "status": "RESEARCH_UNCONFIRMED",
    }


def detect_spreads(prints, *, max_gap_ms=1000):
    """Flag likely multi-leg groups; never assert that prints are one order.

    Equal contract counts, same underlying and expiry, near-simultaneous times,
    different strikes, and opposite execution sides are required.
    """
    result = [dict(p, possible_spread=False, spread_peer_ids=[]) for p in prints]
    for i, a in enumerate(result):
        for b in result[i+1:]:
            if a["event_id"] == b["event_id"]: continue
            if (a["symbol"], a["expiration"], a["right"], a["size"]) != (
                b["symbol"], b["expiration"], b["right"], b["size"]):
                continue
            if a["strike"] == b["strike"]: continue
            if {a["execution"], b["execution"]} != {"ASK_SIDE_PRINT", "BID_SIDE_PRINT"}:
                continue
            delta = abs((_time(a["time"])-_time(b["time"])).total_seconds()*1000)
            if delta <= max_gap_ms:
                a["possible_spread"] = b["possible_spread"] = True
                a["spread_peer_ids"].append(b["event_id"])
                b["spread_peer_ids"].append(a["event_id"])
    return result


def evaluate_response(event, stock_bars):
    """Forward returns from *future* real observed underlying prints, never fabricated.

    stock_bars rows: {time, price}; each horizon needs an observation at or
    after the horizon, no more than 1 minute afterward.
    """
    start = _time(event["time"])
    base = event.get("underlying_price")
    if base is None: return {"status": "NO_ENTRY_STOCK_PRICE", "returns_pct": {}}
    base = _number(base, positive=True)
    bars = sorted((_time(b["time"]), _number(b["price"], positive=True)) for b in stock_bars)
    returns = {}
    for m in HORIZONS:
        target = start + timedelta(minutes=m)
        eligible = [(t,p) for t,p in bars if target <= t <= target+timedelta(minutes=1)]
        returns[str(m)+"m"] = round((eligible[0][1]/base-1)*100, 3) if eligible else None
    return {"status": "PARTIAL" if None in returns.values() else "COMPLETE",
            "returns_pct": returns, "method": "timestamped underlying trade-price response, not option P/L"}


def analyze_batch(raw_prints, *, as_of, min_premium=MIN_PREMIUM):
    """No external effects. Excludes invalid/stale prints and duplicate provider IDs."""
    accepted, rejected, seen = [], defaultdict(int), set()
    for raw in raw_prints:
        try:
            p = normalize_print(raw, as_of=as_of, min_premium=min_premium)
            if p is None:
                rejected["BELOW_THRESHOLD"] += 1
                continue
            if p["event_id"] in seen:
                rejected["DUPLICATE"] += 1
                continue
            seen.add(p["event_id"])
            accepted.append(p)
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected["INVALID_OR_STALE"] += 1
    return {"events": detect_spreads(accepted), "rejected": dict(rejected),
            "coverage": "ONLY_PROVIDER_PRINTS_RECEIVED",
            "notice": "Prints and inferred sides are not verified opening buys or institutional activity"}


def alert_preview(event, *, telegram=True, website=True):
    """Create inert alert intent; no external delivery unless a separate approved gateway exists."""
    risk = "POSSIBLE_MULTI_LEG" if event.get("possible_spread") else "SINGLE_PRINT_UNCONFIRMED"
    return {"idempotency_key": event["event_id"],
            "channels": [x for x, on in (("telegram", telegram), ("website", website)) if on],
            "delivery_status": "DISABLED_REQUIRES_APPROVAL",
            "title": event["symbol"]+" "+event["right"]+" unusual print",
            "premium": event["premium"], "contract": event["contract"], "risk": risk,
            "execution": event["execution"], "provider": event["provider"],
            "time": event["time"], "scope": "INTERNAL_ONLY"}
