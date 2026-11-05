import pandas as pd
import pytest
from core.spx_scalping import volume_profile_proxy, pressure_proxy


def sample(n=150):
    return pd.DataFrame({'High':[102+i*.01 for i in range(n)],
                         'Low':[98+i*.01 for i in range(n)],
                         'Close':[101+i*.01 for i in range(n)],
                         'Volume':[100+i for i in range(n)]},
                        index=pd.date_range('2026-01-05 09:30',periods=n,freq='min'))


def test_profile_within_range():
    d=sample();p=volume_profile_proxy(d)
    assert p['value_area_low'] <= p['poc'] <= p['value_area_high']
    assert len(p['histogram'])==32
    assert sum(x['volume'] for x in p['histogram'])==sum(d.Volume)


def test_pressure_is_proxy():
    p=pressure_proxy(sample())
    assert p['close_location_pressure']>0
    assert 'NOT real bid/ask' in p['source']


def test_missing_volume_rejected():
    d=sample();d['Volume']=0
    assert volume_profile_proxy(d) is None
    assert pressure_proxy(d) is None


def test_bad_bins_rejected():
    with pytest.raises(ValueError): volume_profile_proxy(sample(),bins=2)
