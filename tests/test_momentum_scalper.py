from datetime import datetime, timezone, timedelta
from core.momentum_scalper import plan_momentum_scalp, evaluate_scalp_exit

NOW = datetime(2026, 11, 10, 14, 45, tzinfo=timezone.utc)
CALL = "SPY261110C00750000"
PUT = "SPY261110P00750000"

def bars(bear=False):
    out = []
    for i in range(8):
        c = (100 - i * .05) if bear else (100 + i * .05)
        out.append({"t": f"2026-11-10T14:{37+i:02d}:00Z", "c": c,
                    "h": c + .10, "l": c - .10,
                    "v": 100 if i < 5 else 500, "complete": True})
    out[-1]["c"] = 98 if bear else 102
    out[-1]["l"] = 97.9 if bear else 101.9
    out[-1]["h"] = 98.1 if bear else 102.1
    return out

def quote(bid="0.90", ask="0.95", now=NOW):
    return {"bp": bid, "ap": ask, "t": now.isoformat()}

def plan(**kwargs):
    return plan_momentum_scalp("SPY", bars(), CALL, quote(),
                               equity=1000, day_start_equity=1000,
                               budget=100, now=NOW, **kwargs)

def test_affordable_call_is_only_candidate():
    result = plan()
    assert result["status"] == "PAPER_CANDIDATE"
    assert result["execution"] == "NONE"
    assert result["estimated_contract_cost"] == "95.00"
    assert float(result["minimum_reward_risk"]) >= 1.5

def test_bearish_contract_right():
    r = plan_momentum_scalp("SPY", bars(True), PUT, quote(),
                            equity=1000, day_start_equity=1000,
                            budget=100, now=NOW)
    assert r["direction"] == "BEARISH"
    assert plan_momentum_scalp("SPY", bars(True), CALL, quote(),
                               equity=1000, day_start_equity=1000,
                               budget=100, now=NOW)["status"] == "REJECTED"

def test_stale_and_unconfirmed_fail_closed():
    assert plan_momentum_scalp("SPY", bars(), CALL, quote(now=NOW-timedelta(minutes=2)),
                                equity=1000, day_start_equity=1000,
                                budget=100, now=NOW)["status"] == "REJECTED"
    candles = bars()
    candles[-1]["complete"] = False
    assert plan_momentum_scalp("SPY", candles, CALL, quote(),
                                equity=1000, day_start_equity=1000,
                                budget=100, now=NOW)["status"] == "REJECTED"

def test_guardrails():
    r = plan_momentum_scalp("SPY", bars(), CALL, quote(ask="2.00",bid="1.90"),
                             equity=1000, day_start_equity=1000, budget=100, now=NOW)
    assert "budget" in r["reason"]
    assert plan_momentum_scalp("SPY", bars(), CALL, quote(), equity=890,
                                day_start_equity=1000, budget=100, now=NOW)["status"] == "REJECTED"
    assert plan_momentum_scalp("SPY", bars(), CALL, quote(), equity=1000,
                                day_start_equity=1000, budget=100, now=NOW,
                                open_positions=3)["status"] == "REJECTED"
    assert plan_momentum_scalp("SPY", bars(), CALL, quote(), equity=1000,
                                day_start_equity=1000, budget=100,
                                now=NOW.replace(hour=16))["status"] == "REJECTED"

def test_trailing_stop_and_momentum_weakening():
    r = evaluate_scalp_exit("1", "1.32", peak_bid="1.6", momentum_confirmed=True)
    assert r["status"] == "HOLD_CANDIDATE" and r["stop_premium"] == "1.3000"
    r = evaluate_scalp_exit("1", "1.25", peak_bid="1.6", momentum_confirmed=True)
    assert r["status"] == "EXIT_CANDIDATE"
    r = evaluate_scalp_exit("1", "1.10", peak_bid="1.2", momentum_confirmed=False)
    assert r["status"] == "EXIT_CANDIDATE"
    assert evaluate_scalp_exit("1", "1.10", peak_bid="1.2", momentum_confirmed=None)["status"] == "NO_TRADE"
