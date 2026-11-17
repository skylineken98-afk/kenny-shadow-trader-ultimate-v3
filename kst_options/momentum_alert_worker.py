"""KST read-only opening/midday momentum alerts over private Telegram.

Research alerts only. Starts scanning at 09:30 ET and begins the next pass as
soon as the prior pass finishes, subject to provider request rate limits.
Requires configured TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID. No trades are placed.
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests

from core.momentum_scalper import _confirmed_momentum
from core.momentum_scheduler import run_loop, regular_session
from zoneinfo import ZoneInfo

LOG = logging.getLogger("kst.momentum_alert")
ET = ZoneInfo("America/New_York")


def symbols_from_env():
    allowed = []
    for item in os.getenv("KST_MOMENTUM_SYMBOLS", "SPY,AMD,QQQ,NVDA,AVGO").split(","):
        sym = item.strip().upper()
        if sym and sym.replace(".", "").isalpha() and len(sym) <= 6 and sym not in allowed:
            allowed.append(sym)
    return allowed[:20]


def completed_bars(symbol, now, *, session=None, feed=None):
    """Fetch only today's completed 1-minute bar observations.

    Returns [] on unavailable/not-yet-finished data; no delayed or previous
    session candles masquerade as current momentum.
    """
    feed = feed or os.getenv("KST_MOMENTUM_STOCK_FEED", "iex").lower()
    if feed not in ("sip", "iex"):
        raise ValueError("Stock feed must be sip or iex")
    key = os.getenv("ALPACA_API_KEY", "").strip()
    secret = os.getenv("ALPACA_API_SECRET", "").strip()
    if not key or not secret:
        raise RuntimeError("Alpaca stock market-data credentials not configured")
    local = now.astimezone(ET)
    opening = local.replace(hour=9, minute=30, second=0, microsecond=0)
    if local < opening:
        return []
    response = (session or requests).get(
        "https://data.alpaca.markets/v2/stocks/bars",
        params={"symbols": symbol, "timeframe": "1Min",
                "start": opening.astimezone(timezone.utc).isoformat(),
                "end": now.astimezone(timezone.utc).isoformat(),
                "limit": 1000, "feed": feed, "adjustment": "raw"},
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
        timeout=12)
    response.raise_for_status()
    rows = response.json().get("bars", {}).get(symbol, [])
    complete = []
    for b in rows:
        try:
            started = datetime.fromisoformat(str(b["t"]).replace("Z", "+00:00"))
            if started.tzinfo is None or started.astimezone(ET).date() != local.date():
                continue
            # Alpaca bar timestamp is bar START; wait until the minute closes.
            if started + timedelta(minutes=1) > now:
                continue
            complete.append({"t": (started + timedelta(minutes=1)).isoformat(),
                             "c": b["c"], "h": b["h"], "l": b["l"],
                             "v": b["v"], "complete": True})
        except (ValueError, TypeError, KeyError):
            continue
    return complete[-8:]


def build_alert(symbol, outcome, feed):
    direction = outcome["direction"]
    return (
        "KST MOMENTUM ALERT · PAPER RESEARCH ONLY\n"
        + symbol + " · " + ("BULLISH / CALL WATCH" if direction == "BULLISH"
                            else "BEARISH / PUT WATCH") + "\n"
        + "Confirmed bar close: " + outcome["observed_at"] + "\n"
        + "Relative candle volume: " + outcome["volume_expansion_proxy"] + "x\n"
        + "Stock bars: Alpaca " + feed.upper() + " feed\n"
        + "Watch for a fresh liquid options contract and validated bid/ask; "
          "no option quote, probability, fill or broker order implied."
    )


def telegram_send(message, *, session=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("Telegram destination not configured")
    if not isinstance(message, str) or len(message) > 1500:
        raise ValueError("Invalid Telegram alert")
    response = (session or requests).post(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        json={"chat_id": chat, "text": message,
              "disable_web_page_preview": True}, timeout=12)
    response.raise_for_status()
    if response.json().get("ok") is not True:
        raise RuntimeError("Telegram rejected alert")
    return True


class MomentumTelegramScanner:
    def __init__(self, *, provider=completed_bars, sender=telegram_send,
                 clock=lambda: datetime.now(timezone.utc)):
        self.provider = provider
        self.sender = sender
        self.clock = clock
        self.sent = {}
        self.last_request = 0.0

    def cycle(self):
        now = self.clock()
        if not regular_session(now):
            return []
        symbols = symbols_from_env()
        if not symbols:
            LOG.warning("No momentum symbols configured")
            return []
        feed = os.getenv("KST_MOMENTUM_STOCK_FEED", "iex").lower()
        emitted = []
        for symbol in symbols:
            # API-aware minimum spacing; no fixed *scan* interval is imposed.
            # Batch provider queries in a future optimization if scale grows.
            gap = 1.0 - (time.monotonic() - self.last_request)
            if gap > 0:
                time.sleep(gap)
            self.last_request = time.monotonic()
            bars = self.provider(symbol, self.clock())
            if len(bars) < 2:
                continue
            result = _confirmed_momentum(symbol, bars)
            if result["status"] != "PAPER_CANDIDATE":
                continue
            try:
                stamp = datetime.fromisoformat(result["observed_at"])
                if stamp.tzinfo is None or not 0 <= (self.clock() - stamp).total_seconds() <= 120:
                    continue
            except (TypeError, ValueError):
                continue
            # Only one alert per symbol/direction/completed candle.
            # Do not mark sent on Telegram failures.
            key = (symbol, result["direction"], result["observed_at"])
            if key in self.sent:
                continue
            self.sender(build_alert(symbol, result, feed))
            self.sent[key] = self.clock()
            emitted.append(key)
        # Limit only the dedup memory, not the scan schedule.
        if len(self.sent) > 200:
            ordered = sorted(self.sent, key=self.sent.get)
            for key in ordered[:-100]:
                self.sent.pop(key, None)
        return emitted


def main():
    logging.basicConfig(level=logging.INFO)
    if os.getenv("KST_MOMENTUM_ALERTS_ENABLED", "false").lower() != "true":
        LOG.warning("Momentum alerts not enabled; no Telegram messages sent")
        return
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        LOG.error("Missing Telegram bot token or destination; no alerts can be sent")
        return
    scanner = MomentumTelegramScanner()
    run_loop(scanner.cycle, on_error=lambda exc:
             LOG.error("Momentum alert scan failed: %s", type(exc).__name__))


if __name__ == "__main__":
    main()
