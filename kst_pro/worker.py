"""Independent main-KST scheduled research collectors; no broker submission."""
import logging,os
from kst_options.engine import utcnow
from .collection import start_jobs

def run():
 from .market import refresh_earnings,refresh_company,ticker
 from .positions import refresh as positions
 from .research import cycle
 from .ops import monitor
 from .history import collect
 symbols=[ticker(s) for s in os.getenv('STOCK_SYMBOLS','AAPL,MSFT,NVDA,TSLA,AMD,AMZN,META,GOOGL,SOFI,HOOD').split(',')[:40]]
 rotation=[0]
 def company(store):
  if not os.getenv('FINNHUB_API_KEY'):raise ValueError('FINNHUB_API_KEY required')
  sym=symbols[rotation[0]%len(symbols)];count=refresh_company(store,sym,utcnow());rotation[0]+=1
  for req in store.call('POST','rpc/kst_claim_data_requests',data={}):
   try:
    from .market import enrich_earnings
    refresh_company(store,req['symbol'],utcnow());enrich_earnings(store,req['symbol'],utcnow());store.patch('kst_data_requests',req['id'],{'status':'DONE'})
   except Exception:store.patch('kst_data_requests',req['id'],{'status':'ERROR' if req['attempts']>=3 else 'PENDING'})
  return {'rows_saved':count,'message':sym+' company news checked and available records saved'}
 def earnings(store):
  count=refresh_earnings(store,utcnow())
  return {'rows_saved':count,'message':f'{count} provider-reported earnings records saved; schedules need issuer confirmation'}
 def research(store):
  report=cycle(store,utcnow())
  return {'status':'COLLECTING' if report['state']=='COLLECTING' else 'OK','message':report.get('reason','Research evaluation saved; no automatic promotion')}
 jobs=[('earnings',1800,earnings),('personal_positions',60,lambda s:positions(s,utcnow())),
       ('company_news',120,company),('research',600,research),
       ('historical_trendlines',3600,lambda s:collect(s,utcnow())),
       ('monitor',60,lambda s:monitor(s,utcnow()))]
 if os.getenv('BACKUP_ENABLED','false')=='true':
  def backup(store):
   from .backup import backup as create
   create()
  jobs.append(('backup',86400,backup))
 start_jobs(jobs,'pro')
if __name__=='__main__':logging.basicConfig(level=logging.INFO);run()
