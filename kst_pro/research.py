"""Entry-known feature capture and chronological research challengers.
No model-weight training, automatic trading-rule changes, or profit claims.
"""
import hashlib,math,uuid
from datetime import timedelta
import numpy as np
from kst_options.engine import parse,stamp,num,NY

def entry_features(signal,news,setup):
 known=parse(signal['created_at']);risk=signal.get('risk_snapshot') or {};g=risk.get('greeks') or {}
 try:valid_risk=parse(risk['observed_at'])<=known
 except (KeyError,ValueError,TypeError):valid_risk=False
 headlines=0
 for item in news:
  try:
   if parse(item.get('first_seen_at') or item['fetched_at'])<=known and known-timedelta(hours=24)<=parse(item['published_at'])<=known:headlines+=1
  except (KeyError,ValueError,TypeError):pass
 regime=None;rvol=None
 try:
  if parse(setup['created_at'])<=known and (known-parse(setup['created_at'])).total_seconds()<=5400:
   frame=(setup.get('details') or {}).get('frames',{}).get('5m') or {};rvol=num(frame.get('rvol'));regime=1 if frame.get('trend')=='BULLISH' else -1 if frame.get('trend')=='BEARISH' else 0
 except (KeyError,ValueError,TypeError):pass
 ask=num(signal.get('entry_ask'));bid=num(signal.get('entry_bid'))
 return [(ask-bid)/((ask+bid)/2) if ask and bid is not None else None]+[num(g.get(k)) if valid_risk else None for k in ('delta','gamma','theta','vega','rho')]+[num(risk.get('implied_volatility')) if valid_risk else None,regime,rvol,min(headlines,20)]

def replay(signal,marks,stop=.30,trail_start=.20,giveback=.5,slippage=.01):
 entry=float(signal['entry_ask'])+slippage;fee=float(signal.get('fee_estimate') or 0);start=parse(signal['quote_at']);due=parse(signal['due_at']);peak=0.;last=None;previous=start
 for mark in sorted(marks,key=lambda r:r['quote_at']):
  t=parse(mark['quote_at']);bid=num(mark.get('bid'))
  if t<=previous or t<=start or t>due+timedelta(minutes=30) or bid is None or bid<0:continue
  previous=t;ret=((max(0,bid-slippage)-entry)*100-fee)/(entry*100);peak=max(peak,ret);last=(ret,t)
  if ret<=-stop:return {'return':ret,'reason':'OBSERVED_STOP'}
  if peak>=trail_start and ret<=peak*giveback:return {'return':ret,'reason':'TRAILING_GIVEBACK'}
  if t>=due:return {'return':ret,'reason':'MEASUREMENT_DEADLINE'}
 return None # incomplete horizon is not a fabricated close

def split_days(rows):
 days=sorted({parse(r['created_at']).astimezone(NY).date() for r in rows})
 if len(days)<10:return None
 a=days[int(len(days)*.6)];b=days[int(len(days)*.8)]
 groups=[[],[],[]]
 for r in rows:
  day=parse(r['created_at']).astimezone(NY).date();end=parse(r['closed_at']).astimezone(NY).date()
  if day<a and end<a:groups[0].append(r)
  elif a<=day<b and end<b:groups[1].append(r)
  elif day>=b:groups[2].append(r)
 return groups if all(len(g)>=20 for g in groups) else None

def fit(rows,ridge):
 x=np.array([[np.nan if v is None else v for v in r['rich_features']] for r in rows],float);y=np.array([max(-1,min(2,r['outcome_return'])) for r in rows],float)
 means=np.array([np.mean(c[np.isfinite(c)]) if np.isfinite(c).any() else 0 for c in x.T]);x=np.where(np.isfinite(x),x,means);scales=np.std(x,axis=0);scales=np.where(scales>1e-8,scales,1);x=(x-means)/scales
 x=np.column_stack([np.ones(len(x)),x]);penalty=np.eye(x.shape[1])*ridge;penalty[0,0]=0
 weights=np.linalg.solve(x.T@x+penalty,x.T@y)
 return {'means':means.tolist(),'scales':scales.tolist(),'weights':weights.tolist(),'ridge':ridge}

def predict(row,model):
 values=[model['means'][i] if v is None or not math.isfinite(v) else v for i,v in enumerate(row['rich_features'])]
 return model['weights'][0]+sum((v-model['means'][i])/model['scales'][i]*model['weights'][i+1] for i,v in enumerate(values))

