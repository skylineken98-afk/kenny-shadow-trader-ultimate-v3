from datetime import datetime,timedelta,timezone
from kst_options.engine import mark,context_label,candidate,stamp
NOW=datetime(2026,11,6,20,tzinfo=timezone.utc)

def signal():
 return dict(entry_ask=1,quote_at=stamp(NOW-timedelta(minutes=1)),due_at=stamp(NOW+timedelta(hours=1)),risk_snapshot={'existing':'preserved'})

def test_stop_then_target_keeps_first_observed_stop_separate_from_final_return():
 s=signal()
 stopped=mark(s,dict(bp=.6,ap=.62,t=stamp(NOW)),NOW)
 s.update(stopped)
 later=NOW+timedelta(minutes=1)
 won=mark(s,dict(bp=1.6,ap=1.62,t=stamp(later)),later)
 s.update(won)
 assert s['risk_snapshot']['observed_barrier']['outcome']=='STOP_FIRST_OBSERVED'
 assert s['risk_snapshot']['existing']=='preserved'
 assert s['estimated_return']>.5
 assert 'state' not in s # barrier observation does not change horizon closure

def test_target_then_stop_and_fee_adjustment():
 s=signal();s.update(mark(s,dict(bp=1.5,ap=1.52,t=stamp(NOW)),NOW))
 later=NOW+timedelta(minutes=1)
 s.update(mark(s,dict(bp=.5,ap=.52,t=stamp(later)),later))
 assert s['risk_snapshot']['observed_barrier']['outcome']=='TARGET_FIRST_OBSERVED'
 r=mark(signal(),dict(bp=1.5,ap=1.52,t=stamp(NOW)),NOW,fee=1)
 assert 'observed_barrier' not in r['risk_snapshot'] # +49%, not the +50% barrier

def test_barrier_after_horizon_does_not_rewrite_earlier_path():
 s=signal();s['due_at']=stamp(NOW-timedelta(seconds=1))
 r=mark(s,dict(bp=2,ap=2.02,t=stamp(NOW)),NOW)
 assert 'observed_barrier' not in r['risk_snapshot']
 assert r['state']=='CLOSED'

def test_setup_timestamp_and_bar_freshness_are_both_required():
 c=dict(option_type='CALL')
 setup=dict(status='SETUP',side='BULLISH',created_at=stamp(NOW),details={'frames':{'5m':{'bar_closed_at':stamp(NOW-timedelta(minutes=5))}}})
 assert context_label(c,setup,NOW)=='BULLISH_SETUP_ALIGNED'
 setup['created_at']=stamp(NOW-timedelta(minutes=6))
 assert context_label(c,setup,NOW)=='STRUCTURAL_ONLY'
 setup['created_at']=stamp(NOW);setup['details']['frames']['5m']['bar_closed_at']=stamp(NOW-timedelta(days=1))
 assert context_label(c,setup,NOW)=='STRUCTURAL_ONLY'
 setup['details']={}
 assert context_label(c,setup,NOW)=='STRUCTURAL_ONLY'

def test_new_entries_require_quote_under_one_minute():
 snapshot={'latestQuote':dict(bp=1,ap=1.05,t=stamp(NOW-timedelta(seconds=61))),'greeks':dict(delta=.5)}
 assert candidate('SPY261113C00600000',snapshot,NOW,'opra') is None


def test_legacy_flags_never_get_an_invented_first_crossing():
 s=signal();s['stop_seen']=True
 r=mark(s,dict(bp=2,ap=2.02,t=stamp(NOW)),NOW)
 assert r['risk_snapshot']['observed_barrier']['outcome']=='PRIOR_ORDER_UNKNOWN'


def test_trend_frames_exclude_forming_bars_and_record_actual_bar_time():
 import pandas as pd
 from unittest.mock import patch
 from core.market import _trend_confluence
 now=datetime.now(timezone.utc)
 def history(symbol,period,interval):
  freq='5min' if interval=='5m' else '1h'
  idx=pd.date_range(end=pd.Timestamp(now).floor(freq),periods=300,freq=freq)
  return pd.DataFrame({'Open':100.,'High':101.,'Low':99.,'Close':100.,'Volume':10.},index=idx)
 with patch('core.market.history',side_effect=history):
  result=_trend_confluence('TEST')
 for f in result['frames'].values():
  closed=datetime.fromisoformat(f['bar_closed_at'])
  assert closed<=datetime.now(timezone.utc)
