import pytest
from core.execution import build_paper_order, AlpacaPaperBroker, ExecutionError, PAPER_URL

OPTION='SPY270115C00500000'

def test_standard_option_cost_and_limit():
    order=build_paper_order(OPTION,'buy',2,'1.20',signal_id='signal-a',max_order_cost=250)
    assert order['qty']=='2' and order['limit_price']=='1.20'
    assert order['client_order_id'].startswith('kstp-')

def test_same_signal_same_client_id():
    a=build_paper_order(OPTION,'buy',1,'.20',signal_id='foo')
    b=build_paper_order(OPTION,'buy',1,'.20',signal_id='foo')
    assert a['client_order_id']==b['client_order_id']

@pytest.mark.parametrize('data',[
    ('BAD','buy',1,'1'),(OPTION,'sell',1,'1'),(OPTION,'buy',0,'1'),
    (OPTION,'buy',1,'nan'),(OPTION,'buy',1,'4'),
])
def test_reject_invalid(data):
    with pytest.raises(ExecutionError):
        build_paper_order(*data,signal_id='x',max_order_cost=250)

def test_disabled_fails_closed():
    broker=AlpacaPaperBroker(key='dummy',secret='dummy',enabled=False)
    with pytest.raises(ExecutionError): broker.account()
    with pytest.raises(ExecutionError): broker.submit({},approved=True)

def test_no_live_endpoint():
    assert PAPER_URL=='https://paper-api.alpaca.markets/v2'

def test_explicit_approval_required():
    broker=AlpacaPaperBroker(enabled=True,key='dummy',secret='dummy')
    proposal=build_paper_order(OPTION,'buy',1,'.50',signal_id='source')
    with pytest.raises(ExecutionError): broker.submit(proposal)
