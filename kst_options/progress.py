"""Budget-constrained RESEARCH portfolios, not brokerage accounts or fills."""
from datetime import timedelta
from .engine import utcnow,stamp,num
AGENTS=['conservative','balanced','aggressive','challenge','daily_10pct_research']
def regime(signal):
 d=signal.get('details') or {};frames=d.get('frames') or {}
 trends=[(frames.get(k) or {}).get('trend') for k in ('4h','1h','5m')]
 if any(t is None for t in trends):return 'INSUFFICIENT_CONTEXT'
 if all(t=='BULLISH' for t in trends):return 'ALIGNED_UPTREND'
 if all(t=='BEARISH' for t in trends):return 'ALIGNED_DOWNTREND'
 return 'MIXED_TIMEFRAMES' # not proof of chop

def remember(store):
 # Source row IDs make repeated polling idempotent. No reconstructed history.
 signals=store.rows('ultimate_signals',order='created_at.desc',limit=500)
 if signals:store.insert('kst_market_memory',[{'id':s['id'],'created_at':s['created_at'],'symbol':s['symbol'],'regime':regime(s),'observation':{'status':s['status'],'side':s.get('side'),'frames':(s.get('details') or {}).get('frames',{}),'source':s.get('source')}} for s in signals],ignore=True)

def cycle(store,provider,now,allow_open=False):
 positions=store.rows('kst_agent_positions',state='eq.OPEN',order='opened_at.asc',limit=100)
 contracts=list(dict.fromkeys(p['contract'] for p in positions));quotes=provider.quotes(contracts) if contracts else {}
 from .engine import quote
 for p in positions:
  q=quote(quotes.get(p['contract'],{}),utcnow())
  if q:
   result=store.call('POST','rpc/kst_agent_mark',data={'p_position':p['id'],'p_bid':q[0],'p_quote':stamp(q[2])})
   if result.get('action')=='RESEARCH_CLOSE':store.insert('kst_agent_decisions',{'agent':p['agent'],'action':result['action'],'reason':result['reason'],'signal_id':p['signal_id'],'model_version':p['model_version'],'regime':p['regime']})
 if not allow_open:return
 remember(store)
 candidates=store.rows('kst_option_signals',state='eq.OPEN',feed='eq.opra',quality_label='eq.QUALIFIED',context_label='in.(BULLISH_SETUP_ALIGNED,BEARISH_SETUP_ALIGNED)',quote_at='gte.'+stamp(now.replace(microsecond=0)-timedelta(minutes=5)),order='score.desc',limit=100)
 entry_quotes=provider.quotes(list(dict.fromkeys(c['contract'] for c in candidates))) if candidates else {}
 for agent in AGENTS:
  result={'action':'WAIT','reason':'No fresh, direction-aligned eligible options'};chosen=None
  for c in candidates:
   chosen=c
   live=entry_quotes.get(c['contract'],{});q=quote(live,utcnow(),max_age=60)
   if not q or (num(live.get('as')) or 0)<1 or (q[1]-q[0])/((q[0]+q[1])/2)>.15:
    result={'action':'WAIT','reason':'No fresh option ask with displayed size and acceptable spread'};continue
   result=store.call('POST','rpc/kst_agent_open',data={'p_agent':agent,'p_signal':c['id'],'p_ask':q[1],'p_bid':q[0],'p_quote':stamp(q[2])})
   if result.get('action')=='RESEARCH_OPEN' or result.get('reason')=='One open research position per agent':break
  store.insert('kst_agent_decisions',{'agent':agent,'action':result['action'],'reason':result['reason'],'signal_id':chosen['id'] if chosen else None,'model_version':chosen['model_version'] if chosen else 'baseline-v1','regime':chosen['context_label'] if chosen else 'NO_SETUP'})
