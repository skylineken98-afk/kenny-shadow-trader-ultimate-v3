import pandas as pd
from core.market import levels
from core.risk import sizing,permitted

def test_levels():
    close=list(range(100,160))
    df=pd.DataFrame({'Close':close,'High':[x+1 for x in close],'Low':[x-1 for x in close],'Open':close,'Volume':[100]*60})
    x=levels(df)
    assert x['trend']=='BULLISH' and x['resistance']==160

def test_sizing():
    assert sizing(10000,10000,100,98)==10
    assert sizing(0,10000,100,98)==0

def test_daily_loss_kill():
    assert not permitted(9400,10000,0,100)[0]
    assert not permitted(10000,10000,0,100,killed=True)[0]
