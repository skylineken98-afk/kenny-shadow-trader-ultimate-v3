import pytest
from decimal import Decimal
from core.robinhood_live_controls import (AllocationPolicy, OrderResearchLedger,
                                           LiveControlError, proposal_key)

def test_allocation_review_no_permission():
    policy=AllocationPolicy()
    r=policy.review(order_notional=10,account_buying_power=100,open_exposure=0,
                    daily_realized_loss=0,broker_state_confirmed=True)
    assert r['passes_risk_checks']
    assert r['authorizes_broker_submission'] is False

def test_refuse_unknown_account():
    p=AllocationPolicy()
    r=p.review(order_notional=10,account_buying_power=100,open_exposure=0,
               daily_realized_loss=0)
    assert 'BROKER_STATE_NOT_RECONCILED' in r['reasons']

def test_limits():
    p=AllocationPolicy()
    def check(**kwargs):
        return p.review(account_buying_power=100,open_exposure=0,
                        daily_realized_loss=0,broker_state_confirmed=True,**kwargs)
    assert 'ORDER_CAP' in check(order_notional=61)['reasons']
    assert 'EXPOSURE_CAP' in check(order_notional=15,pending_order_notional=50)['reasons']
    assert 'DAILY_LOSS_LIMIT' in p.review(order_notional=10,account_buying_power=100,
                  open_exposure=0,daily_realized_loss=5,broker_state_confirmed=True)['reasons']

def test_idempotency_and_reconcile():
    ledger=OrderResearchLedger()
    k=proposal_key('account','signal','instrument','BUY')
    ledger.propose(key=k,broker='robinhood',account_ref='account',instrument_id='instrument',notional=10)
    ledger.propose(key=k,broker='robinhood',account_ref='account',instrument_id='instrument',notional=10)
    assert ledger.conn.execute('SELECT COUNT(*) FROM live_order_research').fetchone()[0]==1
    with pytest.raises(LiveControlError):
        ledger.reconcile(key=k,broker_order_id='id1',broker_state='OPEN')
    x=ledger.reconcile(key=k,broker_order_id='id1',broker_state='OPEN',broker_snapshot_verified=True)
    assert x['state']=='OPEN'
    with pytest.raises(LiveControlError):
        ledger.reconcile(key=k,broker_order_id='id2',broker_state='FILLED',broker_snapshot_verified=True)
    ledger.close()

def test_restart_never_unblocks_trading():
    ledger=OrderResearchLedger()
    assert not ledger.restart_gate([],[])['safe_to_resume']
    assert ledger.restart_gate([],[],snapshot_verified=True)['reason']=='POSITION_RECONCILIATION_NOT_IMPLEMENTED'
    ledger.close()


def test_sixty_dollar_order_limit():
    p=AllocationPolicy()
    assert p.max_new_order == Decimal('60')
    assert p.max_open_exposure == Decimal('60')
    kw=dict(account_buying_power=100,open_exposure=0,daily_realized_loss=0,broker_state_confirmed=True)
    assert p.review(order_notional=60,**kw)['passes_risk_checks']
    assert 'ORDER_CAP' in p.review(order_notional=60.01,**kw)['reasons']
    assert 'EXPOSURE_CAP' in p.review(order_notional=60,open_exposure=1, account_buying_power=100, daily_realized_loss=0, broker_state_confirmed=True)['reasons']
    assert p.review(order_notional=60,**kw)['authorizes_broker_submission'] is False
