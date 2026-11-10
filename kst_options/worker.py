"""Run as an ADDITIONAL Railway service: python -m kst_options.worker."""
import logging,os,time,uuid
from datetime import timedelta
from .engine import utcnow,stamp,parse,NY,BUDGETS,candidate,deadline,mark,num,requested_choices,context_label,affordable
from .store import Store
from .provider import Provider
from .universe import universe,diverse_choices,rotating_batch,enrichment_shortlist,scan_symbols,priority_index_symbols
from .evidence_ranking import activity,rank_with_evidence,sector_returns
from .learning import active,train
log=logging.getLogger('kst_options')
def track(store,provider,now):
 # Track separately from scanning, including all open lots, not a capped latest subset.
 fee=num(os.getenv('OPTIONS_ROUND_TRIP_FEE','0'))
 if fee is None or fee<0:raise ValueError('OPTIONS_ROUND_TRIP_FEE must be finite and nonnegative')
 offset=0;open_rows=[]
 while True:
  page=store.rows('kst_option_signals',state='eq.OPEN',feed='eq.'+provider.feed,order='created_at.asc,id.asc',limit=100,offset=offset)
  open_rows.extend(page)
  if len(page)<100:break
  offset+=100
 contracts=list(dict.fromkeys(s['contract'] for s in open_rows));quotes=provider.quotes(contracts) if contracts else {}
 for s in open_rows:
  if now>parse(s['due_at'])+timedelta(minutes=30):
   store.patch('kst_option_signals',s['id'],{'state':'UNRESOLVED','closed_at':stamp(now)});continue
  update=mark(s,quotes.get(s['contract'],{}),now,float(s.get('fee_estimate',fee)))
  if update:
   store.call('POST','kst_option_marks',params={'on_conflict':'signal_id,quote_at'},data={'id':str(uuid.uuid4()),'signal_id':s['id'],'observed_at':stamp(now),'quote_at':update['last_quote_at'],'bid':update['last_bid'],'ask':quotes[s['contract']]['ap'],'estimated_pl':update['estimated_pl'],'estimated_return':update['estimated_return']},prefer='resolution=ignore-duplicates,return=minimal')
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
 started=now;scan_deadline=time.monotonic()+180
 weights,version=active(store);day=now.astimezone(NY).date();candidates={};errors=0
 all_symbols=universe()
 cadence=max(300,int(os.getenv('OPTIONS_SCAN_SECONDS','300')))
 pending=store.rows('kst_signal_requests',status='eq.PENDING',created_at='lte.'+stamp(started),order='created_at.asc',limit=100)
 daily_window=now.astimezone(NY).hour*60+now.astimezone(NY).minute>=945
 rotating=rotating_batch(all_symbols,started,min(24,max(1,int(os.getenv('OPTIONS_UNIVERSE_BATCH','12')))),cadence)
 priority=priority_index_symbols()
 symbols=scan_symbols(rotating,priority)
 # Explicit user scan requests must check the full configured universe,
 # not only the scheduled rotating slice. Preserve default rotation otherwise.
 if pending:
  symbols=scan_symbols(all_symbols,priority)
 # SPX is attempted on every scan independently of the rotating stock basket.
 # No silent feed fallback: unavailable index-chain quotes are never invented.
 spx_contracts=0
 for symbol in symbols:
  if time.monotonic()>scan_deadline:
   errors+=1;log.warning('Scan time budget reached; remaining basket deferred');break
  windows=[(day,day+timedelta(days=7))] if symbol=='SPX' else [(day,day+timedelta(days=45)),(day+timedelta(days=270),day+timedelta(days=730))]
  for lo,hi in windows:
   try:
    for contract,snapshot in provider.chain(symbol,lo,hi):
     quote_now=utcnow()
     c=candidate(contract,snapshot,quote_now,provider.feed,weights) or candidate(contract,snapshot,quote_now,provider.feed,weights,relaxed=True)
     if c:
      if symbol=='SPX':
       # No SPX entries without a verified underlying and price-structure feed.
       # Exclude index candidates from the publishing pool entirely for now.
       spx_contracts+=1
       continue
      candidates[contract]=c
   except Exception as exc:errors+=1;log.warning('Chain %s: %s; HTTP %s',symbol,type(exc).__name__,getattr(exc,'status_code','unavailable'))
 now=utcnow()
 candidates={k:c for k,c in candidates.items() if 0<=(now-parse(c['quote_at'])).total_seconds()<=300}
 for symbol in symbols:
  setups=store.rows('ultimate_signals',symbol='eq.'+symbol,select='created_at,status,side,details',order='created_at.desc',limit=1)
  setup=setups[0] if setups else None
  for c in candidates.values():
   if c['underlying']==symbol:
    c['context_label']=context_label(c,setup,now);c['context_at']=setup.get('created_at') if setup else None
 # Enrich a bounded shortlist rather than querying metadata for every chain item.
 # All enrichment is read-only. No absent metric is treated as confirmed 0 flow.
 shortlist=enrichment_shortlist(candidates.values(),limit=12)
 sector_data={}
 try:sector_data=sector_returns(symbols,now)
 except Exception:log.warning('Sector return research unavailable')
 day_volumes={}
 if shortlist:
  try:day_volumes=provider.daily_volumes([c['contract'] for c in shortlist],now)
  except Exception as exc:log.warning('Option bar volume data unavailable (%s; HTTP %s); ranking remains structural where absent',type(exc).__name__,getattr(exc,'status_code','unavailable'))
 # Preserve sampled contract-volume evidence separately from OI and quote sizes.
 from .strike_volume import strike_activity
 observed_strikes=strike_activity([c['contract'] for c in shortlist],day_volumes,
                                  as_of=stamp(now),
                                  universe_label='enrichment shortlist, not all market contracts')
 try:
  store.call('POST','kst_options_strike_activity',
       data={'id':'latest','observed_at':stamp(now),'payload':observed_strikes},
       prefer='resolution=merge-duplicates,return=minimal')
 except Exception:
  log.warning('Strike-volume report not stored; apply kst_options/market_pulse.sql')
 for c in shortlist:
  sym=c['contract']
  bar=day_volumes.get(sym) or {}
  oi=None
  try:oi=provider.open_interest(sym,now)
  except Exception:log.warning('Open interest unavailable for %s',sym)
  # Do not describe previous-session volume as live current session volume.
  if bar and not bar.get('current_session'):bar={}
  a=activity(contract_volume=bar.get('volume'),
             open_interest=(oi or {}).get('open_interest'),
             historical_volume=bar.get('historical_volume'),
             as_of=bar.get('as_of'),oi_date=(oi or {}).get('date'),
             source='Alpaca option daily aggregates / contract metadata; feed and entitlements apply')
  updated=rank_with_evidence(c,a,sector_data.get(c['underlying']))
  candidates[sym]=updated
 # Enrichment can take time. Never publish an entry whose quote has aged out.
 now=utcnow()
 candidates={k:c for k,c in candidates.items() if 0<=(now-parse(c['quote_at'])).total_seconds()<=60}
 fee=num(os.getenv('OPTIONS_ROUND_TRIP_FEE','0'))
 if fee is None or fee<0:raise ValueError('Invalid fee estimate')
 batch=str(uuid.uuid4());rows=[]
 # Do not reset an open contract's entry each cycle or duplicate its training labels.
 existing=set();offset=0
 while True:
  page=store.rows('kst_option_signals',select='contract,category,budget',state='eq.OPEN',feed='eq.'+provider.feed,order='created_at.asc,id.asc',limit=100,offset=offset)
  existing.update((r['contract'],r['category'],float(r['budget'])) for r in page)
  if len(page)<100:break
  offset+=100
 for cat in ('0DTE','Swings','LEAPS'):
  for budget in BUDGETS:
   choices=diverse_choices((c for c in candidates.values() if c['quality_label']=='QUALIFIED' and c['category']==cat and affordable(c['entry_ask'],budget,fee)),3)
   for c in choices:
    if (c['contract'],cat,float(budget)) in existing:continue
    rows.append(dict(c,id=str(uuid.uuid4()),created_at=stamp(now),batch_id=batch,budget=budget,fee_estimate=fee,model_version=version,due_at=stamp(deadline(c,now)),state='OPEN'))
 if rows:store.insert('kst_option_signals',rows)
 # Fulfill only requests queued before this scan began. Later requests wait for a new scan.
 requests=pending
 for req in requests:
  choices=requested_choices(candidates.values(),req['category'],req['budget'],fee);published=[]
  for c in choices:
   published.append(publish_request_choice(store,c,req,now,fee,version))
  message=f'{len(published)} fresh contracts found; '+('three ranked ideas returned.' if len(published)==3 else 'fewer than three valid quotes available; no contracts invented.')
  if errors:message+=' Some chain requests failed; results are incomplete.'
  store.patch('kst_signal_requests',req['id'],{'status':'DONE','completed_at':stamp(utcnow()),'results':published,'message':message})
 spx_note=('SPX index options scanned as non-actionable watchlist; verified cash-index feed and structure triggers not connected.' if spx_contracts else 'SPX index chain unavailable or no fresh eligible quotes; no SPX signals fabricated.') if priority else 'SPX index scan disabled by configuration.'
 store.health('DEGRADED' if errors or priority else 'OK',f'{len(rotating)}/{len(all_symbols)} rotating symbols plus {len(priority)} priority indexes attempted; {len(candidates)} quote-qualified research candidates; {len(rows)} new research records; {errors} failed chain requests. {spx_note} Feed: {provider.feed}. No orders submitted.')
