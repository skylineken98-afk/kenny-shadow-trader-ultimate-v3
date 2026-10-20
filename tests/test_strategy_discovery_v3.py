import pandas as pd
import numpy as np
import pytest
from core.strategy_discovery import CATALOG,candidates,research_backtest,walk_forward
from core.robinhood_gateways import RobinhoodMCPGateway,RobinhoodCryptoReadOnly,LiveRiskGate,LiveExecutionUnavailable

def bars(n=240):
    idx=pd.date_range('2025-01-01',periods=n,freq='h',tz='UTC')
    close=np.linspace(100,135,n)
    return pd.DataFrame({'Open':close,'High':close+1,'Low':close-1,'Close':close,'Volume':np.ones(n)*1000},index=idx)

def test_library_and_hypotheses():
    assert len(CATALOG)>=50
    c=candidates(60)
    assert len(c)==60 and len(set(x.name for x in c))==60

def test_holdout_and_order_of_data():
    c=candidates(1)[0]
    result=walk_forward(bars(),c)
    assert result['status']=='EVALUATED' and result['auto_promote'] is False
    for rec in result['holdout']['records']:
        assert rec['decision_at']<rec['entry_at']<rec['exit_at']
        assert rec['entry_at']>=result['cutoff']

def test_fail_on_unordered_bars():
    with pytest.raises(ValueError):research_backtest(bars().iloc[::-1],candidates(1)[0])

def test_mcp_never_submits():
    g=RobinhoodMCPGateway()
    assert g.status()['authenticated'] is False
    with pytest.raises(LiveExecutionUnavailable):g.submit({'buy':'SPY'})

def test_crypto_never_submits():
    c=RobinhoodCryptoReadOnly()
    with pytest.raises(LiveExecutionUnavailable):c.submit({'buy':'BTC-USD'})
    with pytest.raises(LiveExecutionUnavailable):c.get('/api/v1/crypto/trading/orders/anything')

def test_trade_caps():
    g=LiveRiskGate()
    assert g.review(20,0,0)['within_limits']
    assert not g.review(50,0,0)['within_limits']
    assert not g.review(20,5,0)['within_limits']
    assert g.review(20,0,0)['live_order_authorized'] is False
