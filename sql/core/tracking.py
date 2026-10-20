"""Signal attribution never conflates price touch with fills."""
from datetime import datetime,timezone

def evaluate_signal(signal,candles):
    entry=signal.get('entry');stop=signal.get('stop');target=signal.get('target');side=signal.get('side')
    if not all(isinstance(x,(int,float)) for x in (entry,stop,target)) or side not in ('BULLISH','BEARISH'):
        return {'state':'UNTRACKABLE','reason':'missing executable plan'}
    entered=False;out=None;entry_time=None
    for c in candles:
        high=float(c['high']);low=float(c['low']);ts=c.get('time')
        if not entered:
            if low<=entry<=high:entered=True;entry_time=ts
            else:continue
        # OHLC cannot order stop and target touches in one bar; conservative assumption.
        hit_stop=low<=stop if side=='BULLISH' else high>=stop
        hit_target=high>=target if side=='BULLISH' else low<=target
        if hit_stop:out=('STOP',stop,ts);break
        if hit_target:out=('TARGET',target,ts);break
    if not entered:return {'state':'UNTRIGGERED','simulated_fill':False}
    result={'state':'OPEN' if out is None else out[0],'simulated_fill':True,'entry_time':entry_time,'fills_are_assumed':True}
    if out:
        move=(out[1]-entry)/entry*(1 if side=='BULLISH' else -1)
        result.update({'exit_price':out[1],'exit_time':out[2],'underlying_return_pct':round(move*100,3),'options_return_pct':None})
    return result