def run():
 from kst_pro.collection import start_jobs,during_session
 def news_job(store):
  from .news import refresh
  count=refresh(store,utcnow())
  if not count:return {'status':'DEGRADED','message':'No recent news returned; inspect feed health'}
  return {'rows_saved':count,'message':f'{count} headline records saved; links only'}
 def options_job(store):
  scan(store,Provider(),utcnow())
  row=store.rows('kst_options_health',id='eq.options',limit=1)
  return {'status':row[0]['status'],'message':row[0]['message']} if row else {'status':'ERROR','message':'No scan completion evidence'}
 def track_job(store):track(store,Provider(),utcnow())
 def proxy_job(store):
  from .proxy import refresh
  refresh(store,utcnow())
 def stocks_job(store):
  from .stocks import refresh
  refresh(store,utcnow())
 def pulse_job(store):
  from .market_pulse import refresh
  report=refresh(store,utcnow())
  return {'rows_saved':report['coverage']['valid'],'data_as_of':report['as_of'],'message':'Measured price/volume watchlist; not institutional fund flows'}
 def memory_job(store):
  from .progress import remember
  remember(store)
 def paper_job(store):
  from .progress import cycle
  cycle(store,Provider(),utcnow(),allow_open=True)
 jobs=[('news',300,news_job),('options',max(300,int(os.getenv('OPTIONS_SCAN_SECONDS','300'))),during_session(options_job)),
       ('option_tracking',max(30,int(os.getenv('OPTIONS_TRACK_SECONDS','60'))),during_session(track_job)),
       ('market_memory',600,memory_job),('market_proxy',60,during_session(proxy_job)),
       ('market_pulse',300,during_session(pulse_job))]
 if os.getenv('STOCK_RESEARCH_ENABLED','true').lower()=='true':jobs.append(('stocks',60,during_session(stocks_job)))
 if os.getenv('OPTIONS_PAPER_AI_ENABLED','true').lower()=='true':jobs.append(('paper_agents',15,during_session(paper_job)))
 # Training remains separate from quote collection and cannot block it.
 jobs.append(('option_learning',1800,lambda store:train(store)))
 start_jobs(jobs,'options')
if __name__=='__main__':logging.basicConfig(level=logging.INFO);run()
