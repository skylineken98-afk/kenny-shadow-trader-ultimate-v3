"""Independent bounded collector loops. Health is evidence, never a price quote."""
import logging,time,threading,os
from datetime import datetime,timezone
from kst_options.store import Store
log=logging.getLogger('kst.collection')

def stamp():return datetime.now(timezone.utc).isoformat()
def safe_error(exc):
 # Never stringify arbitrary provider errors: URLs can contain credentials.
 from kst_options.store import DatabaseError
 if isinstance(exc,DatabaseError):return str(exc)
 if isinstance(exc,RuntimeError) and str(exc).startswith('Database '):return str(exc)
 code=getattr(exc,'status_code',None)
 return type(exc).__name__+(f' HTTP {code}' if isinstance(code,int) else '')

def save(store,name,**data):
 store.call('POST','kst_collection_status',data={'id':name,**data},prefer='resolution=merge-duplicates,return=minimal')

def loop(name,interval,fn,stop=None):
 store=Store();failures=0
 while stop is None or not stop.is_set():
  start=time.monotonic();attempt=stamp()
  try:
   # A monitoring outage must not prevent the fetch/save operation itself.
   try:save(store,name,last_attempt_at=attempt,interval_seconds=interval,status='RUNNING')
   except Exception:log.warning('%s status write unavailable',name)
   result=fn(store) or {}
   if not isinstance(result,dict):result={}
   failures=0
   status=result.get('status','OK');message=result.get('message','Collector completed; see dataset timestamps')
   fields=dict(last_finished_at=stamp(),status=status,message=message,consecutive_failures=0)
   if status in ('OK','COLLECTING'):
    fields['last_success_at']=stamp()
   if result.get('data_as_of'):fields['data_as_of']=result['data_as_of']
   if result.get('rows_saved') is not None:fields['rows_saved']=result['rows_saved']
   save(store,name,**fields)
   from .ops import health
   health(store,name,status,message)
   log.info('%s %s',name,status)
  except Exception as exc:
   failures+=1;message=safe_error(exc)
   log.error('%s failed: %s',name,message)
   try:
    save(store,name,last_finished_at=stamp(),status='CONFIG' if isinstance(exc,ValueError) else 'ERROR',message=message,consecutive_failures=failures)
    from .ops import health
    health(store,name,'ERROR',message)
   except Exception:log.warning('%s failure status unavailable',name)
  # Back off repeated failures, never hot-loop a database/provider outage.
  delay=max(1, max(interval,min(900,30*2**min(failures,5)))- (time.monotonic()-start))
  if stop is not None:stop.wait(delay)
  else:time.sleep(delay)

def start_jobs(jobs,service):
 threads=[]
 for name,interval,fn in jobs:
  t=threading.Thread(target=loop,args=(name,interval,fn),name=name,daemon=True);t.start();threads.append(t)
 store=Store()
 while True:
  # Do not report a dead scheduler as healthy. Railway restarts the process.
  if any(not t.is_alive() for t in threads):raise RuntimeError('Collector thread stopped')
  try:
   from .ops import beat
   beat(store,service,message='Scheduler alive; collector and data freshness tracked separately')
  except Exception:log.warning('%s scheduler heartbeat unavailable',service)
  time.sleep(60)

_clock_cache={}
_clock_lock=threading.Lock()
def market_open():
 import requests
 with _clock_lock:
  if time.monotonic()-_clock_cache.get('checked',-1e9)<60:return _clock_cache['open']
  response=requests.get('https://paper-api.alpaca.markets/v2/clock',headers={
   'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'].strip(),
   'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET'].strip()},timeout=(5,15))
  if not response.ok:
   from kst_options.provider import ProviderError
   raise ProviderError(response.status_code)
  value=response.json().get('is_open')
  if not isinstance(value,bool):raise ValueError('Market clock missing is_open')
  _clock_cache.update(checked=time.monotonic(),open=value)
  return value

def during_session(fn):
 def task(store):
  if not market_open():return {'status':'MARKET_CLOSED','message':'Exchange clock reports closed; no live quote or new entry claimed.'}
  return fn(store)
 return task
