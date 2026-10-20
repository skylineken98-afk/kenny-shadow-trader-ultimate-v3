from core.v3_readiness import audit
from core.v3_release_gates import allowed
from core.v3_signal_audit import event
from core.v3_notifications import send_private_test
from core.v3_model_validation import validate,time_split
from core.v3_membership import transition
import pytest

def test_audit_does_not_expose_key():
 d=audit({'UNUSUAL_WHALES_API_KEY':'not-for-output'})
 assert d['unusual_whales']['credentials_present']
 assert 'not-for-output' not in str(d)
 assert d['unusual_whales']['status']=='NOT_LIVE_VERIFIED'

def test_gates_fail_closed():
 assert not allowed('live_broker',{},explicit_approval=True)['allowed']
 assert not allowed('public_uw_data',{'unusual_whales':True})['allowed']
 assert allowed('paper_scanning',{'market_scanner':True,'supabase_journal':True},explicit_approval=True)['allowed']
 assert not allowed('paper_scanning',{'market_scanner':True,'supabase_journal':True})['allowed']

def test_audit_entry_sanitizes():
 with pytest.raises(ValueError):event('signal_created',details={'api_key':'secret'})
 assert event('signal_created',symbol='SPY')['kind']=='signal_created'

def test_telegram_opt_in():
 assert not send_private_test(approved=False)['sent']

def test_validation_no_model_promotion():
 assert validate([],[])['automatic_promotion'] is False
 assert time_split([])['status']=='INSUFFICIENT_SAMPLES'

def test_membership_rejects_unverified():
 assert not transition('trial','paid',verified_webhook=False,event_id='x')['accepted']
 assert transition('trial','paid',verified_webhook=True,event_id='evt_x')['state']=='active'
