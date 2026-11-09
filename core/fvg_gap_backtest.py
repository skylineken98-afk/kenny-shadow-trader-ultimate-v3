"""Experimental 4H gap / sweep / reclaim research; standard-library CSV runner.
Timestamps are UTC-aware bar OPEN times. Inputs must contain completed bars.
No broker calls, automatic promotion, option fills, or profitability claims.
"""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path


def validate(rows, minutes):
    if not isinstance(minutes, int) or minutes < 1:
        raise ValueError('Positive integer bar duration required')
    result = []
    for row in rows:
        t = datetime.fromisoformat(str(row['timestamp']).replace('Z', '+00:00'))
        values = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
        o, h, l, c = values
        if t.tzinfo is None or not all(math.isfinite(x) and x > 0 for x in values):
            raise ValueError('Aware timestamps and finite positive prices required')
        if h < max(o, l, c) or l > min(o, h, c):
            raise ValueError('Invalid OHLC geometry')
        if result and t < result[-1]['end']:
            raise ValueError('Bars must be ordered, unique, and nonoverlapping')
        result.append(dict(t=t, end=t+timedelta(minutes=minutes), o=o, h=h, l=l, c=c))
    return result


def signals(context, triggers, *, trigger_minutes=1, lookback=20,
            expiry_bars=10, zone_age_hours=48, min_rr=1.5, target='midpoint'):
    """Bearish 4H gap approached from below -> long sweep/reclaim, and mirror.
    Freeze latest eligible gap and prior range at sweep time. Confirm on a later
    close beyond the opposite range boundary. No hand-drawn trendline fitting.
    """
    if not isinstance(lookback, int) or lookback < 2 or not isinstance(expiry_bars, int) or expiry_bars < 1:
        raise ValueError('Invalid lookback/expiry')
    if not math.isfinite(min_rr) or min_rr < 1.5 or not math.isfinite(zone_age_hours) or zone_age_hours <= 0:
        raise ValueError('Invalid RR/zone age')
    if target not in ('midpoint', 'far_edge'):
        raise ValueError('Unknown target')
    h = validate(context, 240)
    b = validate(triggers, trigger_minutes)
    gaps = []
    for i in range(2, len(h)):
        a, c = h[i-2], h[i]
        # Exclude three-bar patterns straddling missing 4H intervals.
        if h[i-1]['t'] != a['end'] or c['t'] != h[i-1]['end']:
            continue
        if c['h'] < a['l']:
            gaps.append(dict(available=c['end'], lo=c['h'], hi=a['l'], side=1))
        elif c['l'] > a['h']:
            gaps.append(dict(available=c['end'], lo=a['h'], hi=c['l'], side=-1))
    output = []
    pending = None
    for i in range(lookback, len(b)):
        bar = b[i]
        # Never bridge missing trigger bars with a pending setup.
        if i and bar['t'] != b[i-1]['end']:
            pending = None
        if pending:
            p = pending
            invalid = bar['l'] <= p['stop'] if p['side'] == 1 else bar['h'] >= p['stop']
            if invalid or i > p['expires']:
                pending = None
            elif p['side']*(bar['c']-p['boundary']) > 0:
                risk = p['side']*(bar['c']-p['stop'])
                reward = p['side']*(p['target']-bar['c'])
                if risk > 0 and reward/risk >= min_rr:
                    output.append(dict(index=i, decision_at=bar['end'].isoformat(),
                                       side=p['side'], stop=p['stop'], target=p['target'],
                                       sweep_at=p['sweep_at'], gap_available_at=p['available'].isoformat()))
                pending = None
            continue
        prior = b[i-lookback:i]
        if any(prior[j]['end'] != prior[j+1]['t'] for j in range(len(prior)-1)) or prior[-1]['end'] != bar['t']:
            continue
        lo, hi = min(x['l'] for x in prior), max(x['h'] for x in prior)
        if bar['l'] < lo and bar['h'] > hi:
            continue
        side = 1 if bar['l'] < lo < bar['c'] else (-1 if bar['h'] > hi > bar['c'] else 0)
        if not side:
            continue
        eligible = [g for g in gaps if g['side'] == side and g['available'] <= bar['t']
                    and bar['t']-g['available'] <= timedelta(hours=zone_age_hours)
                    and (bar['c'] < g['lo'] if side == 1 else bar['c'] > g['hi'])]
        if not eligible:
            continue
        g = eligible[-1]
        # Reject zones already traversed after formation (observed trigger history).
        history = [x for x in b[:i] if x['t'] >= g['available']]
        if any(x['h'] >= g['hi'] if side == 1 else x['l'] <= g['lo'] for x in history):
            continue
        level = (g['lo']+g['hi'])/2 if target == 'midpoint' else (g['hi'] if side == 1 else g['lo'])
        pending = dict(g, side=side, stop=bar['l'] if side == 1 else bar['h'],
                       target=level, boundary=hi if side == 1 else lo,
                       expires=i+expiry_bars, sweep_at=bar['end'].isoformat())
    return output


