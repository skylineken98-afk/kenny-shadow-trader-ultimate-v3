import pytest
from core import uw_extended_research as er
from core import research_backtest as bt
from core import uw_alert_scheduler as sched

def test_endpoint_disabled_by_default():
    assert er.get_feed('history','SPY')['status']=='DISABLED'

def test_missing_endpoint(monkeypatch):
    monkeypatch.delenv('UW_EARNINGS_PATH',raising=False)
    assert er.get_feed('earnings','SPY',approved=True)['status']=='NOT_CONFIGURED'

def test_restrict_endpoint(monkeypatch):
    monkeypatch.setenv('UW_HISTORY_PATH','https://evil.test/api/stock/{ticker}')
    with pytest.raises(ValueError):er.get_feed('history','SPY',approved=True)

def test_fake_response(monkeypatch):
    monkeypatch.setenv('UW_HISTORY_PATH','/api/stock/{ticker}/flow-recent')
    monkeypatch.setattr(er,'_request',lambda path: {'data':[]} if path.endswith('/SPY/flow-recent') else None)
    assert er.get_feed('history','SPY',approved=True)['status']=='AVAILABLE'

def test_backtest_time_leakage():
    rows=[{'decision_time':'2026-10-19T12:00:00Z','feature_available_at':'2026-10-19T13:00:00Z',
           'exit_time':'2026-10-19T14:00:00Z','net_return_pct':50,'fill_verified':True}]
    assert bt.evaluate(rows)['count']==0

def test_backtest_valid():
    rows=[{'decision_time':'2026-10-19T12:00:00Z','feature_available_at':'2026-10-19T11:00:00Z',
           'exit_time':'2026-10-19T14:00:00Z','net_return_pct':10,'fill_verified':True}]
    assert bt.evaluate(rows)['win_rate']==1.0
    assert bt.comparison(rows,rows)['automatic_model_promotion'] is False

def test_scan_off(monkeypatch):
    monkeypatch.setenv('UW_SCAN_ENABLED','true')
    assert sched.run_once(['SPY'],enabled=False)['status']=='DISABLED'

def test_scan_safe(monkeypatch):
    monkeypatch.setenv('UW_SCAN_ENABLED','true')
    def collect(t):return {'ticker':t,'observed_at':'2026-10-19T13:00:00Z','sources':{'flow':[{'secret':'vendor data'}]},'errors':{}}
    result=sched.run_once(['SPY'],enabled=True,collector=collect)
    assert result['status']=='RESEARCH_ONLY' and 'secret' not in str(result) and result['orders_placed']==0
