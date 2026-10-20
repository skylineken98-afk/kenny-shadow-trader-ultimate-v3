"""Private, read-only Unusual Whales research orchestration.

Do not expose vendor records to public pages or train/redistribute without a license.
No order placement; no hidden live calls; endpoint names must be confirmed against API docs.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from . import unusual_whales as uw

# These paths are existing adapter methods, not speculative vendor routes.
SOURCES = {'flow': uw.stock_flow, 'greeks': uw.greek_exposure, 'darkpool': uw.darkpool}

def collect_private_snapshot(ticker, sources=None):
    """Fetch ticker snapshots; report unavailable entitlements as errors, not false zeros."""
    ticker=uw._ticker(ticker)
    selected=list(SOURCES) if sources is None else list(sources)
    if any(s not in SOURCES for s in selected):
        raise ValueError('Unknown research source')
    now=datetime.now(timezone.utc).isoformat()
    results={};errors={}
    for source in selected:
        try:
            payload=SOURCES[source](ticker)
            results[source]=payload.get('data')
        except (uw.UnusualWhalesError, ValueError) as exc:
            errors[source]=str(exc)
    return {'ticker':ticker,'observed_at':now,'sources':results,'errors':errors,
            'partial':bool(errors),'research_only':True,'real_money_execution':False}

def snapshot_id(snapshot):
    compact=json.dumps(snapshot,sort_keys=True,default=str)
    return hashlib.sha256(compact.encode()).hexdigest()

def private_summary(snapshot):
    """Safe operational metadata only: intentionally excludes licensed vendor values."""
    return {'ticker':snapshot['ticker'],'observed_at':snapshot['observed_at'],
            'sources_ok':list(snapshot['sources']), 'sources_failed':list(snapshot['errors']),
            'research_only':True}
