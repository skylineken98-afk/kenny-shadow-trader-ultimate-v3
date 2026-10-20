"""Point-in-time research backtest for observations with known paper returns.

No future-looking feature leakage: event timestamp strictly before decision timestamp.
No manufactured returns or simulated option fills without actual quotes.
"""
from datetime import datetime,timezone
from statistics import mean

def _dt(value):
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('Timezone required')
    return dt.astimezone(timezone.utc)

def evaluate(records):
    valid=[]; skipped=0
    for item in records:
        try:
            signal=_dt(item['decision_time']); available=_dt(item['feature_available_at']); exited=_dt(item['exit_time'])
            ret=float(item['net_return_pct'])
            if not available <= signal < exited or not -100 <= ret <= 100000: raise ValueError('invalid chronology/return')
            if item.get('fill_verified') is not True: raise ValueError('unverified fill')
            valid.append(ret)
        except (KeyError,TypeError,ValueError,OverflowError): skipped+=1
    if not valid: return {'count':0,'skipped':skipped,'win_rate':None,'mean_net_return_pct':None,'expectancy_pct':None,'status':'INSUFFICIENT_VERIFIED_SAMPLES'}
    return {'count':len(valid),'skipped':skipped,'win_rate':sum(x>0 for x in valid)/len(valid),
            'mean_net_return_pct':mean(valid),'expectancy_pct':mean(valid),'status':'DESCRIPTIVE_ONLY_NOT_VALIDATED'}

def comparison(champion, challenger):
    a=evaluate(champion); b=evaluate(challenger)
    return {'champion':a,'challenger':b,'automatic_model_promotion':False,
            'message':'Run out-of-sample, time-split and cost-aware validation before promotion.'}
