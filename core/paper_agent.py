"""Opt-in, research-only deterministic paper engine. No brokerage API imports or orders."""
from datetime import datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL
from core.agents import evaluate
from core.risk import Limits, sizing, permitted

PROFILES=('conservative','balanced','aggressive','challenge','daily_10pct_research')

def candidate(signal,profile,account_equity=10000,open_exposure=0,day_start_equity=None,kill=False):
    decision=evaluate(signal,profile)
    if not decision['eligible']:return {'eligible':False,'reason':decision['reason']}
    if signal.get('side') not in ('BULLISH','BEARISH'):return {'eligible':False,'reason':'no supported direction'}
    entry,stop,target=(signal.get(k) for k in ('entry','stop','target'))
    if any(not isinstance(x,(int,float)) or x<=0 for x in (entry,stop,target)):
        return {'eligible':False,'reason':'invalid price levels'}
    side='BUY' if signal['side']=='BULLISH' else 'SELL'
    if (side=='BUY' and not(stop<entry<target)) or (side=='SELL' and not(target<entry<stop)):
        return {'eligible':False,'reason':'inconsistent stop or target'}
    # Only unleveraged stock/spot crypto quantity modelling. No short borrowing, futures or options mechanics.
    if side!='BUY':return {'eligible':False,'reason':'short-selling mechanics not simulated'}
    symbol=signal.get('symbol','')
    if symbol.endswith('=F') or symbol.endswith('=X') or symbol in ('NQ','ES'):
        return {'eligible':False,'reason':'futures/forex requires instrument-specific engine'}
    qty=sizing(account_equity,account_equity,entry,stop,Limits())
    if qty<=0:return {'eligible':False,'reason':'zero paper quantity'}
    allowed,reason=permitted(account_equity,day_start_equity or account_equity,open_exposure,qty*entry,Limits(),killed=kill)
    if not allowed:return {'eligible':False,'reason':reason}
    return {'eligible':True,'symbol':symbol,'profile':profile,'side':side,'entry':entry,'stop':stop,'target':target,'qty':qty,'notional':qty*entry,'simulation_only':True}

def create_event_from_signal(signal,profile,account_equity=10000):
    plan=candidate(signal,profile,account_equity)
    if not plan.get('eligible'):return plan
    # one candidate per specific source row/profile, deduped in Supabase
    event_id=str(uuid5(NAMESPACE_URL,f"kenny-paper:{signal.get('id')}:{profile}"))
    return {'id':event_id,'created_at':datetime.now(timezone.utc).isoformat(),
            'source_signal_id':signal.get('id'),'symbol':plan['symbol'],
            'agent':profile,'status':'CANDIDATE_ONLY','detail':plan}

def conservative_bar_exit(side,stop,target,bar):
    """OHLC does not order intrabar touches; if both, assume stop first."""
    low=float(bar['low']);high=float(bar['high'])
    if side=='BUY':
        if low<=stop:return ('STOP',stop)
        if high>=target:return ('TARGET',target)
    elif side=='SELL':
        if high>=stop:return ('STOP',stop)
        if low<=target:return ('TARGET',target)
    return None
