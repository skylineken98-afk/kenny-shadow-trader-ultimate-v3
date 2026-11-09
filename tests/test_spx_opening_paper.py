from datetime import datetime
from zoneinfo import ZoneInfo
from core.spx_opening_paper import opening_entry, opening_exit

ET = ZoneInfo("America/New_York")


def bars(up=True):
    out = []
    for i in range(22):
        p = 100 + (i if up else -i) * .5
        out.append({"high": p+.1, "low": p-.1, "close": p,
                    "volume": 500, "vwap": 100})
    return out


def t(hour, minute):
    return datetime(2026, 11, 9, hour, minute, tzinfo=ET)


def test_no_entry_before_932_or_after_1000():
    opts = dict(bars=bars(), hourly_trend="BULLISH", zone_side="BULLISH",
                reward_risk=1.5, fresh_quote=True)
    assert opening_entry(t(9,31), **opts)["action"] == "SKIP"
    assert opening_entry(t(10,0), **opts)["action"] == "SKIP"


def test_bullish_entry_only_on_confirmed_momentum():
    result = opening_entry(t(9,32), bars=bars(), hourly_trend="BULLISH",
                           zone_side="BULLISH", reward_risk=1.5, fresh_quote=True)
    assert result["side"] == "CALL"
    result = opening_entry(t(9,32), bars=bars(), hourly_trend="BEARISH",
                           zone_side="BULLISH", reward_risk=1.5, fresh_quote=True)
    assert result["side"] == "CALL"  # upward price momentum overrides bearish context


def test_bearish_entry():
    result = opening_entry(t(9,32), bars=bars(False), hourly_trend="BEARISH",
                           zone_side="BEARISH", reward_risk=2, fresh_quote=True)
    assert result["side"] == "PUT"


def test_fail_closed_without_quote_or_with_limit():
    kw = dict(bars=bars(), hourly_trend="BULLISH", zone_side="BULLISH",
              reward_risk=1.5)
    assert opening_entry(t(9,32), **kw)["action"] == "SKIP"
    assert opening_entry(t(9,32), **kw, fresh_quote=True, daily_loss_pct=10)["action"] == "SKIP"


def test_weakening_and_stop_and_hard_exit():
    base = dict(side="CALL", entry_ask=1.0, latest_bid=1.2,
                fast_ema=102, slow_ema=101, underlying_close=102,
                vwap=100, last_1m_close=102, previous_1m_close=101)
    assert opening_exit(t(9,40), **base)["action"] == "HOLD"
    assert opening_exit(t(9,40), **{**base, "fast_ema":100})["reason"] == "momentum_weakening"
    assert opening_exit(t(9,40), **{**base, "latest_bid":.74})["reason"] == "premium_stop_25pct"
    assert opening_exit(t(10,0), **{**base, "latest_bid":None})["reason"] == "1000_ET_hard_cutoff"


def test_timezone_required():
    try:
        opening_entry(datetime(2026,11,9,9,32), bars=[], hourly_trend='BULLISH', zone_side='BULLISH', reward_risk=1.5)
    except ValueError:
        return
    assert False, "naive datetimes must be rejected"


def test_put_wins_despite_bullish_higher_timeframes():
    result = opening_entry(t(9,32), bars=bars(False), hourly_trend="BULLISH",
                           zone_side="BULLISH", reward_risk=1.5, fresh_quote=True)
    assert result["action"] == "ENTRY_CANDIDATE"
    assert result["side"] == "PUT"


def test_mixed_momentum_stays_out():
    mixed = bars()
    mixed[-1] = {"high": 100.2, "low": 99.8, "close": 100,
                 "volume": 500, "vwap": 100}
    result = opening_entry(t(9,32), bars=mixed, hourly_trend="BULLISH",
                           zone_side="BULLISH", reward_risk=1.5, fresh_quote=True)
    assert result["action"] == "SKIP"
