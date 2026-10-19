import logging,time,os,uuid
from core.settings import symbols
from core.market import confluence
from core.db import insert,now
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
def cycle():
    for sym in symbols():
        try:
            s=confluence(sym)
            row={'id':str(uuid.uuid4()),'created_at':now(),'symbol':sym,'status':s['status'],'side':s.get('side','WAIT'),'entry':s.get('entry'),'stop':s.get('stop'),'target':s.get('target'),'details':s,'source':'rule_based_scan','execution_state':'NONE'}
            r=insert('ultimate_signals',row);logging.info('%s %s %s',sym,s['status'],r.get('ok'))
        except Exception:logging.exception('scan failure %s',sym)
if __name__=='__main__':
    while True:
        try:cycle()
        except Exception:logging.exception('scan cycle failed')
        time.sleep(max(300,int(os.getenv('SCAN_INTERVAL_SECONDS','3600'))))
