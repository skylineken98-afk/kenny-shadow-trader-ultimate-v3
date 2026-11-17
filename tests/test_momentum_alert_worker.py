from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from kst_options.momentum_alert_worker import (
    MomentumTelegramScanner, build_alert, completed_bars, telegram_send,
)

NOW = datetime(2026, 11, 10, 14, 35, tzinfo=timezone.utc)


def test_momentum_alert_deduplicates_and_never_places_order():
    messages = []
    def bars(symbol, now):
        return [
            dict(t="2026-11-10T14:33:00Z", c=100, h=100.1, l=99.9, v=100, complete=True),
            dict(t="2026-11-10T14:34:00Z", c=101, h=101.1, l=100.5, v=400, complete=True),
        ]
    scanner = MomentumTelegramScanner(provider=bars, sender=messages.append, clock=lambda: NOW)
    with patch("kst_options.momentum_alert_worker.symbols_from_env", return_value=["SPY", "AMD"]), \
         patch("kst_options.momentum_alert_worker.time.sleep"):
        assert len(scanner.cycle()) == 2
        assert scanner.cycle() == []
    assert len(messages) == 2
    assert all("PAPER RESEARCH ONLY" in m for m in messages)
    assert all("no option quote" in m for m in messages)


def test_bar_requires_completed_minute_and_current_session():
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"bars":{"SPY":[
                {"t":"2026-11-09T20:59:00Z","c":99,"h":100,"l":98,"v":1000},
                {"t":"2026-11-10T14:33:00Z","c":100,"h":101,"l":99,"v":1000},
                {"t":"2026-11-10T14:34:00Z","c":101,"h":102,"l":100,"v":2000},
                {"t":"2026-11-10T14:35:00Z","c":102,"h":103,"l":101,"v":3000}
            ]}}
    class Session:
        def get(self, *args, **kwargs):return Response()
    with patch.dict("os.environ", {"ALPACA_API_KEY":"test", "ALPACA_API_SECRET":"test"}):
        b=completed_bars("SPY", NOW, session=Session())
    assert len(b)==2
    assert b[0]["complete"] is True
    assert b[-1]["t"].startswith("2026-11-10T14:35:")


def test_telegram_requires_opt_in_destination():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN":"", "TELEGRAM_CHAT_ID":""}):
        try: telegram_send("test")
        except RuntimeError as e:assert "destination" in str(e)
        else:assert False


def test_no_alert_on_neutral_or_old_candles():
    seen = []
    def old(symbol,now):
        return [{"t":"2026-11-09T14:33:00Z","c":100,"h":100.1,"l":99.9,"v":100,"complete":True},
                {"t":"2026-11-09T14:34:00Z","c":101,"h":101.1,"l":100.5,"v":400,"complete":True}]
    scanner = MomentumTelegramScanner(provider=old,sender=seen.append,clock=lambda:NOW)
    with patch("kst_options.momentum_alert_worker.symbols_from_env",return_value=["SPY"]):
        assert scanner.cycle() == []
    assert seen == []


def test_alert_discloses_feed_and_quote_limitations():
    message=build_alert("AMD", {"direction":"BEARISH","observed_at":NOW.isoformat(),"volume_expansion_proxy":"2.40"},"iex")
    assert "AMD" in message and "BEARISH" in message
    assert "IEX" in message and "no option quote" in message
