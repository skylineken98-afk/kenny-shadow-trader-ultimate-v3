"""Budget-aware contract research tiers. Cheap contracts are not inherently bad;
wide spreads and missing quotes are still clearly flagged.

All thresholds are screening heuristics, not win probabilities.
"""
import math

def screening_policy(budget):
    try:
        budget = float(budget)
    except (ValueError, TypeError):
        raise ValueError("Invalid budget")
    if not math.isfinite(budget) or budget < 5 or budget > 3000:
        raise ValueError("Budget must be between $5 and $3000")
    # Low-premium contracts naturally have higher percentage spreads due to ticks.
    if budget <= 50:
        return {"max_spread_pct": 35., "min_volume": 1, "min_oi": 10}
    if budget <= 100:
        return {"max_spread_pct": 30., "min_volume": 1, "min_oi": 10}
    if budget <= 200:
        return {"max_spread_pct": 25., "min_volume": 2, "min_oi": 20}
    return {"max_spread_pct": 20., "min_volume": 5, "min_oi": 50}

def price_quality(bid, ask, budget, volume=None, oi=None):
    policy = screening_policy(budget)
    nums = (bid, ask)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in nums):
        return None, "INVALID_QUOTE"
    if bid <= 0 or ask <= bid or ask * 100 > float(budget):
        return None, "INVALID_OR_OVER_BUDGET"
    spread = 200 * (ask-bid)/(ask+bid)
    if spread > policy["max_spread_pct"]:
        return None, "SPREAD_TOO_WIDE"
    # V1 snapshots may omit volume and OI. Missing liquidity is not verified.
    if volume is not None and (not math.isfinite(volume) or volume < policy["min_volume"]):
        return None, "LOW_VOLUME"
    if oi is not None and (not math.isfinite(oi) or oi < policy["min_oi"]):
        return None, "LOW_OPEN_INTEREST"
    speculative = (spread > 15 or ask < 0.20 or
                   volume is None or oi is None or
                   (volume is not None and volume < 5) or
                   (oi is not None and oi < 50))
    return {
        "spread_pct": round(spread, 2),
        "liquidity_label": "SPECULATIVE_HIGH_FRICTION" if speculative else "STANDARD",
        "premium_band": "$50" if ask*100 <= 50 else "$100" if ask*100 <= 100 else "$200" if ask*100 <= 200 else "ABOVE_200",
        "estimated_roundtrip_spread_cost": round((ask-bid)*100, 2),
        "verified_executable": False,
    }, None
