import pandas as pd
from core.flow_intelligence import measure_flow, alignment_bonus


def candles(sign=1):
    close=[20+sign*.15*i for i in range(35)]
    return pd.DataFrame({'Close':close,'High':[v+(.01 if sign>0 else .2) for v in close],
                         'Low':[v-(.2 if sign>0 else .01) for v in close],'Volume':[1000]*34+[8000]})


def test_detects_direction_and_large_relative_volume():
    bull=measure_flow(candles(1))
    bear=measure_flow(candles(-1))
    assert bull['direction']=='BULLISH' and bull['relative_volume']==8
    assert bear['direction']=='BEARISH'
    assert alignment_bonus(bull, 'BULLISH')>0
    assert alignment_bonus(bull, 'BEARISH')==0


def test_insufficient_data_not_fake_inflow():
    assert measure_flow(candles().head(3)) is None
