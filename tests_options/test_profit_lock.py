from datetime import datetime,timedelta,timezone
from kst_options.profit_lock import observe
T=datetime(2026,11,6,15,tzinfo=timezone.utc)
def step(s,bid,minute):
 result=observe(s,bid,T+timedelta(minutes=minute));s['risk_snapshot']={'profit_lock':result};return result

def test_ladder_ratchets_never_lowers_and_records_observed_gap_exit():
 s={'entry_ask':1}
 for minute,(bid,stop) in enumerate([(1.31,.3),(1.43,.4),(1.61,.5),(1.8,.75),(2.1,1),(2.38,1.25)]):
  r=step(s,bid,minute);assert r['stop_return']==stop;assert 'stop_hit_at' not in r
 r=step(s,2.30,7);assert r['stop_return']==1.25
 r=step(s,2.1,8);assert r['observed_exit_return']==1.1
 assert r['stop_return']==1.25 # actual observed bid can gap below the reference
 assert step(s,4,9)==r # subsequent rally does not rewrite a recorded exit

def test_exact_target_arms_without_exiting_same_observation():
 s={'entry_ask':1};r=step(s,1.3,0)
 assert r['stop_return']==.3 and 'stop_hit_at' not in r
 assert step(s,1.29,1)['exit_reason']=='PROFIT_LOCK_STOP_OBSERVED'

def test_initial_loss_stop_and_non_unit_cost():
 s={'entry_ask':.9};r=step(s,.9,0);assert r['stop_premium']==.63
 assert step(s,.6,1)['exit_reason']=='INITIAL_STOP_OBSERVED'


def test_new_signal_closes_research_at_profit_stop_and_keeps_expiry_deadline():
 from kst_options.engine import mark,deadline
 s={'entry_ask':1,'quote_at':(T-timedelta(seconds=5)).isoformat(),'due_at':(T+timedelta(days=5)).isoformat(), 'risk_snapshot':{'exit_policy':'profit-lock-v1'}}
 s.update(mark(s,{'bp':1.43,'ap':1.45,'t':T.isoformat()},T))
 assert s['risk_snapshot']['profit_lock']['stop_return']==.4
 later=T+timedelta(minutes=1)
 r=mark(s,{'bp':1.35,'ap':1.37,'t':later.isoformat()},later)
 assert r['state']=='CLOSED' and round(r['outcome_return'],2)==.35
 expiry=deadline({'category':'Swings','expiration':'2026-11-13','risk_snapshot':{'exit_policy':'profit-lock-v1'}},T)
 assert expiry.date().isoformat()=='2026-11-13'
