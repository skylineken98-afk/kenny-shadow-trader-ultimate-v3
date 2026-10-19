import logging, os, time
from workers.scan_worker import cycle as scan_cycle
from workers.ai_news_worker import cycle as news_cycle
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')

def main(role='orchestrator'):
    if role not in ('orchestrator','news','scan'): raise ValueError('WORKER_ROLE must be orchestrator, news, or scan')
    logging.info('Ultimate V2 starting role=%s; live execution disabled',role)
    while True:
        if role in ('orchestrator','news'):
            try: news_cycle()
            except Exception: logging.exception('News cycle failed')
        if role in ('orchestrator','scan'):
            try: scan_cycle()
            except Exception: logging.exception('Scan cycle failed')
        if os.getenv('RUN_ONCE','0')=='1': break
        time.sleep(max(300,int(os.getenv('WORKER_INTERVAL_SECONDS','3600'))))
