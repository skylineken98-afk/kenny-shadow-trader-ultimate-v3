import pandas as pd
import pytest
from core.liquidity_fvg import liquidity_fvg_setup


def fixture():
    h = pd.DataFrame([[105,120,98,106]]*12, columns=['Open','High','Low','Close'], index=pd.date_range('2026-11-01', periods=12, freq='4h', tz='UTC'))
    rows = [[101,102,100,101]]*12 + [[101,101,98,101], [101,106,100.5,105], [105,107,103,106], [105,106,102,104]]
    b = pd.DataFrame(rows,columns=h.columns,index=pd.date_range('2026-11-03 00:00',periods=len(rows),freq='15min',tz='UTC'))
    return h,b,b.index[-1]+pd.Timedelta(minutes=15)


def test_complete_sequence_and_no_early_signal():
    h,b,now=fixture()
    result=liquidity_fvg_setup(h,b,now)
    assert result['status']=='SETUP'
    assert result['side']=='BULLISH'
    assert result['stop'] < result['entry'] < result['target']
    assert result['reward_risk'] >= 1.5
    for length in range(13,len(b)):
        assert liquidity_fvg_setup(h,b.iloc[:length],b.index[length-1]+pd.Timedelta(minutes=15))['status']=='WAIT'


def test_bearish_mirror():
    h,b,now=fixture()
    def mirror(d):
        return pd.DataFrame({'Open':220-d.Open,'High':220-d.Low,'Low':220-d.High,'Close':220-d.Close},index=d.index)
    r=liquidity_fvg_setup(mirror(h),mirror(b),now)
    assert r['side']=='BEARISH'
    assert r['target'] < r['entry'] < r['stop']


def test_forming_stale_invalidated_and_bad_data():
    h,b,now=fixture()
    assert liquidity_fvg_setup(h,b,now-pd.Timedelta(minutes=1))['status']=='WAIT'
    assert liquidity_fvg_setup(h,b,now+pd.Timedelta(hours=1))['status']=='WAIT'
    b.iloc[-1,b.columns.get_loc('Low')]=97
    assert liquidity_fvg_setup(h,b,now)['status']=='WAIT'
    b.iloc[-1,b.columns.get_loc('Close')]=float('nan')
    with pytest.raises(ValueError):liquidity_fvg_setup(h,b,now)


def test_missing_sweep_and_low_rr():
    h,b,now=fixture()
    assert liquidity_fvg_setup(h,b,now,min_rr=10)['status']=='WAIT'
    b.iloc[12,b.columns.get_loc('Low')]=100
    assert liquidity_fvg_setup(h,b,now)['status']=='WAIT'
