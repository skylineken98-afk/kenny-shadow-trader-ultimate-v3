"""Run as an ADDITIONAL Railway service: python -m kst_options.worker."""
import logging,os,time,uuid
from datetime import timedelta
from .engine import utcnow,stamp,parse,NY,BUDGETS,candidate,deadline,mark,num,requested_choices,context_label,affordable
from .store import Store
from .provider import Provider
from .universe import universe,diverse_choices,rotating_batch
from .learning import active,train
log=logging.getLogger('kst_options')
def track(store,provider,now):
 # Track separately from scanning, including all open lots, not a capped latest subset.
 fee=num(os.getenv('OPTIONS_ROUND_TRIP_FEE','0'))
 if fee is None or fee<0:raise ValueError('OPTIONS_ROUND_TRIP_FEE must be finite and nonnegative')
 offset=0;open_rows=[]
 while True:
  page=store.rows('kst_option_signals',state='eq.OPEN',feed='eq.'+provider.feed,order='created_at.asc,id.asc',limit=500,offset=offset)
  open_rows.extend(page)
  if len(page)<500:break
  offset+=500
 contracts=list(dict.fromkeys(s['contract'] for s in open_rows));quotes=provider.quotes(contracts) if contracts else {}
 for s in open_rows:
  if now>parse(s['due_at'])+timedelta(minutes=30):
   store.patch('kst_option_signals',s['id'],{'state':'UNRESOLVED','closed_at':stamp(now)});continue
  update=mark(s,quotes.get(s['contract'],{}),now,float(s.get('fee_estimate',fee)))
  if update:
   store.insert('kst_option_marks',{'id':str(uuid.uuid4()),'signal_id':s['id'],'observed_at':stamp(now),'quote_at':update['last_quote_at'],'bid':update['last_bid'],'ask':quotes[s['contract']]['ap'],'estimated_pl':update['estimated_pl'],'estimated_return':update['estimated_return']},ignore=True)
   store.patch('kst_option_signals',s['id'],update)
def publish_request_choice(store,c,req,now,fee,version):
 # Each requested recommendation keeps its own immutable price/time baseline.
 # A prior scheduled signal for the same contract may have a different entry.
 ident=str(uuid.uuid5(uuid.NAMESPACE_URL,'kst-request:'+req['id']+':'+c['contract']))
 row=dict(c,id=ident,created_at=stamp(now),batch_id=str(uuid.uuid5(uuid.NAMESPACE_URL,req['id'])),budget=req['budget'],fee_estimate=fee,model_version=version,due_at=stamp(deadline(c,now)),state='OPEN')
 store.insert('kst_option_signals',row,ignore=True)
 saved=store.rows('kst_option_signals',id='eq.'+ident,limit=1)[0]
 return {**{k:saved.get(k) for k in c},'signal_id':ident,'fee_estimate':saved['fee_estimate'],'model_version':saved['model_version'],'requested_at':req['created_at']}

def scan(store,provider,now):
 started=now
 weights,version=active(store);day=now.astimezone(NY).date();candidates={};errors=0
 all_symbols=universe()
 cadence=max(300,int(os.getenv('OPTIONS_SCAN_SECONDS','300')))
 symbols=rotating_batch(all_symbols,started,int(os.getenv('OPTIONS_UNIVERSE_BATCH','12')),cadence)
 # No silent fallback from OPRA to indicative. Index coverage is provider dependent.
 for symbol in symbols:
  for lo,hi in [(day,day+timedelta(days=45)),(day+timedelta(days=270),day+timedelta(days=730))]:
   try:
    for contract,snapshot in provider.chain(symbol,lo,hi):
     quote_now=utcnow()
     c=candidate(contract,snapshot,quote_now,provider.feed,weights) or candidate(contract,snapshot,quote_now,provider.feed,weights,relaxed=True)
     if c:candidates[contract]=c
   except Exception as exc:errors+=1;log.warning('Chain %s: %s; HTTP %s',symbol,type(exc).__name__,getattr(exc,'status_code','unavailable'))
 now=utcnow()
 candidates={k:c for k,c in candidates.items() if 0<=(now-parse(c['quote_at'])).total_seconds()<=300}
 for symbol in symbols:
  setups=store.rows('ultimate_signals',symbol='eq.'+symbol,select='created_at,status,side',order='created_at.desc',limit=1)
  setup=setups[0] if setups else None
  for c in candidates.values():
   if c['underlying']==symbol:
    c['context_label']=context_label(c,setup,now);c['context_at']=setup.get('created_at') if setup else None
 fee=num(os.getenv('OPTIONS_ROUND_TRIP_FEE','0'))
 if fee is None or fee<0:raise ValueError('Invalid fee estimate')
 batch=str(uuid.uuid4());rows=[]
 # Do not reset an open contract's entry each cycle or duplicate its training labels.
 existing=set();offset=0
 while True:
  page=store.rows('kst_option_signals',select='contract,category,budget',state='eq.OPEN',feed='eq.'+provider.feed,order='created_at.asc,id.asc',limit=500,offset=offset)
  existing.update((r['contract'],r['category'],float(r['budget'])) for r in page)
  if len(page)<500:break
  offset+=500
 for cat in ('0DTE','Swings','LEAPS'):
  for budget in BUDGETS:
   choices=diverse_choices((c for c in candidates.values() if c['quality_label']=='QUALIFIED' and c['category']==cat and affordable(c['entry_ask'],budget,fee)),3)
   for c in choices:
    if (c['contract'],cat,float(budget)) in existing:continue
    rows.append(dict(c,id=str(uuid.uuid4()),created_at=stamp(now),batch_id=batch,budget=budget,fee_estimate=fee,model_version=version,due_at=stamp(deadline(c,now)),state='OPEN'))
 if rows:store.insert('kst_option_signals',rows)
 # Fulfill only requests queued before this scan began. Later requests wait for a new scan.
 requests=store.rows('kst_signal_requests',status='eq.PENDING',created_at='lte.'+stamp(started),order='created_at.asc',limit=100)
 for req in requests:
  choices=requested_choices(candidates.values(),req['category'],req['budget'],fee);published=[]
  for c in choices:
   published.append(publish_request_choice(store,c,req,now,fee,version))
  message=f'{len(published)} fresh contracts found; '+('three ranked ideas returned.' if len(published)==3 else 'fewer than three valid quotes available; no contracts invented.')
  if errors:message+=' Some chain requests failed; results are incomplete.'
  store.patch('kst_signal_requests',req['id'],{'status':'DONE','completed_at':stamp(utcnow()),'results':published,'message':message})
 store.health('DEGRADED' if errors else 'OK',f'{len(symbols)}/{len(all_symbols)} symbols scanned this cycle; {len(candidates)} qualifying contracts; {len(rows)} new research records; {errors} failed chain requests. Feed: {provider.feed}. No orders submitted.')
