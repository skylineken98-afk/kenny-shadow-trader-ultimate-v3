"""One-shot scheduler-safe scanner. Never runs automatically by importing.

Produces private operational notices only, no raw UW data or live orders.
"""
import os
from datetime import datetime,timezone
from .uw_research_pipeline import collect_private_snapshot,private_summary

def run_once(tickers, *, enabled=False, max_symbols=5, collector=collect_private_snapshot):
    if not enabled or os.getenv('UW_SCAN_ENABLED','false').lower()!='true':
        return {'status':'DISABLED','items':[]}
    allowed=[]
    for ticker in tickers:
        clean=str(ticker).strip().upper()
        if clean and clean not in allowed: allowed.append(clean)
    if len(allowed)>max_symbols: return {'status':'LIMIT_EXCEEDED','items':[]}
    items=[]
    for ticker in allowed:
        try: items.append(private_summary(collector(ticker)))
        except (ValueError,RuntimeError): items.append({'ticker':ticker,'status':'ERROR'})
    return {'status':'RESEARCH_ONLY','scanned_at':datetime.now(timezone.utc).isoformat(),
            'items':items,'alerts_sent':0,'orders_placed':0}
