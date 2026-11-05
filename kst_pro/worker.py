"""Additional Railway service: python -m kst_pro.worker. No broker submission."""
import logging,os,time
from .ops import beat,monitor,health
from .market import refresh_company,refresh_earnings,enrich_earnings,ticker
from .positions import refresh as refresh_positions
from kst_options.engine import utcnow
from kst_options.store import Store
log=logging.getLogger('kst.pro')

def run():
 store=Store();last={};rotation=0
 while True:
  now=utcnow()
  try:beat(store,'pro')
  except Exception:log.warning('Database heartbeat failed; connection/migration needs attention')
  def task(name,interval,fn):
   if time.monotonic()-last.get(name,-1000000000)<interval:return False
   try:
    fn();health(store,name,'OK','Scheduled task completed; inspect timestamps and coverage in the relevant tab')
   except ValueError:
    health(store,name,'CONFIG','Provider or task configuration needs attention')
   except Exception:
    log.warning('%s task failed; inspect credentials, entitlement and schema',name)
    try:health(store,name,'ERROR','Task failed; check provider access and migration')
    except Exception:pass
   last[name]=time.monotonic()
   return True
  try:
   task('earnings',1800,lambda:refresh_earnings(store,utcnow()))
   task('personal_positions',30,lambda:refresh_positions(store,utcnow()))
   if os.getenv('FINNHUB_API_KEY'):
    for req in store.call('POST','rpc/kst_claim_data_requests',data={}):
     try:
      refresh_company(store,req['symbol'],utcnow());enrich_earnings(store,req['symbol'],utcnow());store.patch('kst_data_requests',req['id'],{'status':'DONE'})
     except Exception:store.patch('kst_data_requests',req['id'],{'status':'ERROR' if req['attempts']>=3 else 'PENDING'})
    symbols=[]
    for s in os.getenv('STOCK_SYMBOLS','AAPL,MSFT,NVDA,TSLA,AMD,AMZN,META,GOOGL,SOFI,HOOD').split(',')[:40]:
     try:symbols.append(ticker(s))
     except ValueError:pass
    if symbols:
     symbol=symbols[rotation%len(symbols)]
     if task('company_news',60,lambda:refresh_company(store,symbol,utcnow())):rotation+=1
   else:health(store,'company_news','CONFIG','Configure FINNHUB_API_KEY for ticker-specific news')
   def research():
    from .research import cycle
    cycle(store,utcnow())
   task('research',300,research)
   if os.getenv('BACKUP_ENABLED','false')=='true':
    def backup():
     from .backup import backup as create_backup
     create_backup()
    task('backup',86400,backup)
   task('monitor',30,lambda:monitor(store,utcnow()))
  except Exception:log.warning('Pro worker loop interrupted; will retry')
  time.sleep(30)
if __name__=='__main__':logging.basicConfig(level=logging.INFO);run()
