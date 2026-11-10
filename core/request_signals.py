"""Read-only V3 option contract discovery. Never places trades or invents vendor quotes."""
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo
import math
from core.flow_intelligence import alignment_bonus
from core.affordable_options import screening_policy, price_quality

CATEGORIES = ('0DTE', 'Swings', 'LEAPS')

def dte_group(expiration, today):
    try: days = (date.fromisoformat(str(expiration)[:10]) - today).days
    except (TypeError, ValueError): return None
    if days == 0: return '0DTE'
    if 5 <= days <= 45: return 'Swings'
    if days >= 365: return 'LEAPS'
    return None

def to_float(value, default=None):
    try:
        n=float(value)
        return n if math.isfinite(n) else default
    except (ValueError, TypeError):return default

def quote_timestamp(value):
    if value is None: return None
    try:
        import pandas as pd
        x=pd.Timestamp(value)
        if pd.isna(x):return None
        return x.tz_localize('UTC').to_pydatetime() if x.tzinfo is None else x.to_pydatetime().astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError):return None

def rank_row(raw, ticker, expiration, right, underlying, direction, budget, now, max_age_hours=48, flow=None):
    if direction not in ('BULLISH','BEARISH'):return None
    if right != ('call' if direction=='BULLISH' else 'put'):return None
    bid=to_float(raw.get('bid')); ask=to_float(raw.get('ask'))
    price=to_float(raw.get('lastPrice'));strike=to_float(raw.get('strike'))
    vol=to_float(raw.get('volume'),0); oi=to_float(raw.get('openInterest'),0)
    contract=raw.get('contractSymbol')
    if not isinstance(contract,str) or not contract.strip() or strike is None:return None
    if bid is None or ask is None:return None
    quality, rejection = price_quality(bid, ask, budget, vol, oi)
    if rejection:return None
    spread=(ask-bid)/((ask+bid)/2)
    ts=quote_timestamp(raw.get('lastTradeDate'))
    # Vendor lastTradeDate is a trade timestamp, not a timestamp for the current bid/ask quote.
    # Do not present stale option snapshots as current executable quotations.
    if ts is None or ts>now+timedelta(minutes=5) or now-ts>timedelta(hours=max_age_hours):return None
    pct=to_float(raw.get('percentChange'))
    change=to_float(raw.get('change'))
    # Quote quality/contract liquidity/strike proximity rather than fabricated win probability.
    proximity=abs(strike-underlying)/underlying if underlying>0 else 1
    allowed_spread=screening_policy(budget)['max_spread_pct']/100
    score=round(100*(0.40*max(0,1-spread/allowed_spread)+0.30*min(vol/250,1)+0.20*min(oi/2000,1)+0.10*max(0,1-min(proximity/0.15,1))),2)
    return {'ticker':ticker,'contract':contract,'expiration':expiration,'right':right.upper(), 'strike':strike,
        'bid':bid,'ask':ask,'last':price,'change':change,'percent_change':pct,
        'high':to_float(raw.get('dayHigh')),'low':to_float(raw.get('dayLow')),
        'open':to_float(raw.get('open')),'previous_close':None,
        'volume':int(vol),'open_interest':int(oi),'spread_pct':round(spread*100,1),
        'cost':round(ask*100,2),'price_band':quality['premium_band'],
        'liquidity_label':quality['liquidity_label'], 'estimated_roundtrip_spread_cost':quality['estimated_roundtrip_spread_cost'], 'verified_executable':False,'rank_score':round(score + alignment_bonus(flow, direction), 2), 'base_contract_score':score, 'flow':flow, 'quote_warning':'Indicative bid/ask; vendor does not supply a verified quote timestamp',
        'last_trade_at':ts.isoformat(),'data_checked_at':now.isoformat(),'direction':direction,
        'entry_note':'No executable entry/stop/target without an option-premium risk model'}

def discover_contracts(tickers, budget=300, now=None, ticker_factory=None, analyzer=None, per_category=3, flow_provider=None):
    """Find at most three unique option contracts per expiration category across supplied underlyings.
    Requires real yfinance chains; never produces mock market values in production.
    """
    now=now or datetime.now(timezone.utc)
    today=now.astimezone(ZoneInfo('America/New_York')).date()
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory=yf.Ticker
    if analyzer is None:
        from core.market import confluence
        analyzer=confluence
    if flow_provider is None:
        from core.market import history
        from core.flow_intelligence import measure_flow
        def flow_provider(symbol):
            return measure_flow(history(symbol, period='2mo', interval='1d'))
    results={group:[] for group in CATEGORIES}; notices=[]
    policy=screening_policy(budget)
    budget=float(budget)
    notices.append(f'Budget ${budget:g}: price screening allows up to {policy["max_spread_pct"]:g}% spreads, volume >= {policy["min_volume"]}, OI >= {policy["min_oi"]}; speculative candidates are flagged, not asserted profitable')
    unique=list(dict.fromkeys(str(t).upper().strip() for t in tickers if str(t).strip()))
    for symbol in unique:
        try:
            analysis=analyzer(symbol)
            if analysis.get('status')!='SETUP' or analysis.get('side') not in ('BULLISH','BEARISH'):
                notices.append(f'{symbol}: no fresh momentum-plus-volume setup; skipped');continue
            underlying=to_float(analysis.get('entry') or analysis.get('price'))
            if not underlying or underlying<=0:continue
            # Missing flow data does not fabricate money flows or block otherwise valid ideas.
            try: flow = flow_provider(symbol)
            except Exception:
                flow = None
                notices.append(f'{symbol}: OHLCV flow data unavailable')
            ticker=ticker_factory(symbol)
            groups={g:[] for g in CATEGORIES}
            for exp in ticker.options or []:
                group=dte_group(exp,today)
                if group:groups[group].append(exp)
            for group,expirations in groups.items():
                for exp in expirations[:(2 if group=='Swings' else 3)]:
                    try:
                        chain=ticker.option_chain(exp)
                        right='call' if analysis['side']=='BULLISH' else 'put'
                        frame=chain.calls if right=='call' else chain.puts
                        for row in frame.to_dict('records'):
                            record=rank_row(row,symbol,exp,right,underlying,analysis['side'],budget,now,
                                            max_age_hours=(24 if group=='0DTE' else 72), flow=flow)
                            if record:
                                record['category']=group
                                record['underlying_price']=underlying
                                results[group].append(record)
                    except Exception as exc: notices.append(f'{symbol} {exp}: chain unavailable ({type(exc).__name__})')
        except Exception as exc: notices.append(f'{symbol}: data unavailable ({type(exc).__name__})')
    for group in CATEGORIES:
        ranked=sorted(results[group],key=lambda r:(r['rank_score'],r['volume'],r['open_interest']),reverse=True)
        selected=[];seen=set()
        for r in ranked:
            if r['contract'] in seen:continue
            seen.add(r['contract']);selected.append(r)
            if len(selected)==per_category:break
        results[group]=selected
    return results, notices
