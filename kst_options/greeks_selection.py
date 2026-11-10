"""KST Greeks-aware, quote-based options research (no orders, no win probabilities).

The five Greeks are vendor estimates, not audited option prices or guaranteed
future sensitivities. Missing/unverified timestamps are explicitly flagged.
The selection adjustment is small and cannot override liquidity/budget gates.
"""
from datetime import datetime, timezone
import math

GREEKS = ("delta", "gamma", "theta", "vega", "rho")


def _finite(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def analyze_contract_greeks(snapshot, *, option_type, entry_ask, underlying_price=None,
                            assumed_move_pct=1.0, holding_days=1.0, now=None,
                            max_greek_age_seconds=300):
    """Interpret provider Greeks without fetching data or making trading decisions.

    Standard Greek units assumed: delta in premium/$ underlying, gamma in
    delta/$ underlying, theta in premium/calendar-day, vega in premium/one
    implied-volatility *percentage point*, and rho in premium/one percentage
    point rate shift. Providers can differ: outputs are conditional estimates.
    """
    if option_type not in ("CALL", "PUT"):
        raise ValueError("Invalid option type")
    ask = _finite(entry_ask)
    move_pct, days = _finite(assumed_move_pct), _finite(holding_days)
    if ask is None or ask <= 0 or move_pct is None or not 0 < move_pct <= 20 or days is None or not 0 <= days <= 365:
        raise ValueError("Invalid scenario inputs")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    data = snapshot if isinstance(snapshot, dict) else {}
    raw = data.get("greeks") or {}
    raw = raw if isinstance(raw, dict) else {}
    values = {g: _finite(raw.get(g)) for g in GREEKS}
    warnings = []
    delta, gamma, theta, vega = (values[k] for k in ("delta", "gamma", "theta", "vega"))
    if delta is None or not (-1 <= delta <= 1) or (delta <= 0 if option_type == "CALL" else delta >= 0):
        warnings.append("Missing or direction-inconsistent Delta")
    if gamma is None or not 0 <= gamma <= 100:
        warnings.append("Missing or invalid Gamma")
    if theta is None or theta > 0:
        warnings.append("Theta missing or unconventional positive sign")
    if vega is None or vega < 0:
        warnings.append("Vega missing or unconventional negative sign")
    greek_time = _timestamp(data.get("greeks_timestamp") or data.get("greeks_at"))
    age = (now - greek_time).total_seconds() if greek_time else None
    fresh = age is not None and 0 <= age <= max_greek_age_seconds
    if not fresh:
        warnings.append("Greeks timestamp absent, stale or future dated; no live-Greeks verification")
    price = _finite(underlying_price)
    scenarios = []
    if price is not None and price > 0 and all(x is not None for x in (delta, gamma, theta, vega)):
        if -1 <= delta <= 1 and 0 <= gamma <= 100 and theta <= 0 and vega >= 0:
            change = price * move_pct / 100
            for direction in (-1, 1):
                for iv_point_change in (-2.0, 0.0, 2.0):
                    underlying_change = direction * change
                    approximate_premium_change = (delta * underlying_change +
                        .5 * gamma * underlying_change ** 2 + theta * days +
                        vega * iv_point_change)
                    scenarios.append({
                        "underlying_change": round(underlying_change, 5),
                        "iv_change_percentage_points": iv_point_change,
                        "holding_days": days,
                        "estimated_premium": round(max(0.0, ask + approximate_premium_change), 5),
                        "estimated_contract_pnl_before_costs": round(
                            (max(0.0, ask + approximate_premium_change) - ask) * 100, 2),
                    })
    else:
        warnings.append("Underlying price or required Greeks unavailable: no scenarios generated")

    # Risk metrics are descriptive only; 0DTE Greeks can shift drastically.
    theta_pct_day = abs(theta)/ask*100 if theta is not None and theta <= 0 else None
    delta_abs = abs(delta) if delta is not None else None
    gamma_leverage = gamma / max(delta_abs, .01) if gamma is not None and delta_abs is not None else None
    # Never apply quality bonus when Greek timestamp provenance is unknown.
    # Bounded [-5,+5], not a prediction or win-probability.
    adjustment = 0.0
    if fresh and theta_pct_day is not None and gamma_leverage is not None and delta_abs is not None:
        adjustment = max(-5.0, min(5.0, 2.0 * (1-abs(delta_abs-.50)/.50)
            + min(gamma_leverage, 2.0) - min(theta_pct_day/10.0, 7.0)))
    return {
        "greeks": values,
        "greeks_at": greek_time.isoformat() if greek_time else None,
        "greeks_age_seconds": round(age, 1) if age is not None else None,
        "greeks_fresh_verified_timestamp": fresh,
        "theta_pct_of_ask_per_day_proxy": round(theta_pct_day, 2) if theta_pct_day is not None else None,
        "gamma_to_abs_delta_proxy": round(gamma_leverage, 5) if gamma_leverage is not None else None,
        "structural_score_adjustment": round(adjustment, 3),
        "scenarios": scenarios,
        "warnings": warnings,
        "model": "static delta-gamma-theta-vega approximation; not an option pricing model",
        "source_note": "Vendor Greek units, calculation cadence and timestamps must be verified separately.",
        "not_probability_of_profit": True,
        "research_only": True,
    }


def rank_with_greeks(candidates, *, now=None):
    """Rank already qualified contracts only; retain missing-Greeks candidates.

    Returns copies: structural score remains exposed, Greek-adjusted score is
    separately labeled. Does not introduce new execution or affordability rules.
    """
    now = now or datetime.now(timezone.utc)
    rows = []
    for candidate in candidates:
        c = dict(candidate)
        analysis = c.get("greeks_analysis") or (c.get("risk_snapshot") or {}).get("greeks_analysis") or {}
        bonus = _finite(analysis.get("structural_score_adjustment"))
        if not analysis.get("greeks_fresh_verified_timestamp"):
            bonus = 0.0
        base = _finite(c.get("score"))
        c["greeks_adjusted_score"] = round(max(0.0, min(100.0, base + max(-5.0, min(5.0, bonus or 0)))), 3) if base is not None else None
        c["greeks_adjustment_applied"] = bool(bonus)
        rows.append(c)
    return sorted(rows, key=lambda x: (-(x.get("greeks_adjusted_score") if x.get("greeks_adjusted_score") is not None else -1),
                                        str(x.get("contract") or "")))
