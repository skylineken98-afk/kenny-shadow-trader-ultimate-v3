"""Shared read-only KST research tool contract for website and future ChatGPT MCP.

This module does NOT implement OAuth, public MCP transport, or fresh scan jobs.
It intentionally exposes stored observations only, with explicit provenance.
"""
from datetime import datetime, timezone
from .market_research import market_research

_ALLOWED = {"research_snapshot", "market_coverage"}
_MAX_BUDGET = 100000

class ResearchToolError(ValueError):
    pass

def run_research_tool(store, tool, arguments=None, *, now=None):
    """Return JSON-serializable research data; caller must authenticate/authorize first.

    Never accept arbitrary table names, SQL, user IDs, broker instructions or
    provider keys from an untrusted caller.
    """
    if tool not in _ALLOWED:
        raise ResearchToolError("Unsupported research tool")
    args = arguments or {}
    if not isinstance(args, dict):
        raise ResearchToolError("Expected an object")
    if set(args) - {"symbol", "horizon", "direction", "max_contract_cost"}:
        raise ResearchToolError("Unsupported argument")
    symbol = str(args.get("symbol") or "").upper().strip()
    if symbol and (not symbol.isascii() or not symbol.isalpha() or not 1 <= len(symbol) <= 6):
        raise ResearchToolError("Invalid symbol")
    horizon = str(args.get("horizon") or "all").lower()
    if horizon not in {"all", "0dte", "swings", "leaps"}:
        raise ResearchToolError("Invalid horizon")
    direction = str(args.get("direction") or "both").lower()
    if direction not in {"both", "bullish", "bearish"}:
        raise ResearchToolError("Invalid direction")
    budget = args.get("max_contract_cost")
    if budget is not None:
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 0 < budget <= _MAX_BUDGET:
            raise ResearchToolError("Invalid maximum contract cost")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ResearchToolError("Timestamp must be timezone aware")
    # Existing retrieval handles symbol-scoped DB queries; these are cached
    # snapshots, NOT evidence that a new market scan ran.
    query = "Show best option trades and technical setups"
    if horizon != "all":
        query += " " + horizon
    if symbol:
        query += " " + symbol
    data, references = market_research(store, query, now=now)
    candidates = data.get("contract_candidates")
    if isinstance(candidates, list):
        def keep(item):
            if horizon != "all" and str(item.get("category") or "").lower() != horizon:
                return False
            if direction != "both":
                typ = str(item.get("option_type") or "").lower()
                if typ not in {"call", "put"} or (typ == "call") != (direction == "bullish"):
                    return False
            if budget is not None:
                # Standard US equity option multiplier is 100, but not all
                # contracts use it. Do not guess affordability for others.
                contract = str(item.get("contract") or "")
                ask = item.get("entry_ask")
                if not contract or not isinstance(ask, (int, float)) or ask <= 0:
                    return False
                if not contract.startswith(str(item.get("underlying") or "")):
                    return False
                if ask * 100 > budget:
                    return False
            return True
        data["contract_candidates"] = [x for x in candidates if keep(x)]
    if tool == "market_coverage":
        return {"observed_at": now.isoformat(), "coverage": data.get("coverage", {"status": "UNAVAILABLE"}),
                "scope": "stored KST research sample; not full market coverage"}
    return {"observed_at": now.isoformat(), "kind": "stored_research_snapshot",
            "fresh_scan_triggered": False, "broker_orders_enabled": False,
            "research_only": True, "filters": {"symbol": symbol or None, "horizon": horizon,
            "direction": direction, "max_contract_cost": budget},
            "data": data, "references": references,
            "warning": "Indicative quotes are not executable; verify contract multiplier, spread, liquidity and freshness independently."}