def selection_return(rows,key):
 # Rank within each day; never compare a later day's opportunities to earlier ones.
 days={}
 for row in rows:days.setdefault(row['created_at'][:10],[]).append(row)
 selected=[]
 for group in days.values():selected.extend(sorted(group,key=key,reverse=True)[:max(1,len(group)//3)])
 return float(np.mean([max(-1,min(2,r['outcome_return'])) for r in selected]))

def evaluate(rows):
 unique={}
 for r in sorted(rows,key=lambda r:r['created_at']):
  if r.get('feed')!='opra' or r.get('state')!='CLOSED' or num(r.get('outcome_return')) is None or len(r.get('rich_features',[]))!=10:continue
  unique.setdefault((r['contract'],parse(r['created_at']).astimezone(NY).date()),r)
 rows=list(unique.values());groups=split_days(rows)
 if len(rows)<100 or not groups:return {'state':'COLLECTING','independent_contract_days':len(rows),'reason':'Need at least 100 eligible contract-days across 10 days and 20 purged samples in each chronological partition'}
 train,validation,test=groups;models=[fit(train,r) for r in (1.,10.,100.)]
 chosen=max(models,key=lambda m:selection_return(validation,lambda r:predict(r,m)))
 scores={}
 for name,group in [('validation',validation),('test',test)]:scores[name]={'baseline':selection_return(group,lambda r:r['score']),'challenger':selection_return(group,lambda r:predict(r,chosen))}
 passed=all(v['challenger']>v['baseline']+.02 for v in scores.values())
 strategies=[(.30,.20,.5),(.20,.20,.5),(.30,.30,.5),(.30,.20,.7)]
 def utility(group,strategy):
  values=[replay(r,r.get('marks',[]),*strategy) for r in group];values=[v['return'] for v in values if v is not None]
  return float(np.mean(values)) if len(values)>=20 else None
 base=strategies[0];chosen_exit=max(strategies,key=lambda p:utility(train,p) if utility(train,p) is not None else -999)
 exit_scores={name:{'baseline':utility(group,base),'challenger':utility(group,chosen_exit)} for name,group in [('validation',validation),('test',test)]}
 return {'state':'RESEARCH_PASS' if passed else 'REJECTED','independent_contract_days':len(rows),'partition_counts':[len(g) for g in groups],'ranking':scores,'model':chosen,'exit_candidate':chosen_exit,'exit_results':exit_scores,'exit_pass':all(v['baseline'] is not None and v['challenger'] is not None and v['challenger']>v['baseline']+.02 for v in exit_scores.values()),'limitations':'Retrospective selection bias, correlated symbols, finite polling, missing features and small samples remain. One-cent premium slippage each way plus configured fees. No production promotion or performance guarantee. Validate prospectively before adoption.'}

def cycle(store,now):
 recent=store.rows('kst_option_signals',feed='eq.opra',order='created_at.desc',limit=250)
 captured={r['id']:r for r in store.rows('kst_research_samples',order='created_at.desc',limit=500)}
 added=0
 for s in recent:
  if s['id'] in captured:continue
  if added>=25:break
  added+=1
  news=store.rows('kst_company_news',symbol='eq.'+s['underlying'],first_seen_at='lte.'+s['created_at'],published_at='lte.'+s['created_at'],order='published_at.desc',limit=20)
  setups=store.rows('ultimate_signals',symbol='eq.'+s['underlying'],created_at='lte.'+s['created_at'],order='created_at.desc',limit=1)
  record={'id':s['id'],'created_at':s['created_at'],'entry_known_at':s['created_at'],'contract':s['contract'],'features':entry_features(s,news,setups[0] if setups else {})}
  store.insert('kst_research_samples',record,ignore=True);captured[s['id']]=record
 rows=[{**s,'rich_features':captured[s['id']]['features'],'marks':[]} for s in recent if s['state']=='CLOSED' and s['id'] in captured]
 if len(rows)>=100:
  by_id={s['id']:s for s in rows};ids=list(by_id)
  for i in range(0,len(ids),100):
   offset=0
   while True:
    marks=store.rows('kst_option_marks',signal_id='in.('+','.join(ids[i:i+100])+')',order='quote_at.asc,id.asc',limit=10000,offset=offset)
    for mark in marks:
     if mark['signal_id'] in by_id:by_id[mark['signal_id']]['marks'].append(mark)
    if len(marks)<10000:break
    offset+=10000
 report=evaluate(rows);digest=hashlib.sha256('|'.join(sorted(r['id'] for r in rows)).encode()).hexdigest();ident=str(uuid.uuid5(uuid.NAMESPACE_URL,'research-r5:'+digest))
 store.insert('kst_research_reports',{'id':ident,'state':report['state'],'report':report},ignore=True)
 return report

