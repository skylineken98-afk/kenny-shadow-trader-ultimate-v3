from datetime import datetime, timezone
import json
import pytest
from core.opening_momentum_breakout import detect, paper_option_plan, backtest, append_performance

NOW = datetime(2026, 11, 10, 14, 36, 30, tzinfo=timezone.utc)

def candles(bear=False):
    # One opening impulse, three restrained pullback candles, then a breakout.
    rows = [
        (100, 101.2, 99.9, 101.0, 1200),
        (101.0, 101.1, 100.7, 100.8, 200),
        (100.8, 100.9, 100.65, 100.75, 180),
        (100.75, 100.9, 100.7, 100.85, 220),
        (100.85, 101.9, 100.8, 101.75, 750),
    ]
    if bear:
        rows = [(200-o, 200-l, 200-h, 200-c, v) for o,h,l,c,v in rows]
    return [dict(t=f"2026-11-10T14:{30+i:02d}:00Z", o=o,h=h,l=l,c=c,v=v,complete=True)
            for i,(o,h,l,c,v) in enumerate(rows)]

def test_bull_and_bear_breakout():
    for bear, name in ((False,"BULLISH"),(True,"BEARISH")):
        s=detect(candles(bear))
        assert s["status"]=="PAPER_SIGNAL", s
        assert s["direction"]==name
        assert s["relative_volume"]>=1.3
        assert s["execution"]=="NONE"
        assert s["underlying_target_1_5rr"]>0

def test_reject_weak_breakout_volume_and_unconfirmed():
    b=candles()
    b[-1]["c"]=100.9
    assert detect(b)["status"]=="REJECTED"
    b=candles();b[-1]["v"]=100
    assert "volume" in detect(b)["reason"].lower()
    b=candles();b[-1]["complete"]=False
    assert detect(b)["status"]=="REJECTED"

def test_no_future_lookahead_or_timeframe_alignment():
    original=detect(candles())
    later=candles()+[dict(t="2026-11-10T14:35:00Z",o=101.75,h=103,l=101,c=102.9,v=800,complete=True)]
    assert detect(later[:5])==original
    # There is no 4H/1H/5M trend argument or requirement.

def test_reject_mismatched_session_and_invalid_ohlcv():
    b=candles();b[0]["t"]="2026-11-10T14:29:00Z"
    assert detect(b)["status"]=="REJECTED"
    b=candles();b[2]["h"]=99
    assert detect(b)["status"]=="REJECTED"
    b=candles();b[-1]["t"]=b[-2]["t"]
    assert detect(b)["status"]=="REJECTED"

def test_options_only_paper_and_risk_guards():
    b=candles()
    quote={"bp":"0.90","ap":"0.95","t":NOW.isoformat()}
    opts=dict(equity=1000,day_start_equity=1000,budget=100,now=NOW)
    r=paper_option_plan("SPY",b,"SPY261110C00750000",quote,**opts)
    assert r["status"]=="PAPER_CANDIDATE",r
    assert r["estimated_one_contract_cost"]=="95.00"
    assert r["execution"]=="NONE" and r["premium_initial_stop"]=="0.7125"
    assert paper_option_plan("SPY",b,"SPY261110P00750000",quote,**opts)["status"]=="REJECTED"
    assert paper_option_plan("SPY",b,"SPY261110C00750000",quote,
                            **dict(opts,equity=890))["status"]=="REJECTED"
    assert paper_option_plan("SPY",b,"SPY261110C00750000",quote,
                            **dict(opts,budget=50))["status"]=="REJECTED"
    assert paper_option_plan("SPY",b,"SPY261110C00750000",quote,
                            **dict(opts,open_positions=3))["status"]=="REJECTED"

def test_backtest_next_bar_entry_costs_and_reporting(tmp_path):
    data=candles()+[
        dict(t=f"2026-11-10T14:{35+i:02d}:00Z",
             o=101.8+i*.1,h=102+i*.1,l=101.6+i*.1,
             c=101.85+i*.1,v=350,complete=True) for i in range(5)]
    result=backtest(data,holding_bars=2,fee_bps=5,slippage_bps=5)
    assert result["trades"]==1,result
    rec=result["records"][0]
    assert rec["decision_at"]==data[4]["t"].replace("Z","+00:00")
    assert rec["entry_at"]==data[5]["t"].replace("Z","+00:00")
    assert rec["option_fill_verified"] is False
    assert result["option_returns"] is False and not result["auto_promote"]
    output=tmp_path/"strategy.jsonl"
    append_performance(output,result,dataset_id="historical-snapshot-v1",phase="historical")
    assert json.loads(output.read_text())["phase"]=="historical"
    with pytest.raises(ValueError):
        append_performance(output,result,dataset_id="",phase="paper")

def test_backtest_cost_validation():
    with pytest.raises(ValueError):
        backtest(candles(),fee_bps=-1)
    with pytest.raises(ValueError):
        backtest(candles(),slippage_bps=float("nan"))
