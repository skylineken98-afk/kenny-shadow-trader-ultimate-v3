"""Read-only personal trade research intake. No broker access or order execution.

The caller must supply independently broker-verified CLOSED executions.
All timestamps must be aware; market features must have existed before entry.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

def _time(value):
    if not isinstance(value, str):
        raise ValueError("ISO timestamp string required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("Timezone must be explicit")
    return dt.astimezone(timezone.utc)

def _money(value, *, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid decimal") from exc
    if not number.is_finite() or (positive and number <= 0):
        raise ValueError("Nonfinite or nonpositive amount")
    return number

def normalize_closed_trade(trade, features=None):
    """Build privacy-minimized, independently auditable outcome.

    Expected already reconciled broker fields: provider, broker_trade_id,
    symbol, asset_type, entry_time, exit_time, quantity, entry_total,
    exit_total, fees_total, fill_verified=True, closed=True.
    Totals are positive cash notionals for *long* positions only (e.g.
    summed contract premium x 100); do not mix underlying spot with option fills.
    Partial fills must be aggregated by the caller before normalization.
    """
    if not isinstance(trade, dict):
        raise ValueError("Trade must be a mapping")
    if trade.get("fill_verified") is not True or trade.get("closed") is not True:
        raise ValueError("Require independently verified, closed fills")
    provider = trade.get("provider")
    if provider not in ("ROBINHOOD", "MANUAL_VERIFIED"):
        raise ValueError("Unsupported verified source")
    identifier = trade.get("broker_trade_id")
    if not isinstance(identifier, str) or not 1 <= len(identifier) <= 128:
        raise ValueError("Missing provider trade identifier")
    symbol = trade.get("symbol")
    if not isinstance(symbol, str) or re.fullmatch(r"[A-Z0-9.\\-]{1,32}", symbol) is None:
        raise ValueError("Invalid symbol")
    asset = trade.get("asset_type")
    if asset not in ("EQUITY_LONG", "OPTION_LONG_CALL", "OPTION_LONG_PUT"):
        raise ValueError("Unsupported position type; only long, fully closed positions")
    entry, exit_ = _time(trade.get("entry_time")), _time(trade.get("exit_time"))
    if entry >= exit_ or exit_ > datetime.now(timezone.utc):
        raise ValueError("Trade chronology invalid")
    quantity = _money(trade.get("quantity"), positive=True)
    entry_total = _money(trade.get("entry_total"), positive=True)
    exit_total = _money(trade.get("exit_total"))
    fees = _money(trade.get("fees_total", "0"))
    if exit_total < 0 or fees < 0:
        raise ValueError("Negative proceeds or fees")
    net_pnl = exit_total - entry_total - fees
    ret = net_pnl / entry_total * 100
    if ret < -100 or ret > 100000:
        raise ValueError("Return outside research scoring range")
    features = features or {}
    if not isinstance(features, dict):
        raise ValueError("Features must be a mapping")
    allowed = {"spx_trend", "spy_relative_qqq", "vix", "sector_pressure",
               "market_regime", "institutional_stress_status", "setup_tag"}
    if set(features) - allowed:
        raise ValueError("Unapproved market feature fields")
    if features:
        available = _time(trade.get("feature_available_at"))
        if available > entry:
            raise ValueError("Reject future information at trade entry")
    else:
        available = entry
    # Stable scoped trade ID, without leaking broker IDs into public dashboards.
    record_id = sha256(f"{provider}:{identifier}".encode()).hexdigest()
    return {
        "trade_id": record_id, "provider": provider, "symbol": symbol,
        "asset_type": asset, "quantity": str(quantity),
        "decision_time": entry.isoformat(), "feature_available_at": available.isoformat(),
        "exit_time": exit_.isoformat(), "entry_total": str(entry_total),
        "exit_total": str(exit_total), "fees_total": str(fees),
        "net_pnl": str(net_pnl), "net_return_pct": round(float(ret), 4),
        "fill_verified": True, "closed": True, "market_features": features,
        "research_only": True, "execution_enabled": False,
    }

def research_summary(records):
    """Descriptive statistics, never claim causal learning or a validated edge."""
    rows = [r for r in records if r.get("fill_verified") is True and r.get("closed") is True]
    if not rows:
        return {"verified_closed_trades": 0, "net_pnl": None, "win_rate": None,
                "average_return_pct": None, "status": "INSUFFICIENT_DATA"}
    pnl = sum((_money(r["net_pnl"]) for r in rows), Decimal(0))
    returns = [_money(r["net_return_pct"]) for r in rows]
    return {
        "verified_closed_trades": len(rows), "net_pnl": str(pnl),
        "win_rate": round(sum(_money(r["net_pnl"]) > 0 for r in rows) / len(rows), 4),
        "average_return_pct": round(float(sum(returns) / len(rows)), 4),
        "status": "DESCRIPTIVE_ONLY", "automatic_strategy_update": False,
    }

def persist_verified_trade(owner_id, trade, features=None, *, enabled=False, db_client=None):
    """Explicit opt-in server-only upsert. Never call from public/mobile client.

    Requires private Supabase migration and authenticated owner UUID provided
    by a server-side authorization layer; no trust in caller-supplied user IDs.
    """
    if not enabled:
        raise PermissionError("Personal trade learning ingestion disabled")
    import uuid
    owner = str(uuid.UUID(str(owner_id)))
    record = normalize_closed_trade(trade, features)
    if db_client is None:
        from core.db import client
        db_client = client()
    row = {"owner_id": owner, "trade_id": record["trade_id"],
           "research_record": record}
    result = db_client.table("kst_personal_trade_research").upsert(
        row, on_conflict="owner_id,trade_id").execute()
    if getattr(result, "data", None) is None:
        raise RuntimeError("Database did not confirm research upsert")
    return {"status": "RECORDED_RESEARCH_ONLY", "trade_id": record["trade_id"]}
