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
 signals=store.rows('ultimate_signals',order='created_at.desc',limit=100)
 if signals:store.insert('kst_market_memory',[{'id':s['id'],'created_at':s['created_at'],'symbol':s['symbol'],'regime':regime(s),'observation':{'status':s['status'],'side':s.get('side'),'frames':(s.get('details') or {}).get('frames',{}),'source':s.get('source')}} for s in signals],ignore=True)

def cycle(store,provider,now,allow_open=False):
 positions=store.rows('kst_agent_positions',state='eq.OPEN',order='opened_at.asc',limit=100)
 contracts=list(dict.fromkeys(p['contract'] for p in positions));quotes=provider.quotes(contracts) if contracts else {}
 from .engine import quote
 for p in positions:
  q=quote(quotes.get(p['contract'],{}),utcnow())
  if q:
   result=store.call('POST','rpc/kst_agent_mark',data={'p_position':p['id'],'p_bid':q[0],'p_quote':stamp(q[2])})
   if result.get('action')=='RESEARCH_MARK' and p['agent']=='aggressive':
    live=quotes.get(p['contract'],{})
    fresh=quote(live,utcnow(),max_age=60)
    if fresh and (num(live.get('as')) or 0)>=1:
     added=store.call('POST','rpc/kst_agent_add',data={'p_position':p['id'],'p_ask':fresh[1],'p_bid':fresh[0],'p_quote':stamp(fresh[2])})
     if added.get('action')=='RESEARCH_ADD':store.insert('kst_agent_decisions',{'agent':p['agent'],'action':added['action'],'reason':added['reason'],'signal_id':p['signal_id'],'model_version':p['model_version'],'regime':p['regime']})
   if result.get('action')=='RESEARCH_CLOSE':store.insert('kst_agent_decisions',{'agent':p['agent'],'action':result['action'],'reason':result['reason'],'signal_id':p['signal_id'],'model_version':p['model_version'],'regime':p['regime']})
 if not allow_open:return
 remember(store)
 local=now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York'))
 if local.weekday()>4 or not (570<=local.hour*60+local.minute<960):
  for agent in AGENTS:store.insert('kst_agent_decisions',{'agent':agent,'action':'WAIT','reason':'Regular session closed; no new simulated entries. Feed: '+provider.feed,'model_version':'baseline-v1','regime':'MARKET_CLOSED'})
  return
 accounts={a['agent']:a for a in store.rows('kst_agent_accounts',limit=10)}
 max_ask=max((float(a['cash'])*.025/.30/100 for a in accounts.values()),default=0)
 daily_window=local.hour*60+local.minute>=945
 if daily_window:max_ask=max(max_ask,1)
 filters={'state':'in.(OPEN,CLOSED)','feed':'eq.'+provider.feed,'entry_ask':'lte.'+str(max_ask),'quality_label':'eq.QUALIFIED','quote_at':'gte.'+stamp(now.replace(microsecond=0)-timedelta(minutes=5)),'order':'score.desc','limit':100}
 if not daily_window:filters['context_label']='in.(BULLISH_SETUP_ALIGNED,BEARISH_SETUP_ALIGNED)'
 candidates=store.rows('kst_option_signals',**filters)
 today_start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(now.tzinfo)
 entered={p['agent'] for p in store.rows('kst_agent_positions',select='agent',opened_at='gte.'+stamp(today_start),limit=1000)}
 entry_quotes=provider.quotes(list(dict.fromkeys(c['contract'] for c in candidates))) if candidates else {}
 for agent in AGENTS:
  result={'action':'WAIT','reason':('Daily required entry blocked: no fresh affordable quote' if daily_window and agent not in entered else 'No fresh, direction-aligned eligible options')+' on '+provider.feed+' feed (virtual research only)'};chosen=None
  ranked=sorted(candidates,key=lambda c:((0 if c['category']=='0DTE' else 1) if agent=='aggressive' else (0 if c['category']=='Swings' else 1), c['expiration'] if agent=='aggressive' else '',-float(c['score'])))
  for c in ranked:
   cash=float((accounts.get(agent) or {}).get('cash',0))
   fraction={'conservative':.005,'balanced':.01,'aggressive':.02,'challenge':.025,'daily_10pct_research':.01}[agent]
   required=daily_window and agent not in entered
   if required:fraction=.03
   if required and float(c['entry_ask'])*100+float(c.get('fee_estimate',0))>min(100,cash):continue
   if float(c['entry_ask'])*100*(.25 if agent=='aggressive' else .30)+float(c.get('fee_estimate',0))>cash*fraction:
    result={'action':'WAIT','reason':'No eligible one-contract idea within paper cash and stop-risk limit'};continue
   chosen=c
   live=entry_quotes.get(c['contract'],{});q=quote(live,utcnow(),max_age=60)
   if not q or (num(live.get('as')) or 0)<1 or (q[1]-q[0])/((q[0]+q[1])/2)>.15:
    result={'action':'WAIT','reason':'No fresh option ask with displayed size and acceptable spread'};continue
   result=store.call('POST','rpc/kst_agent_open',data={'p_agent':agent,'p_signal':c['id'],'p_ask':q[1],'p_bid':q[0],'p_quote':stamp(q[2])})
   if result.get('action')=='RESEARCH_OPEN' or result.get('reason') in ('One open research position per agent',):break
  store.insert('kst_agent_decisions',{'agent':agent,'action':result['action'],'reason':result['reason'],'signal_id':chosen['id'] if chosen else None,'model_version':chosen['model_version'] if chosen else 'baseline-v1','regime':chosen['context_label'] if chosen else 'NO_SETUP'})