def backtest(context, triggers, *, trigger_minutes=1, max_hold=60,
             fee_bps=5, slippage_bps=5, entry_from=None, **kwargs):
    if not isinstance(max_hold, int) or max_hold < 1:
        raise ValueError('Positive holding period required')
    if any(not math.isfinite(x) or not 0 <= x <= 500 for x in (fee_bps, slippage_bps)):
        raise ValueError('Invalid costs')
    b = validate(triggers, trigger_minutes)
    records, occupied = [], -1
    for s in signals(context, triggers, trigger_minutes=trigger_minutes, **kwargs):
        i, side = s['index']+1, s['side']
        if i >= len(b) or i <= occupied or b[i]['t'] != b[i-1]['end']:
            continue
        if entry_from and b[i]['t'] < datetime.fromisoformat(entry_from.replace('Z', '+00:00')):
            continue
        entry = b[i]['o']
        risk, reward = side*(entry-s['stop']), side*(s['target']-entry)
        if risk <= 0 or reward/risk < kwargs.get('min_rr', 1.5):
            continue
        end = min(i+max_hold-1, len(b)-1)
        price, reason = b[end]['c'], 'time_or_data_end'
        for j in range(i, end+1):
            x = b[j]
            if j > i and x['t'] != b[j-1]['end']:
                end, price, reason = j-1, b[j-1]['c'], 'data_gap'
                break
            stop_hit = x['l'] <= s['stop'] if side == 1 else x['h'] >= s['stop']
            target_hit = x['h'] >= s['target'] if side == 1 else x['l'] <= s['target']
            if stop_hit:
                end, price, reason = j, min(x['o'], s['stop']) if side == 1 else max(x['o'], s['stop']), 'stop'
                break
            if target_hit:
                end, price, reason = j, s['target'], 'target'
                break
        net = side*(price/entry-1)-2*(fee_bps+slippage_bps)/10000
        records.append(dict(s, entry_at=b[i]['t'].isoformat(), exit_at=b[end]['end'].isoformat(),
                            entry=entry, exit=price, reason=reason, net_return=net, net_r=net*entry/risk))
        occupied = end
    returns = [r['net_return'] for r in records]
    return dict(strategy='four_hour_gap_sweep_reclaim_v1', status='DESCRIPTIVE_SIMULATION',
                research_only=True, option_returns=False, auto_promote=False,
                records=records, trades=len(records),
                win_rate=sum(x > 0 for x in returns)/len(returns) if returns else None,
                expectancy=sum(returns)/len(returns) if returns else None,
                parameters=dict(trigger_minutes=trigger_minutes, max_hold=max_hold,
                                fee_bps=fee_bps, slippage_bps=slippage_bps, entry_from=entry_from, **kwargs))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context', required=True)
    p.add_argument('--triggers', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--phase', choices=['historical', 'holdout', 'paper'], required=True)
    p.add_argument('--trigger-minutes', type=int, default=1)
    p.add_argument('--target', choices=['midpoint', 'far_edge'], default='midpoint')
    p.add_argument('--entry-from', help='Timezone-aware start for holdout entries; retain earlier warmup bars')
    args = p.parse_args()
    paths = [Path(args.context), Path(args.triggers)]
    rows = []
    for path in paths:
        with path.open() as f:
            rows.append(list(csv.DictReader(f)))
    result = backtest(*rows, trigger_minutes=args.trigger_minutes, target=args.target, entry_from=args.entry_from)
    result.update(phase=args.phase, dataset_sha256=[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths])
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
