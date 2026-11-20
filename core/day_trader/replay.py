"""Replay KST's completed-bar momentum rule on underlying OHLCV."""
from math import isfinite

from core.day_trader.simulation import build_pool, simulate
from core.momentum_scalper import _confirmed_momentum


def opening_replay(candles, symbol, *, minutes=1, cost_bps=4, paths=10000):
    """One signal per session, next-open entry, stop-first ambiguous bars."""
    if minutes not in (1, 5) or not 0 <= cost_bps <= 100 or not 1 <= paths <= 10000:
        raise ValueError("Invalid replay interval, cost or path count")
    if candles.empty:
        return {"trades": [], "simulation": None, "sessions": 0}
    if candles.index.tz is None or candles.index.has_duplicates:
        raise ValueError("Replay requires unique timezone-aware candle timestamps")
    frame = candles.sort_index().tz_convert("America/New_York")
    frame = frame.between_time("09:30", "15:59")
    trades = []
    simulation_plan = None
    pool_sessions = []
    sessions = 0
    for day, session in frame.groupby(frame.index.date):
        bars = []
        for stamp, row in session.iterrows():
            offset = stamp.hour * 60 + stamp.minute - 570
            if offset != len(bars) * minutes:
                break
            o, h, l, c, v = map(float, row[["Open", "High", "Low", "Close", "Volume"]])
            if not all(map(isfinite, (o, h, l, c, v))) or not 0 < l <= min(o, c) <= max(o, c) <= h or v < 0:
                break
            bars.append(dict(t=stamp.isoformat(), o=o, h=h, l=l, c=c, v=v, complete=True))
        horizon = 30 // minutes
        # Require the entire 9:30–10:00 ET research window.
        if len(bars) < horizon:
            continue
        sessions += 1
        for i in range(1, horizon - 1):
            signal = _confirmed_momentum(symbol, bars[:i + 1])
            if signal["status"] != "PAPER_CANDIDATE":
                continue
            sign = 1 if signal["direction"] == "BULLISH" else -1
            entry_bar = bars[i + 1]
            entry = entry_bar["o"]
            stop = bars[i]["l" if sign == 1 else "h"]
            risk = sign * (entry - stop)
            if risk <= 0:
                break
            target = entry + sign * 1.5 * risk
            exit_price = bars[horizon - 1]["c"]
            outcome = "time exit"
            for bar in bars[i + 1:horizon]:
                adverse = bar["l" if sign == 1 else "h"]
                favorable = bar["h" if sign == 1 else "l"]
                if sign * (adverse - stop) <= 0:
                    outcome = "stop"
                    exit_price = min(stop, bar["o"]) if sign == 1 else max(stop, bar["o"])
                    break
                if sign * (favorable - target) >= 0:
                    outcome, exit_price = "target", target
                    break
            trades.append(dict(date=str(day), entry_time=entry_bar["t"], direction=signal["direction"],
                               entry=entry, stop=stop, target=target, outcome=outcome,
                               net_pct=100 * sign * (exit_price - entry) / entry - cost_bps / 100))
            # Five-minute model starts after the entry bar. Use only prior full sessions.
            if minutes == 5 and len(pool_sessions) >= 5 and i + 2 < horizon:
                if entry_bar["l"] > min(stop, target) and entry_bar["h"] < max(stop, target):
                    simulation_plan = (day, len(pool_sessions), entry_bar["c"], stop, target, i + 1, sign)
            break
        if minutes == 5 and len(bars) == 78:
            pool_sessions.append((day, bars))
    simulation = None
    if simulation_plan:
        day, prior_count, entry, stop, target, entry_index, sign = simulation_plan
        model = simulate(build_pool(pool_sessions[:prior_count]), entry, stop, target,
                         entry_index, 5, replays=paths, window=0,
                         side="buy" if sign == 1 else "sell")
        simulation = {key: model[key] for key in
                      ("p_target", "p_stop", "p_neither", "replays", "seed")}
        simulation.update(date=str(day), prior_sessions=prior_count)
    return {"trades": trades, "simulation": simulation, "sessions": sessions}
