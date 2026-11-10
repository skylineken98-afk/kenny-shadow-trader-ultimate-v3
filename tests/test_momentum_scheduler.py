from datetime import datetime, timezone, timedelta
from core.momentum_scheduler import regular_session, seconds_until_open, run_loop

OPEN = datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)

def test_first_scan_is_at_open_and_cycles_immediately_after_finishing():
    times = iter([OPEN - timedelta(seconds=1), OPEN, OPEN])
    delays, observed = [], []
    def clock():
        return next(times)
    def callback():
        observed.append("scan")
    assert run_loop(callback, clock=clock, sleeper=delays.append, max_cycles=2) == 2
    assert observed == ["scan", "scan"]
    # One wait before 09:30; no arbitrary wait between scans.
    assert delays == [1.0]

def test_monitor_can_use_same_immediate_loop_independently():
    count = []
    assert run_loop(lambda: count.append("mark"), clock=lambda: OPEN,
                    sleeper=lambda _: None, max_cycles=3) == 3
    assert count == ["mark", "mark", "mark"]

def test_beyond_open_does_not_cut_off_at_10am():
    assert regular_session(datetime(2026, 11, 10, 19, 10, tzinfo=timezone.utc))
    assert not regular_session(datetime(2026, 11, 10, 21, 10, tzinfo=timezone.utc))

def test_dst_and_weekend_waits():
    fri = datetime(2026, 11, 13, 22, 0, tzinfo=timezone.utc)
    assert seconds_until_open(fri) > 0
    assert regular_session(datetime(2026, 7, 1, 13, 30, tzinfo=timezone.utc))
    assert not regular_session(datetime(2026, 7, 1, 13, 29, tzinfo=timezone.utc))

def test_error_backs_off_and_no_success_recorded():
    calls, delays = [], []
    def broken():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("provider failed")
    assert run_loop(broken, clock=lambda: OPEN, sleeper=delays.append, max_cycles=1) == 1
    assert delays == [5.0]
    assert len(calls) == 2

def test_exchange_closed_calendar_blocks_entries():
    seen = []
    # Controlled loop that stops after a calendar guard check.
    class Stop(Exception): pass
    def sleeper(_):
        raise Stop
    try:
        run_loop(lambda: seen.append(1), clock=lambda: OPEN, sleeper=sleeper,
                 market_is_open=lambda _: False)
    except Stop:
        pass
    assert not seen
