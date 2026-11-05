"""Consent-gated broker fill attribution for a future KST learning pipeline.

Not a broker connector. No credential ingestion, order submission, or trading
permission escalation exists in this module.
"""
from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
import re

SUPPORTED_PROVIDERS=frozenset(("alpaca",))  # Add each broker only after approved OAuth integration
READ_SCOPES=frozenset(("positions:read","orders:read","fills:read","account:read"))
EXECUTE_SCOPE="trading"
CONSENT_VERSION="v1-2026-11"
MIN_AGGREGATE_USERS=20

def normalize_permissions(read_only=True, request_execution=False, broker_approved=False):
    if request_execution:
        if not broker_approved:
            raise PermissionError("Live broker integration must be approved first")
        if read_only:
            raise PermissionError("Execution requires a separate explicit approval")
        raise PermissionError("Production automated execution is disabled pending regulatory and risk reviews")
    return {"scopes":sorted(READ_SCOPES),"execution_enabled":False,
            "training_enabled":False,"requires_user_login":True}

def consent_allows_learning(record,observed_at=None):
    observed_at=observed_at or datetime.now(timezone.utc)
    if not isinstance(record,dict):return False
    agreed=record.get("consented_at")
    if record.get("consent_version")!=CONSENT_VERSION or not record.get("learning_enabled"):return False
    if record.get("revoked_at"):return False
    try:
        at=datetime.fromisoformat(str(agreed).replace("Z","+00:00"))
        return at.tzinfo is not None and at<=observed_at
    except (TypeError,ValueError):return False

def _time(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError,ValueError,OverflowError):return None

def _norm(value):
    try:
        v=Decimal(str(value))
        return v if v.is_finite() else None
    except (InvalidOperation,TypeError):return None

def attribution(fill,signals,clicked_signal_ids=(),max_age_minutes=90):
    """Conservative: a close match is only 'POSSIBLE', not proven causation.

    Confirmed attribution requires separately audited user click/token provenance.
    Never infer a causal effect from an overlapping ticker alone.
    """
    filled_at=_time(fill.get("filled_at"))
    if filled_at is None:return {"label":"UNATTRIBUTED","signal_id":None,"reason":"Unknown fill timestamp"}
    symbol=str(fill.get("symbol") or "").upper()
    side=str(fill.get("side") or "").upper()
    if not re.fullmatch(r"[A-Z.]{1,10}",symbol) or side not in ("BUY","SELL","BTO","STO"):
        return {"label":"UNATTRIBUTED","signal_id":None,"reason":"Unusable instrument or side"}
    matches=[]
    for signal in signals:
        sigtime=_time(signal.get("created_at"))
        if sigtime is None or sigtime>filled_at or filled_at-sigtime>timedelta(minutes=max_age_minutes):
            continue
        if signal.get("status")!="SETUP" or str(signal.get("symbol") or "").upper()!=symbol:
            continue
        direction=str(signal.get("side") or "").upper()
        if direction not in ("BULLISH","BEARISH"):continue
        # Buying bullish calls/bearish puts or shorting equities can be direction-aligned;
        # otherwise don't pretend to attribute the user's intentional strategy.
        opt_type=str(fill.get("option_type") or "").upper()
        if opt_type in ("CALL","PUT"):
            if side not in ("BUY","BTO") or opt_type!=("CALL" if direction=="BULLISH" else "PUT"):
                continue
        elif (side in ("BUY","BTO")) != (direction=="BULLISH"):
            continue
        if fill.get("signal_contract") and signal.get("contract") and fill["signal_contract"]!=signal["contract"]:
            continue
        matches.append(signal)
    if not matches:return {"label":"UNATTRIBUTED","signal_id":None,"reason":"No compatible recent signal"}
    matches.sort(key=lambda x: _time(x["created_at"]),reverse=True)
    chosen=matches[0]
    ident=chosen.get("id")
    if ident and ident in clicked_signal_ids:
        return {"label":"USER_SELECTED_SIGNAL","signal_id":ident,"reason":"Audited explicit selection, not guaranteed execution causality"}
    return {"label":"POSSIBLE_MATCH","signal_id":ident,"reason":"Same ticker, aligned direction and timing; not proof KST caused trade"}

def training_observation(consent,fill,outcome,signals,clicked=()):
    if not consent_allows_learning(consent):
        raise PermissionError("Collective learning requires explicit, active consent")
    pnl=_norm(outcome.get("realized_pnl"))
    if pnl is None:raise ValueError("Broker-verified realized P/L required")
    elapsed=_time(outcome.get("closed_at"))
    start=_time(fill.get("filled_at"))
    if start is None or elapsed is None or elapsed<=start:raise ValueError("Verified fill and close timestamps required")
    attr=attribution(fill,signals,clicked)
    return {"symbol":str(fill["symbol"]).upper(),
            "asset_type":fill.get("asset_type"),
            "direction":str(fill.get("side")).upper(),
            "signal_attribution":attr["label"],
            "signal_id":attr["signal_id"],
            "holding_minutes":round((elapsed-start).total_seconds()/60,1),
            "realized_pnl_sign":1 if pnl>0 else (-1 if pnl<0 else 0),
            "pnl_dollars":float(pnl),
            "verified_source":"broker_fill_and_close",
            "no_personal_identifiers":True,
            "note":"Research observation; does not establish a signal caused the result."}

def public_group_summary(rows):
    """Never publish performance from tiny cohorts or unsupported totals."""
    users={r.get("user_id") for r in rows if r.get("user_id")}
    if len(users)<MIN_AGGREGATE_USERS:
        return {"status":"INSUFFICIENT_INDEPENDENT_USERS","unique_users":len(users),"published":False}
    valid=[r for r in rows if r.get("verified_source")=="broker_fill_and_close" and _norm(r.get("pnl_dollars")) is not None]
    if len(valid)<MIN_AGGREGATE_USERS:
        return {"status":"INSUFFICIENT_VERIFIED_TRADES","published":False}
    # Never expose user IDs, account identifiers, or raw trade histories.
    return {"status":"READY_FOR_AGGREGATE_REVIEW","published":False,
            "verified_trades":len(valid),"cohort_users":len(users),
            "note":"Requires anti-selection-bias review before any model update or public win rate."}