def run():
 store=Store();provider=None;last_scan=0;last_news=0;last_proxy=0;last_stocks=0
 while True:
  try:
   now=utcnow()
   from kst_pro.ops import beat
   beat(store,'options')
   if time.monotonic()-last_news>=max(60,int(os.getenv('NEWS_POLL_SECONDS','300'))):
    try:
     from .news import refresh
     refresh(store,now);last_news=time.monotonic()
    except Exception:log.warning('News refresh failed; check feed access and schema')
   if time.monotonic()-last_proxy>=60:
    try:
     from .proxy import refresh as refresh_proxy
     refresh_proxy(store,now);last_proxy=time.monotonic()
    except Exception:
     log.warning('SPY/SPX proxy unavailable; check stock feed access and reference history')
     store.call('POST','kst_market_proxy',data={'id':'SPX','updated_at':stamp(now),'payload':{'status':'UNAVAILABLE','estimated_spx':None,'note':'SPY data or matched SPX/SPY reference unavailable. No estimate generated.'}},prefer='resolution=merge-duplicates,return=minimal')
   if os.getenv('STOCK_RESEARCH_ENABLED','true').lower()=='true' and time.monotonic()-last_stocks>=60:
    try:
     from .stocks import refresh as refresh_stocks
     refresh_stocks(store,utcnow())
    except Exception:
     log.warning('Stock research unavailable; check stocks.sql and stock data access')
     try:store.call('POST','kst_options_health',data={'id':'stocks','updated_at':stamp(utcnow()),'status':'ERROR','message':'Stock research failed; check stock migration, keys and entitlement.'},prefer='resolution=merge-duplicates,return=minimal')
     except Exception:pass
    last_stocks=time.monotonic()
   if provider is None:provider=Provider()
   track(store,provider,now)
   if os.getenv('OPTIONS_PAPER_AI_ENABLED','true').lower()=='true':
    from .progress import cycle as paper_cycle
    paper_cycle(store,provider,utcnow())
   pending=store.rows('kst_signal_requests',status='eq.PENDING',created_at='gte.'+stamp(now-timedelta(minutes=10)),order='created_at.asc',limit=1)
   if pending or time.monotonic()-last_scan>=max(300,int(os.getenv('OPTIONS_SCAN_SECONDS','300'))):
    scan(store,provider,now);train(store);last_scan=time.monotonic()
    if os.getenv('OPTIONS_PAPER_AI_ENABLED','true').lower()=='true':paper_cycle(store,provider,utcnow(),allow_open=True)
  except Exception as exc:
   try:
    from kst_pro.ops import beat
    beat(store,'options','ERROR','Options cycle failed; check provider access and schema')
   except Exception:pass
   log.error('Options cycle failed (%s); check migration, credentials and provider entitlement',type(exc).__name__)
   try:
    store.health('ERROR','Options cycle failed; check Railway logs, schema and data entitlements.')
    pending=store.rows('kst_signal_requests',status='eq.PENDING',order='created_at.asc',limit=100)
    for req in pending:store.patch('kst_signal_requests',req['id'],{'status':'ERROR','completed_at':stamp(utcnow()),'message':'Scanner failed; verify credentials, market-data access and schema.'})
   except Exception:pass
  time.sleep(max(30,int(os.getenv('OPTIONS_TRACK_SECONDS','60'))))
if __name__=='__main__':logging.basicConfig(level=logging.INFO);run()
