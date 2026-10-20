import pytest
from datetime import datetime,timedelta,timezone
from core.adaptive_learning import market_regime,ResearchJournal

def test_regimes():
    assert market_regime([100]*12)['regime']=='UNKNOWN'
    assert market_regime([100+i for i in range(32)])['regime'] in ('UPTREND','HIGH_VOLATILITY','RANGE_OR_MIXED')

def test_journal_and_leakage(tmp_path):
    j=ResearchJournal(tmp_path/'research.sqlite')
    j.register('v1','conservative',{'threshold':.2})
    dt=datetime(2026,1,1,tzinfo=timezone.utc)
    row={'decision_time':dt.isoformat(),'feature_available_at':(dt-timedelta(minutes=2)).isoformat(),
         'exit_time':(dt+timedelta(minutes=5)).isoformat(),'net_return_pct':1.2,'fill_verified':True}
    j.record('obs1','v1','conservative',row)
    assert j.scorecard('v1')['count']==1
    with pytest.raises(ValueError):j.record('obs2','v1','conservative',{**row,'feature_available_at':(dt+timedelta(minutes=1)).isoformat()})
    with pytest.raises(ValueError):j.record('obs3','v1','conservative',{**row,'token':'secret'})
    j.register('v2','balanced',{})
    assert j.review('v1','v2')['automatic_promotion'] is False
    j.close()

def test_unfilled_excluded(tmp_path):
    j=ResearchJournal(tmp_path/'dev.sqlite');j.register('v1','balanced',{})
    d=datetime(2026,2,1,tzinfo=timezone.utc)
    j.record('x','v1','balanced',{'decision_time':d.isoformat(),'feature_available_at':d.isoformat(),
                                'exit_time':(d+timedelta(days=1)).isoformat(),
                                'net_return_pct':100,'fill_verified':False})
    assert j.scorecard('v1')['count']==0
    j.close()
