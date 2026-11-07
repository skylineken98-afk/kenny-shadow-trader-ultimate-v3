import pandas as pd
from core.trend_quality import trend_quality


def bars(values):
    return pd.DataFrame({'Close': values, 'High': [x+.1 for x in values], 'Low': [x-.1 for x in values]})


def test_directional_trends_and_mismatch():
    up=bars(list(range(1,61)))
    assert trend_quality(up,'BULLISH')['passes']
    assert not trend_quality(up,'BEARISH')['passes']
    assert trend_quality(bars(list(range(61,1,-1))),'BEARISH')['passes']


def test_flat_and_chop_are_rejected():
    assert not trend_quality(bars([10]*60),'BULLISH')['passes']
    q=trend_quality(bars([10,12]*30),'BULLISH')
    assert not q['passes']
    assert q['ema_crosses']>2
    assert q['efficiency']<.35


def test_insufficient_evidence():
    assert not trend_quality(bars([10]*10),'BULLISH')['passes']
