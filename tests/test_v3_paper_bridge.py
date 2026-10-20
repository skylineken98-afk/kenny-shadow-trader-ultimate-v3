import pytest
from core import v3_paper_bridge as bridge

def test_default_disabled(monkeypatch):
    monkeypatch.delenv('V3_ATOMIC_PAPER_BRIDGE_ENABLED',raising=False)
    with pytest.raises(bridge.BridgeDisabled):
        bridge.record_research_entry(agent='balanced',signal_id='x',occ='SPY   261020C00500000',
          asset='call',direction='BULLISH',ask=2,stop=1,target=3,quote_timestamp='2026-10-20T10:00:00Z')

def test_unknown_agent_fails(monkeypatch):
    monkeypatch.setenv('V3_ATOMIC_PAPER_BRIDGE_ENABLED','true')
    with pytest.raises(ValueError):
        bridge.record_research_entry(agent='invalid',signal_id='x',occ='SPY   261020C00500000',
          asset='call',direction='BULLISH',ask=2,stop=1,target=3,quote_timestamp='2026-10-20T10:00:00Z')

def test_rpc_payload(monkeypatch):
    monkeypatch.setenv('V3_ATOMIC_PAPER_BRIDGE_ENABLED','true')
    class Stub:
        def rpc(self,method,payload):
            assert method=='v3_record_paper_entry'
            assert payload['p_max_risk']=='0.01'
            self.payload=payload
            return self
        def execute(self):
            return type('R',(),{'data':'example-uuid'})()
    monkeypatch.setattr(bridge,'client',lambda:Stub())
    result=bridge.record_research_entry(agent='balanced',signal_id='x',occ='SPY   261020C00500000',
        asset='call',direction='BULLISH',ask=2,stop=1,target=3,quote_timestamp='2026-10-20T10:00:00Z')
    assert result['status']=='DATABASE_RECORDED_SIMULATED_ONLY'
