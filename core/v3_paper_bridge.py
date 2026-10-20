"""Explicit opt-in Supabase RPC adapter; never submits real orders.

Do not call until SQL migration reviewed, fresh trusted OCC quotes verified,
account armed deliberately, and exit/settlement logic implemented and tested.
"""
import os
from decimal import Decimal
from core.agents import PROFILES
from core.db import client

class BridgeDisabled(RuntimeError):
    pass

def record_research_entry(*, agent, signal_id, occ, asset, direction,
                          ask, stop, target, quote_timestamp):
    if os.getenv('V3_ATOMIC_PAPER_BRIDGE_ENABLED','false').lower() != 'true':
        raise BridgeDisabled('Atomic paper bridge is disabled')
    if agent not in PROFILES:
        raise ValueError('Unknown paper agent')
    if not all(Decimal(str(x)).is_finite() for x in (ask,stop,target)):
        raise ValueError('Nonfinite price')
    payload = {
        'p_agent':agent, 'p_signal':str(signal_id), 'p_occ':occ,
        'p_asset':asset,'p_direction':direction,'p_ask':str(ask),
        'p_stop':str(stop),'p_target':str(target),
        'p_quote_time':str(quote_timestamp),
        'p_max_risk':str(PROFILES[agent].max_risk_fraction),
        'p_max_exposure':'0.25'
    }
    # PostgREST RPC is one database transaction. Do not fall back to multiple inserts.
    try:
        result=client().rpc('v3_record_paper_entry',payload).execute()
        if not result.data: raise BridgeDisabled('No confirmed order ID from database')
        return {'status':'DATABASE_RECORDED_SIMULATED_ONLY','order_id':str(result.data)}
    except Exception as exc:
        raise BridgeDisabled('Database rejected paper transaction; no execution recorded') from exc
