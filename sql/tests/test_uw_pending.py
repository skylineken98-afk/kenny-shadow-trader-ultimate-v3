from core import uw_research_pipeline as p
from core import uw_research_scoring as scoring
from core import uw_private_store as store
import pytest

def test_collection_partial(monkeypatch):
    monkeypatch.setitem(p.SOURCES,'flow',lambda ticker:{'data':[{'x':1}]})
    def fail(ticker):raise p.uw.UnusualWhalesError('No entitlement')
    monkeypatch.setitem(p.SOURCES,'greeks',fail)
    obj=p.collect_private_snapshot('spy',['flow','greeks'])
    assert obj['partial'] is True and obj['sources']['flow']==[{'x':1}]
    assert 'greeks' in obj['errors']
    assert 'data' not in p.private_summary(obj)

def test_unrecognized_source():
    with pytest.raises(ValueError):p.collect_private_snapshot('SPY',['unknown'])

def test_storage_default_block(monkeypatch):
    monkeypatch.delenv('UW_PRIVATE_STORAGE_ENABLED',raising=False)
    assert store.save_snapshot({'x':1},license_confirmed=True)['saved'] is False

def test_storage_license_block(monkeypatch):
    monkeypatch.setenv('UW_PRIVATE_STORAGE_ENABLED','true')
    assert store.save_snapshot({'x':1},license_confirmed=False)['saved'] is False

def test_alignment_never_enables_execution():
    result=scoring.assess_research_readiness({'4h':'Bullish','1h':'Bullish','5m':'Bullish'}, {'sources':{'flow':[]}})
    assert result['technical_aligned'] and not result['eligible_for_live_order']
    assert result['flow_confirmation']=='UNVALIDATED_SCHEMA'
