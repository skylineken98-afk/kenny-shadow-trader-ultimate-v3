"""Bounded adaptive re-ranking, not an LLM or a profit guarantee.
Only OPRA observations with recorded horizon exits can teach this model.
"""
import uuid
from .engine import BASE,parse,stamp,utcnow,score
GRID=[BASE,[.4,.4,.2],[.7,.2,.1],[.3,.6,.1],[.3,.3,.4],[.5,.2,.3]]
def utility(rows,weights):
 # One contract-day observation, clipped to reduce outlier domination.
 ordered=sorted(rows,key=lambda r:score(r['features'],weights),reverse=True)
 selected=ordered[:max(1,len(ordered)//3)]
 return sum(max(-1,min(2,float(r['outcome_return']))) for r in selected)/len(selected)
def propose(rows,current=BASE):
 unique={}
 for r in sorted(rows,key=lambda r:r['created_at']):
  if r.get('quality_label','QUALIFIED')!='QUALIFIED':continue
  if r.get('feed') not in ('opra','actual','paper_opra') or r.get('state')!='CLOSED' or r.get('outcome_return') is None:continue
  if len(r.get('features',[]))!=3:continue
  unique.setdefault((r['contract'],r['created_at'][:10]),r)
 samples=list(unique.values())
 if len(samples)<100:return None
 cut=int(len(samples)*.8);hold=samples[cut:];boundary=parse(hold[0]['created_at'])
 # Purge labels unavailable at the beginning of the holdout period.
 train=[r for r in samples[:cut] if r.get('closed_at') and parse(r['closed_at'])<boundary]
 if len(train)<60 or len(hold)<20:return None
 challenger=max(GRID,key=lambda w:utility(train,w))
 before,after=utility(hold,current),utility(hold,challenger)
 accepted=challenger!=current and utility(train,challenger)>utility(train,current)+.01 and after>before+.02
 return {'weights':challenger if accepted else current,'state':'PROMOTED' if accepted else 'REJECTED','sample_count':len(samples),'trained_through':max(r['closed_at'] for r in samples),'report':{'training_count':len(train),'holdout_count':len(hold),'champion_holdout_return':before,'challenger_holdout_return':after,'challenger_weights':challenger,'scope':'chronological outcomes from the source recorded on this model','limitations':'Selection bias, correlated markets and small samples remain. No claim of profitability. One quote observation per polling interval.'}}
def active(store):
 rows=store.rows('kst_option_models',state='eq.PROMOTED',order='created_at.desc',limit=1)
 return (rows[0]['weights'],rows[0]['version']) if rows else (BASE,'baseline-v1')
def train(store):
 current,_=active(store)
 last=store.rows('kst_option_models',order='created_at.desc',limit=1)
 research=store.rows('kst_option_signals',state='eq.CLOSED',feed='eq.opra',order='created_at.desc',limit=5000)
 actual=store.rows('kst_trade_outcomes',order='created_at.desc',limit=5000)
 # Personal executed-trade history takes priority only once it passes the same sample gate.
 paper=store.rows('kst_agent_outcomes',order='created_at.desc',limit=5000)
 source='actual_imports' if propose(actual,current) else 'paper_opra' if propose(paper,current) else 'opra_research_estimates'
 rows=actual if source=='actual_imports' else paper if source=='paper_opra' else research
 if last and last[0].get('trained_through') and last[0].get('report',{}).get('source')==source:
  new=[r for r in rows if r.get('closed_at','')>last[0]['trained_through']]
  if len({(r['contract'],r['created_at'][:10]) for r in new})<50:return
 proposal=propose(rows,current)
 if proposal:
  proposal['report']['source']=source
  ident=str(uuid.uuid4());store.insert('kst_option_models',{'id':ident,'version':'adaptive-'+ident[:8],'created_at':stamp(utcnow()),**proposal})
