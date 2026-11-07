"""Closed-bar trend diagnostics. Thresholds are research rules, not probabilities."""
import math


def trend_quality(df, side, window=20):
    if len(df) < max(window + 1, 30):
        return {'state': 'INSUFFICIENT_DATA', 'passes': False}
    c = df.Close.astype(float)
    if not all(math.isfinite(v) for v in c.tail(window + 1)):
        return {'state': 'INSUFFICIENT_DATA', 'passes': False}
    fast = c.ewm(span=9, adjust=False).mean()
    slow = c.ewm(span=21, adjust=False).mean()
    distance = float(c.diff().abs().tail(window).sum())
    efficiency = abs(float(c.iloc[-1] - c.iloc[-window-1])) / distance if distance else 0.0
    # Ignore equality when counting crosses, including flat sections.
    signs = (fast - slow).tail(window + 1).map(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
    signs = signs[signs != 0]
    crosses = int((signs.diff().dropna() != 0).sum())
    # Two completed non-overlapping windows: conservative HH/HL or LH/LL.
    old, recent = df.iloc[-10:-5], df.iloc[-5:]
    hh = recent.High.max() > old.High.max()
    hl = recent.Low.min() > old.Low.min()
    lh = recent.High.max() < old.High.max()
    ll = recent.Low.min() < old.Low.min()
    structure = 'BULLISH' if hh and hl else 'BEARISH' if lh and ll else 'MIXED'
    passes = side in ('BULLISH', 'BEARISH') and structure == side and efficiency >= .35 and crosses <= 2
    return {'state': 'TREND' if passes else 'CHOP_OR_UNCONFIRMED', 'passes': bool(passes),
            'structure': structure, 'efficiency': round(efficiency, 4), 'ema_crosses': crosses,
            'window': window, 'thresholds': {'min_efficiency': .35, 'max_crosses': 2},
            'method': 'EMA9/21 crossings and two completed five-bar structure windows; research rules, not win probability'}
