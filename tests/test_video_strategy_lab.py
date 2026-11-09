import numpy as np
import pandas as pd
import pytest
from core.video_strategy_lab import sweep_decisions, backtest, append_run

def bars():
    n=120
    return pd.DataFrame({'Open':np.full(n,100.),'High':np.full(n,101.),
                         'Low':np.full(n,99.),'Close':np.full(n,100.),
                         'Volume':np.full(n,1000.)},
                        index=pd.date_range('2026-01-01',periods=n,freq='5min',tz='UTC'))

def test_sweep_and_no_future_leakage():
    b=bars();b.iloc[40]=[100,101,98,100.5,1000]
    assert sweep_decisions(b).iloc[40]==1
    changed=b.copy();changed.iloc[41:]=[200,201,199,200,1000]
    assert sweep_decisions(b).iloc[:41].equals(sweep_decisions(changed).iloc[:41])
    r=backtest(b)['records'][0]
    assert r['decision_at']==str(b.index[40]) and r['entry_at']==str(b.index[41])

def test_ambiguous_sweep_and_costs():
    b=bars();b.iloc[40]=[100,102,98,100.5,1000]
    assert sweep_decisions(b).iloc[40]==0
    with pytest.raises(ValueError):backtest(b,fee_bps=-1)
    with pytest.raises(ValueError):backtest(b,slippage_bps=float('nan'))

def test_missing_flow_is_blocked_and_runs_saved(tmp_path):
    r=backtest(bars(),strategy='absorption_profile_v1')
    assert r['status']=='needs_order_flow' and not r['records']
    p=tmp_path/'runs.jsonl'
    append_run(p,r,dataset_id='snapshot-1',phase='historical')
    assert 'snapshot-1' in p.read_text()
