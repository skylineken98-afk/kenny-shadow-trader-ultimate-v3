"""Sequential candle-based sweep/BOS/FVG detector; no orders or flow claims.

Input timestamps are bar OPEN times. Only fully closed, timezone-aware bars
are eligible. The 4h context must be supplied separately from 15m triggers.
"""
import pandas as pd
import numpy as np


def closed_bars(frame, minutes, now):
    columns = ['Open', 'High', 'Low', 'Close']
    if not isinstance(frame, pd.DataFrame) or not set(columns).issubset(frame):
        raise ValueError('OHLC bars required')
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError('Ordered unique timezone-aware timestamps required')
    now = pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware now required')
    d = frame.loc[frame.index + pd.Timedelta(minutes=minutes) <= now, columns].astype(float)
    if not np.isfinite(d.to_numpy()).all() or (d <= 0).any().any() or (d.High < d[['Open', 'Close', 'Low']].max(axis=1)).any() or (d.Low > d[['Open', 'Close', 'High']].min(axis=1)).any():
        raise ValueError('Invalid OHLC values')
    return d


def liquidity_fvg_setup(context, triggers, now, lookback=12, expiry_bars=16, min_rr=1.5):
    """4h support/resistance -> 15m sweep -> close BOS -> FVG -> retest.

    Context zone: prior twelve 4h lows/highs, padded by 25% mean range.
    Sweep reclaims prior 15m range; BOS closes beyond its opposite boundary.
    Displacement body >= prior mean range. FVG is a strict three-bar gap.
    Confirmation closes beyond the gap on a later retest; entry is that close.
    Stops sit beyond the sweep; targets use pre-sweep 4h range extremes.
    Only a confirmation on the latest closed trigger bar returns SETUP.
    """
    if lookback < 3 or expiry_bars < 3 or not np.isfinite(min_rr) or min_rr < 1.5:
        raise ValueError('Invalid setup parameters')
    h = closed_bars(context, 240, now)
    b = closed_bars(triggers, 15, now)
    wait = {'status': 'WAIT', 'side': 'WAIT', 'strategy': 'LIQUIDITY_SWEEP_BOS_FVG', 'confidence_label': 'RULE_BASED_ONLY'}
    if len(h) < 12 or len(b) < lookback + 4:
        return dict(wait, reason='INSUFFICIENT_DATA')
    if pd.Timestamp(now) - (b.index[-1] + pd.Timedelta(minutes=15)) > pd.Timedelta(minutes=15):
        return dict(wait, reason='STALE_TRIGGER_DATA')
    for s in range(max(lookback, len(b)-expiry_bars), len(b)-3):
        # Context is frozen at sweep open, never using a later 4h candle.
        ctx = h.loc[h.index + pd.Timedelta(hours=4) <= b.index[s]].tail(12)
        if len(ctx) < 12 or b.index[s]-(ctx.index[-1]+pd.Timedelta(hours=4)) > pd.Timedelta(hours=4):
            continue
        prior = b.iloc[s-lookback:s]
        lo, hi = float(prior.Low.min()), float(prior.High.max())
        pad = float((ctx.High-ctx.Low).mean())*.25
        for direction in (1, -1):
            sweep = b.iloc[s]
            valid = (sweep.Low < lo and sweep.Close > lo and abs(sweep.Low-ctx.Low.min()) <= pad) if direction == 1 else (sweep.High > hi and sweep.Close < hi and abs(sweep.High-ctx.High.max()) <= pad)
            if not valid:
                continue
            stop = float(sweep.Low-pad*.1 if direction == 1 else sweep.High+pad*.1)
            target = float(ctx.High.max() if direction == 1 else ctx.Low.min())
            bos = None
            gap = None
            for j in range(s+1, len(b)):
                bar = b.iloc[j]
                if (bar.Low <= stop if direction == 1 else bar.High >= stop):
                    break
                if bos is None:
                    average = float((b.High-b.Low).iloc[max(0,j-lookback):j].mean())
                    if direction*(bar.Close-(hi if direction == 1 else lo)) > 0 and direction*(bar.Close-bar.Open) >= average:
                        bos = j
                if gap is None and bos is not None and j >= 2 and j-1 >= bos:
                    a = b.iloc[j-2]
                    if direction == 1 and bar.Low > a.High:
                        gap = (float(a.High), float(bar.Low), j)
                    elif direction == -1 and bar.High < a.Low:
                        gap = (float(bar.High), float(a.Low), j)
                    continue
                if gap is None:
                    continue
                lower, upper, formed = gap
                if (bar.Close < lower if direction == 1 else bar.Close > upper):
                    break
                touched = bar.Low <= upper and bar.High >= lower
                confirmed = bar.Close > upper if direction == 1 else bar.Close < lower
                if touched and confirmed:
                    entry = float(bar.Close)
                    risk, reward = direction*(entry-stop), direction*(target-entry)
                    if j == len(b)-1 and risk > 0 and reward/risk >= min_rr:
                        return dict(wait, status='SETUP', side='BULLISH' if direction == 1 else 'BEARISH', entry=entry, stop=stop, target=target, reward_risk=reward/risk, fvg=[lower,upper], sweep_at=b.index[s].isoformat(), bos_at=b.index[bos].isoformat(), confirmed_at=b.index[j].isoformat(), data_warning='OHLC pattern; liquidity is inferred, not verified order flow. Underlying levels are not option premium levels.')
                    break  # Consume the first confirmed retest, never reissue it.
    return wait
