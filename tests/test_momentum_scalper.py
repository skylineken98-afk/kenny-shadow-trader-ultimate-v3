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
                                now=NOW.replace(hour=21))["status"] == "REJECTED"

def test_trailing_stop_and_momentum_weakening():
    r = evaluate_scalp_exit("1", "1.32", peak_bid="1.6", momentum_confirmed=True)
    assert r["status"] == "HOLD_CANDIDATE" and r["stop_premium"] == "1.3000"
    r = evaluate_scalp_exit("1", "1.25", peak_bid="1.6", momentum_confirmed=True)
    assert r["status"] == "EXIT_CANDIDATE"
    r = evaluate_scalp_exit("1", "1.10", peak_bid="1.2", momentum_confirmed=False)
    assert r["status"] == "EXIT_CANDIDATE"
    assert evaluate_scalp_exit("1", "1.10", peak_bid="1.2", momentum_confirmed=None)["status"] == "NO_TRADE"


def test_momentum_at_open_not_932_gate():
    early = datetime(2026, 11, 10, 14, 31, 20, tzinfo=timezone.utc)
    candles = [
        {"t": "2026-11-10T14:29:00Z", "c": 100, "h": 100.10, "l": 99.90, "v": 100, "complete": True},
        {"t": "2026-11-10T14:30:00Z", "c": 101, "h": 101.10, "l": 100.50, "v": 280, "complete": True},
    ]
    result = plan_momentum_scalp("SPY", candles, CALL, quote(now=early),
                                 equity=1000, day_start_equity=1000,
                                 budget=100, now=early)
    assert result["status"] == "PAPER_CANDIDATE"
    assert result["direction"] == "BULLISH"


def test_amd_midday_momentum_does_not_require_higher_timeframe_alignment():
    midday = datetime(2026, 11, 10, 16, 45, 20, tzinfo=timezone.utc)
    candles = [
        {"t": "2026-11-10T16:43:00Z", "c": 250, "h": 250.2, "l": 249.8, "v": 150, "complete": True},
        {"t": "2026-11-10T16:44:00Z", "c": 251.5, "h": 251.7, "l": 250.9, "v": 450, "complete": True},
    ]
    result = plan_momentum_scalp("AMD", candles, "AMD261110C00250000",
                                 quote(now=midday), equity=1000,
                                 day_start_equity=1000, budget=100, now=midday)
    assert result["status"] == "PAPER_CANDIDATE"
    assert "no fixed candle timeframe" in result["momentum_method"]


def test_one_candle_is_not_enough_and_reversal_selects_put():
    now = datetime(2026, 11, 10, 17, 2, tzinfo=timezone.utc)
    candles = [
        {"t": "2026-11-10T17:00:00Z", "c": 100, "h": 100.1, "l": 99.9, "v": 100, "complete": True},
        {"t": "2026-11-10T17:01:00Z", "c": 98, "h": 98.2, "l": 97.8, "v": 300, "complete": True},
    ]
    assert plan_momentum_scalp("SPY", candles[-1:], PUT, quote(now=now),
                                equity=1000, day_start_equity=1000,
                                budget=100, now=now)["status"] == "REJECTED"
    result = plan_momentum_scalp("SPY", candles, PUT, quote(now=now),
                                 equity=1000, day_start_equity=1000,
                                 budget=100, now=now)
    assert result["status"] == "PAPER_CANDIDATE"
    assert result["direction"] == "BEARISH"
