import pandas as pd
import numpy as np
import pytest
from core.futures_video_pullback import decisions, backtest

def bars(n=160):
    prices = np.linspace(100, 130, n)
    idx = pd.date_range("2026-01-05 14:30",periods=n,freq="5min",tz="UTC")
    return pd.DataFrame({"Open":prices,"High":prices+1,"Low":prices-1,"Close":prices,
                         "Volume":np.full(n,1000.)},index=idx)

def test_no_lookahead():
    b = bars()
    a = decisions(b)
    updated = b.copy()
    updated.loc[updated.index[110]:,"Close"] += 30
    assert a.iloc[:110].equals(decisions(updated).iloc[:110])

def test_research_only_and_costed():
    result = backtest(bars(),symbol="MNQ")
    assert result["research_only"] and not result["broker_orders_enabled"]
    assert result["status"] == "DESCRIPTIVE_SIMULATION"
    assert result["symbol"] == "MNQ"

def test_guards():
    b = bars()
    with pytest.raises(ValueError): backtest(b,symbol="ES")
    with pytest.raises(ValueError): backtest(b,contracts=0)
    with pytest.raises(ValueError): backtest(b,fee_per_side=-1)
    with pytest.raises(ValueError): backtest(b.iloc[::2])
