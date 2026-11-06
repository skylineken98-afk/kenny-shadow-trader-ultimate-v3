"""Sampled profit-lock references. No brokerage orders or guaranteed fills."""
import math
from .engine import parse,stamp

def locked_level(peak):
 if peak+1e-10<.30:return -.30
 if peak+1e-10<.40:return .30
 if peak+1e-10<.50:return .40
 if peak+1e-10<.75:return .50
 if peak+1e-10<1:return .75
 return math.floor((peak+1e-10)*4)/4

def next_level(peak):
 for level in (.30,.40,.50,.75,1.):
  if peak<level-1e-10:return level
 return (math.floor((peak+1e-10)*4)+1)/4

def observe(signal,bid,t):
 entry=float(signal['entry_ask'])
 ret=(float(bid)-entry)/entry
 prior=dict((signal.get('risk_snapshot') or {}).get('profit_lock') or {})
 if prior.get('stop_hit_at'):return prior
 # A newly initialized record cannot reconstruct historic intrapoll paths.
 peak=max(ret,float(prior.get('peak_return',ret)))
 previous_stop=float(prior.get('stop_return',-.30))
 previous_time=prior.get('quote_at')
 hit=ret<=previous_stop+1e-10 and (previous_time is None or t>parse(previous_time))
 level=max(previous_stop,locked_level(peak))
 result=dict(version='profit-lock-v1',quote_at=stamp(t),peak_return=peak,
             stop_return=level,stop_premium=round(entry*(1+level),4),
             next_target_return=next_level(peak),
             next_target_premium=round(entry*(1+next_level(peak)),4),
             basis='Gross observed bid vs recorded ask; fees excluded',
             mode='MONITOR_ONLY',history_scope='Since profit-lock tracking initialized; no historical fill inferred')
 if hit:
  result.update(stop_hit_at=stamp(t),stop_hit_bid=bid,observed_exit_return=ret,
                exit_reason='INITIAL_STOP_OBSERVED' if previous_stop<0 else 'PROFIT_LOCK_STOP_OBSERVED')
 return result
