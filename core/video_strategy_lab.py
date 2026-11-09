"""Video-inspired hypotheses. Rules below are KST approximations, not creator replicas.
Input timestamps denote completed bars. No live execution or automatic promotion.
"""
import json
import math
from pathlib import Path
from core.strategy_discovery import _bars

CANDIDATES = {
    'swing_sweep_reclaim_v1': {'status': 'backtest_ready', 'data': 'completed OHLCV', 'rule': 'Sweep prior 20-bar extreme and close back inside; next-open entry; five-bar hold.'},
    'session_sweep_reclaim_v1': {'status': 'needs_session_rules', 'data': 'intraday OHLCV plus timezone and session calendar'},
    'sharp_drop_reversal_v1': {'status': 'needs_entry_rules', 'data': 'completed OHLCV'},
    'absorption_profile_v1': {'status': 'needs_order_flow', 'data': 'timestamped aggressor-side trades, bid/ask and volume-at-price'},
}

def sweep_decisions(bars, lookback=20):
    b = _bars(bars)
    if not isinstance(lookback, int) or not 2 <= lookback <= 250:
        raise ValueError('Invalid lookback')
    high = b.High.shift(1).rolling(lookback).max()
    low = b.Low.shift(1).rolling(lookback).min()
    long = (b.Low < low) & (b.Close > low) & (b.Close > b.Open)
    short = (b.High > high) & (b.Close < high) & (b.Close < b.Open)
    # A bar sweeping both sides is ambiguous; abstain.
    ambiguous = (b.Low < low) & (b.High > high)
    return (long.astype(int) - short.astype(int)).mask(ambiguous, 0)

def backtest(bars, strategy='swing_sweep_reclaim_v1', lookback=20,
             holding_bars=5, fee_bps=5, slippage_bps=5, entry_from=None):
    if strategy not in CANDIDATES:
        raise ValueError('Unknown strategy')
    spec = CANDIDATES[strategy]
    if spec['status'] != 'backtest_ready':
        return {'strategy': strategy, 'status': spec['status'], 'records': [], 'research_only': True}
    b = _bars(bars)
    if not isinstance(holding_bars, int) or not 1 <= holding_bars <= 50:
        raise ValueError('Invalid holding period')
    costs = [float(fee_bps), float(slippage_bps)]
    if any(not math.isfinite(x) or x < 0 or x > 500 for x in costs):
        raise ValueError('Invalid costs')
    d = sweep_decisions(b, lookback)
    records = []
    i = lookback + 1
    while i + holding_bars < len(b):
        if entry_from is not None and b.index[i] < entry_from:
            i += 1
            continue
        direction = int(d.iloc[i-1])
        if not direction:
            i += 1
            continue
        entry, exit_price = float(b.Open.iloc[i]), float(b.Open.iloc[i+holding_bars])
        records.append({'decision_at': str(b.index[i-1]), 'entry_at': str(b.index[i]),
                        'exit_at': str(b.index[i+holding_bars]), 'direction': direction,
                        'net_return': direction*(exit_price/entry-1)-2*sum(costs)/10000})
        i += holding_bars + 1
    rr = [r['net_return'] for r in records]
    return {'strategy': strategy, 'status': 'DESCRIPTIVE_SIMULATION', 'records': records,
            'trades': len(rr), 'win_rate': sum(x>0 for x in rr)/len(rr) if rr else None,
            'expectancy': sum(rr)/len(rr) if rr else None,
            'research_only': True, 'option_returns': False, 'auto_promote': False,
            'parameters': {'lookback': lookback, 'holding_bars': holding_bars,
                           'fee_bps': fee_bps, 'slippage_bps': slippage_bps}}

def append_run(path, result, *, dataset_id, phase):
    """Persist separate historical/holdout/paper results; caller schedules real runs.

    Dataset ID should identify an immutable snapshot. No scheduler is installed here.
    """
    if phase not in ('historical', 'holdout', 'paper') or not dataset_id:
        raise ValueError('Dataset ID and valid phase required')
    payload = dict(result, dataset_id=dataset_id, phase=phase)
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, allow_nan=False, sort_keys=True)+'\n')
