from decimal import Decimal
import pytest
from core.paper_lifecycle import PaperAccount, PaperRiskError, enter, close_trade

def acct(name='balanced',killed=False): return PaperAccount(name,Decimal('10000'),Decimal('10000'),killed=killed)
def position(a=None,asset='call',direction='BULLISH'):
    return enter(a or acct(),signal_id='s1',symbol='SPY270115C00500000',asset=asset,direction=direction,
                 entry='1',ask='1.05',stop='.90',target='1.50',quantity=1)
def test_open_and_stop():
    p=position(); assert p['cost']=='105.00'
    x=close_trade(p,bar={'low':'.85','high':'1.6'})
    assert x['exit_reason']=='STOP' and Decimal(x['realized_pnl'])==Decimal('-15.00')
def test_put_is_long_bearish(): assert position(asset='put',direction='BEARISH')['state']=='SIMULATED_OPEN'
def test_bearish_stock_rejected():
    with pytest.raises(PaperRiskError): position(asset='stock',direction='BEARISH')
def test_kill():
    with pytest.raises(PaperRiskError):position(acct(killed=True))
def test_risk():
    with pytest.raises(PaperRiskError):
        enter(acct('conservative'),signal_id='a',symbol='SPY',asset='stock',direction='BULLISH',entry='100',ask='100',stop='90',target='120',quantity=10)
def test_missing_exit(): assert close_trade(position(),bar={'low':'1.10','high':'1.20'}) is None
