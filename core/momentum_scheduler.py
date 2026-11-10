"""Session-aware orchestration for KST momentum research; never routes orders.

One dedicated scanner loop and one independent paper-position monitor loop.
Both begin at the NYSE regular session open, 09:30 America/New_York, and
repeat immediately after each successful callback returns. Providers must
enforce their own request budgets, throttling, timeouts and quote freshness.
Exceptions back off so missing data cannot produce an API request storm.
Callbacks are paper-only and do not imply a position was opened.
"""
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from time import sleep
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN_MINUTES, CLOSE_MINUTES = 9 * 60 + 30, 16 * 60


def regular_session(now):
    """Trading-hours guard, not a time-frame/entry confirmation rule.

    Excludes weekends, but not exchange holidays; callers must supply an
    authoritative exchange-calendar guard before production activation.
    """
    if now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    local = now.astimezone(ET)
    minutes = local.hour * 60 + local.minute
    return local.weekday() < 5 and OPEN_MINUTES <= minutes < CLOSE_MINUTES


def seconds_until_open(now):
    if now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    local = now.astimezone(ET)
    for i in range(8):
        date = (local + timedelta(days=i)).date()
        if date.weekday() >= 5:
            continue
        opening = datetime.combine(date, datetime.min.time(), ET).replace(hour=9, minute=30)
        if opening > local:
            return (opening - local).total_seconds()
    raise RuntimeError("unable to find next regular session")


def run_loop(callback, *, clock=lambda: datetime.now(timezone.utc),
             sleeper=sleep, stopped=None, on_error=None,
             market_is_open=regular_session,
             max_cycles=None):
    """Wait for opening, then call continuously, with NO post-success delay.

    Monitoring and scanning should use independent invocations; they must not
    share a blocking queue. Intended for a separately approved paper worker.
    An optional session calendar (including holidays) is REQUIRED in production.
    """
    stopped = stopped or Event()
    cycles = 0
    while not stopped.is_set():
        now = clock()
        if not regular_session(now):
            delay = min(60.0, max(0.05, seconds_until_open(now)))
            sleeper(delay)
            continue
        if not market_is_open(now):
            sleeper(30.0)  # exchange holiday / unscheduled closure
            continue
        try:
            callback()
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return cycles
            # Re-scan or re-mark immediately after the previous cycle.
            # Underlying provider contracts must rate-limit requests.
        except Exception as exc:
            if on_error:
                on_error(exc)
            sleeper(5.0)  # failure backoff; no fabricated success or fills
    return cycles


def start_paper_research(scan_once, mark_open_paper_positions, *,
                         market_is_open=regular_session, on_error=None):
    """Separate daemon loops: entries never block monitoring and vice versa.

    Deliberately NOT invoked by the existing production workers. The optional
    session calendar must be supplied before production service activation.
    """
    stopped = Event()
    def task(callback):
        return run_loop(callback, stopped=stopped,
                        market_is_open=market_is_open, on_error=on_error)
    scanner = Thread(target=task, args=(scan_once,), name="kst-momentum-scan", daemon=True)
    monitor = Thread(target=task, args=(mark_open_paper_positions,),
                     name="kst-momentum-paper-monitor", daemon=True)
    scanner.start()
    monitor.start()
    return stopped, scanner, monitor
