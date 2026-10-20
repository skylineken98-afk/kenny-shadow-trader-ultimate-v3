"""Opt-in, paper simulation-only orchestration entrypoint.

Does not automatically manufacture quotes from underlying candle data.
Real quotes must be supplied by a separately validated data ingestion layer.
"""
import logging
import os
from core.paper_automation import simulate_signal, WorkerError

LOG = logging.getLogger(__name__)

def cycle(quote_provider=None):
    if os.getenv('V3_PAPER_AUTOMATION_ENABLED','false').lower()!='true':
        LOG.info('Paper automation disabled')
        return {'status':'DISABLED'}
    if quote_provider is None:
        # A missing provider must not create invented fills.
        LOG.warning('Verified option quote provider not configured; no simulated orders')
        return {'status':'NO_VERIFIED_QUOTE_PROVIDER'}
    from core.db import fetch
    outcomes=[]
    for signal in fetch('ultimate_signals',limit=100):
        if signal.get('status')!='SETUP': continue
        for agent in ('conservative','balanced','aggressive','challenge','daily_10pct_research'):
            try:
                quote = quote_provider(signal,agent)
                if quote is None: continue
                outcomes.append(simulate_signal(signal['id'],agent,quote))
            except WorkerError as exc:
                LOG.warning('Paper attempt skipped: %s', exc)
    return {'status':'PROCESSED','results':outcomes}

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    print(cycle())
