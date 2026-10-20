import pytest
from core import paper_automation as m
from workers.paper_execution_worker import cycle

def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv('V3_PAPER_AUTOMATION_ENABLED',raising=False)
    with pytest.raises(m.WorkerError,match='disabled'):
        m.simulate_signal('one','balanced',{})

def test_no_broker_no_quote_worker(monkeypatch):
    monkeypatch.setenv('V3_PAPER_AUTOMATION_ENABLED','true')
    assert cycle()['status']=='NO_VERIFIED_QUOTE_PROVIDER'

def test_no_missing_account(monkeypatch):
    monkeypatch.setenv('V3_PAPER_AUTOMATION_ENABLED','true')
    monkeypatch.setattr(m,'_one',lambda table,**kwargs: {'status':'SETUP','side':'BULLISH'} if table=='ultimate_signals' else None)
    with pytest.raises(m.WorkerError,match='emergency stop'):
        m.simulate_signal('one','balanced',{})

def test_emergency_stop_rejects_unknown_agent():
    with pytest.raises(m.WorkerError,match='Unknown agent'):
        m.request_emergency_stop('unknown')
