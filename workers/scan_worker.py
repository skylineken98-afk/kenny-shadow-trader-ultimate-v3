import logging,time,os,uuid
from core.settings import symbols
from core.market import confluence
from core.db import insert,now
from core.institutional_stress import snapshot as institutional_stress_snapshot
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
def cycle():
    # Fetch once per scan cycle. Failure must never masquerade as a calm market.
    try:
        stress = institutional_stress_snapshot()
    except Exception as exc:
        logging.warning('institutional stress unavailable: %s', type(exc).__name__)
        stress = {'status':'UNAVAILABLE','forced_liquidation_confirmed':False,
                  'evidence_class':'MARKET_PROXY_ONLY','trade_action':'NONE'}
    for sym in symbols():
        try:
            s=confluence(sym)
            s['institutional_stress'] = stress
            row={'id':str(uuid.uuid4()),'created_at':now(),'symbol':sym,'status':s['status'],'side':s.get('side','WAIT'),'entry':s.get('entry'),'stop':s.get('stop'),'target':s.get('target'),'details':s,'source':'rule_based_scan','execution_state':'NONE'}
            r=insert('ultimate_signals',row);logging.info('%s %s %s',sym,s['status'],r.get('ok'))
        except Exception:logging.exception('scan failure %s',sym)
if __name__=='__main__' and os.getenv('RAILWAY_SERVICE_NAME') == 'kst-momentum-alerts':
    # Isolated service uses the existing Railway default start command, but
    # must never duplicate the primary market scanner or place orders.
    from kst_options.momentum_alert_worker import main as telegram_momentum_main
    telegram_momentum_main()
elif __name__=='__main__':
    import threading
    from kst_pro.ops import heartbeat_loop
    threading.Thread(target=heartbeat_loop,args=('scanner',),daemon=True).start()
    while True:
        try:cycle()
        except Exception:logging.exception('scan cycle failed')
        time.sleep(max(300,int(os.getenv('SCAN_INTERVAL_SECONDS','3600'))))
