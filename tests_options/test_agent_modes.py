from datetime import datetime,timezone
from unittest.mock import patch
from kst_options.progress import cycle

class Provider:
 feed='indicative'
 def quotes(self,contracts):
  return {c:{'bp':.49,'ap':.5,'as':10,'t':self.now.isoformat()} for c in contracts}
class Store:
 def __init__(self): self.opened=[];self.decisions=[];self.filters=None
 def rows(self,table,**kw):
  if table=='kst_agent_positions' or table=='ultimate_signals':return []
  if table=='kst_agent_accounts':return [{'agent':a,'cash':1000} for a in ['conservative','balanced','aggressive','challenge','daily_10pct_research']]
  if table=='kst_option_signals':
   self.filters=kw
   return [dict(id=c,contract=c,entry_ask=.5,fee_estimate=0,category=cat,expiration=exp,score=score,model_version='test',context_label='STRUCTURAL_ONLY') for c,cat,exp,score in [('swing','Swings','2026-11-20',99),('scalp','0DTE','2026-11-06',80)]]
  return []
 def insert(self,table,data,**kw):
  if table=='kst_agent_decisions':self.decisions.append(data)
 def call(self,method,path,data):
  self.opened.append(data);return {'action':'RESEARCH_OPEN','reason':'test simulation'}

def run(hour,minute):
 now=datetime(2026,11,6,hour,minute,tzinfo=timezone.utc)
 store=Store();provider=Provider();provider.now=now
 with patch('kst_options.progress.utcnow',return_value=now):cycle(store,provider,now,allow_open=True)
 return store

def test_aggressive_prefers_scalp_and_uses_indicative_feed_explicitly():
 store=run(15,0)
 assert store.filters['feed']=='eq.indicative'
 assert next(d for d in store.opened if d['p_agent']=='aggressive')['p_signal']=='scalp'
 assert not any(d['p_agent']=='conservative' for d in store.opened) # Risk cap retained

def test_daily_required_window_evaluates_affordable_structural_ideas():
 store=run(20,46)
 assert 'context_label' not in store.filters
 assert len(store.opened)==5

def test_closed_session_does_not_invent_mandatory_fill():
 store=run(22,0)
 assert store.opened==[]
 assert len(store.decisions)==5
 assert all('closed' in d['reason'] for d in store.decisions)
