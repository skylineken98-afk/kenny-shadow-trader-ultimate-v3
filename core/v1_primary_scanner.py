"""V1 contract selection, extracted from legacy_v1/option_scanner.py.
Read-only Alpaca snapshot research. V1 ranks by raw quality; display is clamped.
No credentials, no signal. No stock/crypto orders or broker execution.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import math
import os
from core.request_signals import CATEGORIES, dte_group
from core.affordable_options import screening_policy, price_quality


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def original_v1_score(ask, spread_pct, delta, max_premium):
    """Original Oct-5-era formula, with unchanged raw score for sort order."""
    score = 100.0 - spread_pct * 2
    # Do not penalize cheap premiums solely for being cheap; penalize spread risk instead.
    if ask <= max_premium:
        score += 5
    if delta is not None:
        a = abs(delta)
        if 0.30 <= a <= 0.70:
            score += 15
        elif 0.20 <= a < 0.30:
            score += 7
        elif a < 0.15:
            score -= 30
    return score


def bounded_score(raw):
    return round(max(0., min(100., raw)), 1)


def snapshot_candidate(contract, snapshot, budget, today, now=None, max_spread=None):
    """V1 bid/ask/spread and delta filter, plus explicit quote-timestamp guard.
    Valid Alpaca option OCC symbol is required. Missing timestamps are labeled
    unverified (not described as live quotes).
    """
    if not isinstance(contract, str) or len(contract) < 16:
        return None
    try:
        expiry = datetime.strptime(contract[-15:-9], '%y%m%d').date()
        right = {'C':'CALL','P':'PUT'}[contract[-9]]
        strike = int(contract[-8:]) / 1000
    except (ValueError, KeyError):
        return None
    group = dte_group(expiry.isoformat(), today)
    if group is None:
        return None
    quote = getattr(snapshot, 'latest_quote', None)
    if quote is None:
        return None
    bid = number(getattr(quote, 'bid_price', None))
    ask = number(getattr(quote, 'ask_price', None))
    if bid is None or ask is None:
        return None
    quality, rejection = price_quality(bid, ask, budget)
    if rejection:
        return None
    spread_pct = quality['spread_pct']
    if max_spread is not None and spread_pct > max_spread:
        return None
    greeks = getattr(snapshot, 'greeks', None)
    delta = number(getattr(greeks, 'delta', None)) if greeks else None
    raw_score = original_v1_score(ask,spread_pct,delta,budget/100)
    trade = getattr(snapshot, 'latest_trade', None)
    last = number(getattr(trade, 'price', None)) if trade else None
    stamp = getattr(quote, 'timestamp', None)
    now = now or datetime.now(timezone.utc)
    if isinstance(stamp, datetime):
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = (now - stamp.astimezone(timezone.utc)).total_seconds()
        if age < -300 or age > (24*3600 if group=='0DTE' else 72*3600):
            return None
        stamp_text = stamp.isoformat()
        warning = 'Alpaca option snapshot; verify exchange quote and trading eligibility before entry'
    else:
        stamp_text = 'unknown'
        warning = 'Quote timestamp is unavailable; cannot verify quote freshness or execution price'
    underlying = contract[:-15]
    return {'ticker':underlying, 'contract':contract, 'expiration':expiry.isoformat(),
        'category':group, 'right':right, 'strike':strike,
        'bid':bid,'ask':ask,'last':last,'percent_change':None,
        'cost':round(ask*100,2), 'spread_pct':round(spread_pct,2),
        'delta':delta,'volume':None,'open_interest':None,
        'rank_score':bounded_score(raw_score),'raw_rank_score':round(raw_score,3),
        'base_contract_score':bounded_score(raw_score),
        'last_trade_at':stamp_text, 'quote_warning':warning,
        'liquidity_label':quality['liquidity_label'],
        'premium_band':quality['premium_band'],
        'estimated_roundtrip_spread_cost':quality['estimated_roundtrip_spread_cost'],
        'verified_executable':False,
        'data_checked_at':now.isoformat(), 'source':'V1 Alpaca contract scanner'}


def discover_v1_contracts(tickers, budget=100, per_category=3, now=None,
                          client=None, analyzer=None):
    """Apply V1 scoring to genuine Alpaca option snapshots, ranking before clamping.
    Optional technical analyzer selects call/put directional candidates; no
    fabricated candidate when technical signal unavailable.
    """
    from core.market import confluence
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo('America/New_York')).date()
    notices=[]
    policy=screening_policy(budget)
    notices.append(f'Budget tier ${budget:g}: max spread {policy["max_spread_pct"]:g}%, minimum volume {policy["min_volume"]}, OI {policy["min_oi"]} when provided; low-premium candidates marked speculative')
    if client is None:
        key = os.getenv('ALPACA_API_KEY')
        secret = os.getenv('ALPACA_API_SECRET')
        if not key or not secret:
            return {g:[] for g in CATEGORIES}, ['V1 primary scanner requires ALPACA_API_KEY and ALPACA_API_SECRET; no fallback was substituted.']
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            client=OptionHistoricalDataClient(key, secret)
        except ImportError:
            return {g:[] for g in CATEGORIES}, ['alpaca-py is not installed. Install project requirements.']
    if analyzer is None:
        analyzer=confluence
    out={g:[] for g in CATEGORIES}
    try:
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        if client is not None and not hasattr(client, 'request_chain'):
            return out,['alpaca-py is not installed.']
        OptionChainRequest=None
    for ticker in dict.fromkeys(str(t).upper().strip() for t in tickers if str(t).strip()):
        try:
            a=analyzer(ticker)
            if a.get('status')!='SETUP' or a.get('side') not in ('BULLISH','BEARISH'):
                notices.append(ticker+': no confirmed trend setup');continue
            wanted='CALL' if a['side']=='BULLISH' else 'PUT'
            if OptionChainRequest is None:
                chain=client.request_chain(ticker)
            else:
                chain=client.get_option_chain(OptionChainRequest(underlying_symbol=ticker))
            for contract,snapshot in chain.items():
                row=snapshot_candidate(contract,snapshot,budget,today,now)
                if row and row['right']==wanted:
                    row['direction']=a['side']
                    out[row['category']].append(row)
        except Exception as exc:
            notices.append(f'{ticker}: V1 chain scan unavailable ({type(exc).__name__})')
    for group in CATEGORIES:
        out[group].sort(key=lambda x:x['raw_rank_score'],reverse=True)
        out[group]=out[group][:per_category]
    return out, notices
