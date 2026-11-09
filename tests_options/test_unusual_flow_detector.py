from datetime import datetime, timezone, timedelta
from kst_options.unusual_flow import analyze_batch, evaluate_response, alert_preview

NOW = datetime(2026, 11, 9, 15, 30, tzinfo=timezone.utc)


def sample(**kwargs):
    row = dict(id="1", provider="fixture", contract="NVDA270219C00245000",
               time=NOW.isoformat(), price=2.0, size=1500, bid=1.9, ask=2.0,
               underlying_price=176.0)
    row.update(kwargs)
    return row


def test_call_and_put_marketwide_250k_filter():
    rows = [sample(), sample(id="2", contract="SPY270219P00500000", price=1.0, size=2500, bid=1.0, ask=1.1),
            sample(id="3", contract="AAPL270219C00200000", size=1)]
    result = analyze_batch(rows, as_of=NOW)
    assert {x["right"] for x in result["events"]} == {"CALL", "PUT"}
    assert result["rejected"]["BELOW_THRESHOLD"] == 1


def test_equal_size_opposite_legs_suppress_naive_bullish_classification():
    a = sample()
    b = sample(id="2", contract="NVDA270219C00255000", price=1.8,
               bid=1.8, ask=2.0, time=(NOW+timedelta(milliseconds=300)).isoformat())
    events = analyze_batch([a,b], as_of=NOW)["events"]
    assert all(e["possible_spread"] for e in events)
    assert all(len(e["spread_peer_ids"]) == 1 for e in events)


def test_dedupe_stale_invalid_and_missing_quote():
    raw = sample(bid=None, ask=None)
    stale = sample(id="2", time=(NOW-timedelta(minutes=3)).isoformat())
    bad = sample(id="3", price=float("nan"))
    r = analyze_batch([raw, raw, stale, bad], as_of=NOW)
    assert len(r["events"]) == 1
    assert r["events"][0]["execution"] == "UNKNOWN"
    assert r["rejected"] == {"DUPLICATE": 1, "INVALID_OR_STALE": 2}


def test_forward_response_no_lookahead_and_missing_bars():
    event = analyze_batch([sample()], as_of=NOW)["events"][0]
    bars = [{"time":(NOW+timedelta(minutes=4)).isoformat(),"price":200},
            {"time":(NOW+timedelta(minutes=5)).isoformat(),"price":178}]
    r = evaluate_response(event,bars)
    assert r["returns_pct"]["5m"] == 1.136
    assert r["returns_pct"]["15m"] is None
    assert r["status"] == "PARTIAL"


def test_inert_preview_and_provenance():
    event = analyze_batch([sample()], as_of=NOW)["events"][0]
    notice = alert_preview(event)
    assert notice["channels"] == ["telegram", "website"]
    assert notice["delivery_status"] == "DISABLED_REQUIRES_APPROVAL"
    assert notice["scope"] == "INTERNAL_ONLY"


def test_reject_future_or_wrong_contract():
    r=analyze_batch([sample(time=(NOW+timedelta(minutes=1)).isoformat()),
                     sample(id="2", contract="broken")],as_of=NOW)
    assert len(r["events"]) == 0
    assert r["rejected"]["INVALID_OR_STALE"] == 2
