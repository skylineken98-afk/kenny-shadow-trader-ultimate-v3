import pytest
from datetime import datetime,timedelta,timezone
from kst_pro.pricing_policy import monthly_amount,display_pricing,validate_stripe_price,require_ready_for_subscription
from kst_pro.broker_learning import (
    normalize_permissions,consent_allows_learning,attribution,
    training_observation,public_group_summary,CONSENT_VERSION,MIN_AGGREGATE_USERS
)

NOW=datetime(2026,11,5,19,tzinfo=timezone.utc)
def ts(minutes):return (NOW+timedelta(minutes=minutes)).isoformat()
def consent(enabled=True):
 return dict(learning_enabled=enabled,consented_at=ts(-120),
             consent_version=CONSENT_VERSION,revoked_at=None)
def fill():return dict(symbol='AAPL',side='BTO',option_type='CALL',asset_type='option',filled_at=ts(1))
def signal():return dict(id='sig1',symbol='AAPL',status='SETUP',side='BULLISH',created_at=ts(0))
def outcome():return dict(closed_at=ts(10),realized_pnl='44.50')

def test_first_year_regular_and_renewal_prices():
 assert [monthly_amount(m) for m in (1,2,12,13,20)]==[10000,10000,10000,15000,15000]
 assert display_pricing()['month_13_plus']==15000

def test_intro_codes_are_equivalent_and_nonstackable():
 for code in ('ENZO','MAYVI'):
  assert [monthly_amount(m,code) for m in (1,2,12,13)]==[0,5000,5000,15000]
 with pytest.raises(ValueError):monthly_amount(2,'ENZO+MAYVI')

def test_billing_requires_correct_stripe_prices_and_schedule():
 p={'active':True,'unit_amount':10000,'currency':'usd','recurring':{'interval':'month'}}
 assert validate_stripe_price(p,10000)
 assert not validate_stripe_price({**p,'unit_amount':15000},10000)
 for env in ({},{'STRIPE_YEAR_TWO_PRICE_ID':'price_next'}):
  with pytest.raises(ValueError):require_ready_for_subscription(env)
 assert require_ready_for_subscription({'STRIPE_YEAR_TWO_PRICE_ID':'price_next','KST_BILLING_PHASES_VERIFIED':'true'})

def test_permissions_never_enable_trading_without_broker_approval():
 defaults=normalize_permissions()
 assert defaults['execution_enabled'] is False and defaults['training_enabled'] is False
 with pytest.raises(PermissionError):normalize_permissions(read_only=False,request_execution=True)
 with pytest.raises(PermissionError):normalize_permissions(read_only=False,request_execution=True,broker_approved=True)

def test_collective_learning_requires_explicit_active_consent():
 assert consent_allows_learning(consent(),NOW)
 assert not consent_allows_learning(consent(False),NOW)
 invalid=consent();invalid['revoked_at']=ts(-1)
 assert not consent_allows_learning(invalid,NOW)
 with pytest.raises(PermissionError):training_observation(consent(False),fill(),outcome(),[signal()])

def test_attribution_is_conservative():
 unknown=attribution(fill(),[signal()])
 assert unknown['label']=='POSSIBLE_MATCH'
 chosen=attribution(fill(),[signal()],clicked_signal_ids=['sig1'])
 assert chosen['label']=='USER_SELECTED_SIGNAL'
 far=signal();far['created_at']=ts(-200)
 assert attribution(fill(),[far])['label']=='UNATTRIBUTED'
 other=signal();other['side']='BEARISH'
 assert attribution(fill(),[other])['label']=='UNATTRIBUTED'

def test_verified_outcome_and_private_cohort():
 obs=training_observation(consent(),fill(),outcome(),[signal()])
 assert obs['pnl_dollars']==44.5 and obs['signal_attribution']=='POSSIBLE_MATCH'
 assert 'user_id' not in obs and obs['verified_source']=='broker_fill_and_close'
 cohort=[dict(obs,user_id='u'+str(i)) for i in range(MIN_AGGREGATE_USERS)]
 assert public_group_summary(cohort[:-1])['published'] is False
 assert public_group_summary(cohort)['published'] is False
 assert public_group_summary(cohort)['status']=='READY_FOR_AGGREGATE_REVIEW'
