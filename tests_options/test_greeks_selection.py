from datetime import datetime, timezone, timedelta
import pytest
from kst_options.greeks_selection import analyze_contract_greeks, rank_with_greeks
from kst_options.engine import candidate, requested_choices

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
SYMBOL = "SPY261110C00600000"

def snap(*, greeks_at=None, option_type="CALL"):
    data = {"greeks": {"delta": 0.48 if option_type == "CALL" else -0.48,
                       "gamma": 0.035, "theta": -0.08, "vega": 0.07, "rho": 0.003},
            "latestQuote": {"bp": 0.95, "ap": 1.0, "t": NOW.isoformat()},
            "impliedVolatility": 0.30, "underlyingPrice": 600}
    if greeks_at is not None:
        data["greeks_at"] = greeks_at.isoformat()
    return data


def test_all_five_greeks_and_scenarios():
    r = analyze_contract_greeks(snap(greeks_at=NOW), option_type="CALL",
                                entry_ask=1, underlying_price=600, now=NOW)
    assert set(r["greeks"]) == {"delta", "gamma", "theta", "vega", "rho"}
    assert r["greeks_fresh_verified_timestamp"]
    assert len(r["scenarios"]) == 6
    assert any(x["estimated_contract_pnl_before_costs"] < 0 for x in r["scenarios"])
    assert r["not_probability_of_profit"] is True


def test_no_fabricated_greek_timestamp_and_no_bonus():
    r = analyze_contract_greeks(snap(), option_type="CALL",
                                entry_ask=1, underlying_price=600, now=NOW)
    assert r["greeks_at"] is None
    assert r["structural_score_adjustment"] == 0
    assert any("timestamp" in x for x in r["warnings"])
    rows = rank_with_greeks([{"contract":"A","score":70,"greeks_analysis":r}])
    assert rows[0]["greeks_adjusted_score"] == 70
    assert not rows[0]["greeks_adjustment_applied"]


def test_stale_or_future_greek_timestamp_no_bonus():
    for dt in (NOW-timedelta(hours=1), NOW+timedelta(seconds=1)):
        r = analyze_contract_greeks(snap(greeks_at=dt), option_type="CALL",
                                    entry_ask=1, underlying_price=600, now=NOW)
        assert r["structural_score_adjustment"] == 0


def test_missing_greeks_not_invented():
    r=analyze_contract_greeks({},option_type="PUT",entry_ask=1,now=NOW)
    assert not r["scenarios"]
    assert r["greeks"]["gamma"] is None
    with pytest.raises(ValueError):
        analyze_contract_greeks({},option_type="CALL",entry_ask=0,now=NOW)


def test_put_direction_and_scenario_changes():
    r=analyze_contract_greeks(snap(greeks_at=NOW,option_type="PUT"),
                              option_type="PUT",entry_ask=1,underlying_price=600,now=NOW)
    assert not any("direction-inconsistent" in w for w in r["warnings"])
    assert r["scenarios"][0]["estimated_premium"] != r["scenarios"][3]["estimated_premium"]


def test_engine_records_analysis_without_changing_liquidity_gates():
    c=candidate(SYMBOL,snap(),NOW,"opra")
    assert c is not None
    assert c["risk_snapshot"]["greeks_analysis"]["greeks"]["rho"] == 0.003
    assert not c["risk_snapshot"]["greeks_analysis"]["greeks_fresh_verified_timestamp"]
    assert candidate(SYMBOL,{**snap(),"latestQuote":{"bp":0.1,"ap":1.0,"t":NOW.isoformat()}},NOW,"opra") is None


def test_affordable_choices_no_mandatory_greeks_and_score_separate():
    r=analyze_contract_greeks(snap(greeks_at=NOW),option_type="CALL",
                              entry_ask=1,underlying_price=600,now=NOW)
    rows=[{"contract":"SPY_A","underlying":"SPY","category":"0DTE","entry_ask":1.0,
           "score":68,"quality_label":"QUALIFIED","greeks_analysis":r},
          {"contract":"IWM_B","underlying":"IWM","category":"0DTE","entry_ask":.49,
           "score":65,"quality_label":"QUALIFIED"}]
    picked=requested_choices(rows,"0DTE",100)
    assert {x["underlying"] for x in picked}=={"SPY","IWM"}
    assert all("structural_score" in x and "greeks_adjusted_score" in x for x in picked)
    assert requested_choices(rows,"0DTE",50)[0]["underlying"]=="IWM"
