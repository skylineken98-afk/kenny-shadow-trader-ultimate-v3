"""Opt-in candidate-only paper worker. Does not execute, open or close real orders."""
import logging, os, time
from core.db import fetch, insert
from core.paper_agent import PROFILES, create_event_from_signal
LOG=logging.getLogger(__name__)

def cycle():
    if os.getenv('PAPER_AUTO_ENABLED','false').lower()!='true':
        LOG.info('Paper worker disabled; PAPER_AUTO_ENABLED is not true');return
    signals=fetch('ultimate_signals',limit=100)
    equity=float(os.getenv('PAPER_RESEARCH_EQUITY','10000'))
    for row in signals:
        if row.get('status')!='SETUP':continue
        signal=dict(row.get('details') or {})
        signal.update({'id':row.get('id'),'symbol':row.get('symbol'),
                       'side':row.get('side'),'entry':row.get('entry'),
                       'stop':row.get('stop'),'target':row.get('target')})
        for name in PROFILES:
            event=create_event_from_signal(signal,name,equity)
            if event.get('status')!='CANDIDATE_ONLY':continue
            # Unique primary key guards repeated worker cycles, not a filled trade.
            result=insert('paper_agent_events',event)
            if not result['ok'] and 'duplicate' not in str(result.get('error','')).lower():
                LOG.warning('candidate storage issue %s: %s',name,result.get('error'))

def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:cycle()
        except Exception:LOG.exception('paper cycle failed')
        if os.getenv('RUN_ONCE')=='1':break
        time.sleep(max(300,int(os.getenv('PAPER_INTERVAL_SECONDS','3600'))))
if __name__=='__main__':main()
