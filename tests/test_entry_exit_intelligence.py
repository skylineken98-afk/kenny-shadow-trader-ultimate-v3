import pandas as pd
import pytest
from core.entry_exit_intelligence import analyze_completed_bars,exit_research

def bars():
    n=80
    values=[100+i*.4 for i in range(n)]
    return pd.DataFrame({'Open':values,'High':[x+1 for x in values], 'Low':[x-1 for x in values], 'Close':values,'Volume':[1000]*n},index=pd.date_range('2026-01-01',periods=n,freq='h'))

def test_no_live_orders():
    result=analyze_completed_bars(bars())
    assert result['status']=='RESEARCH' and result['live_order_authorized'] is False

def test_bad_data():
    assert analyze_completed_bars(bars().head(10))['status']=='INSUFFICIENT_DATA'
    shuffled=bars().iloc[::-1]
    assert analyze_completed_bars(shuffled)['status']=='INVALID_DATA'

def test_exit_styles():
    s={'momentum_weakening':True}
    assert exit_research(s,entry_price=1,current_bid=1.2,style='quick_profit')['exit_candidate']
    assert exit_research(s,entry_price=1,current_bid=1.12,highest_bid=1.5,style='trend_runner')['reason']=='TRAIL'
    assert exit_research(s,entry_price=1,current_bid=1.05,style='adaptive')['reason']=='MOMENTUM'
    assert not exit_research({},entry_price=1,current_bid=1.01)['live_order_authorized']

def test_reject_invalid():
    with pytest.raises(ValueError):exit_research({},entry_price=100,current_bid=0)
