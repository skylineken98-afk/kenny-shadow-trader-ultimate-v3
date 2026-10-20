"""Deterministic, read-only opportunity scoring. No order placement.

Inputs are pre-fetched evidence with explicit provenance. SEC disclosures and FINRA
aggregates are NOT current institutional inflows. Scores are research rankings,
not odds of profit, fair values, or investment recommendations.
"""
import math
from datetime import datetime, timezone


def _number(value):
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def score_opportunity(contract, *, flow=None, fundamentals=None, finra=None, catalyst=None):
    """Rank a previously discovered options contract without manufacturing data.

    fundamentals: {'estimated_fair_value':number,'market_price':number,
                   'as_of':'YYYY-MM-DD','method':str}; supplied by a separate
                   independently justified valuation model, NOT SEC raw filings.
    finra: {'short_interest_pct_float':number,'as_of':str,'source':str}
    catalyst: {'direction':'BULLISH'|'BEARISH','verified':bool,'as_of':str}
    """
    direction = contract.get('direction')
    right = contract.get('right', '').upper()
    if direction not in ('BULLISH', 'BEARISH') or right != ('CALL' if direction == 'BULLISH' else 'PUT'):
        raise ValueError('Contract direction and option right must agree')
    base = _number(contract.get('base_contract_score', contract.get('rank_score')))
    if base is None or not 0 <= base <= 100:
        raise ValueError('Verified base contract score 0..100 required')
    evidence = []; missing = []; adjustment = 0.0
    if flow and flow.get('direction') == direction:
        rv = _number(flow.get('relative_volume'))
        cmf = _number(flow.get('chaikin_money_flow'))
        if rv is not None and cmf is not None:
            # CMF may proxy pressure but does not identify the counterparties.
            p = min(8., max(0., rv - 1.) * 3. + max(0., abs(cmf)) * 9.)
            adjustment += p
            evidence.append({'kind':'ohlcv_pressure','points':round(p,2), 'rvol':rv, 'cmf':cmf,
                             'disclosure':'Estimated from candles; not measured institutional inflow'})
        else: missing.append('volume/price flow measurements')
    else: missing.append('aligned directional OHLCV flow')
    if fundamentals:
        fair = _number(fundamentals.get('estimated_fair_value'))
        price = _number(fundamentals.get('market_price'))
        method = fundamentals.get('method')
        when = fundamentals.get('as_of')
        if fair is not None and price is not None and fair > 0 and price > 0 and method and when:
            discount = (fair / price - 1) * 100
            aligned = discount > 0 if direction == 'BULLISH' else discount < 0
            p = min(abs(discount)/10, 5.) if aligned else 0.
            adjustment += p
            evidence.append({'kind':'model_valuation','points':round(p,2),
                             'model_gap_pct':round(discount,2), 'method':method,'as_of':when,
                             'disclosure':'Model-dependent stock estimate, NOT undervalued option premium'})
        else: missing.append('defensible, dated stock valuation')
    else: missing.append('stock valuation model')
    if finra:
        interest = _number(finra.get('short_interest_pct_float'))
        when = finra.get('as_of'); source = finra.get('source')
        if interest is not None and 0 <= interest <= 100 and when and source:
            evidence.append({'kind':'short_interest_context', 'points':0., 'percent_float':interest,
                             'as_of':when,'source':source,
                             'disclosure':'Delayed positioning context, not trade direction or net inflow'})
        else: missing.append('dated, sourced FINRA metric')
    else: missing.append('FINRA positioning context')
    if catalyst and catalyst.get('verified') is True and catalyst.get('as_of') and catalyst.get('direction') == direction:
        adjustment += 2.
        evidence.append({'kind':'verified_catalyst','points':2.,'as_of':catalyst['as_of']})
    else: missing.append('verified aligned catalyst')
    score = round(min(100., base * 0.85 + adjustment), 2)
    return {'contract':contract.get('contract'), 'ticker':contract.get('ticker'),
            'direction':direction,'right':right,'category':contract.get('category'),
            'score':score,'base_contract_score':base,'estimated_ask_cost':contract.get('cost'),
            'evidence':evidence,'missing_evidence':missing,
            'scored_at':datetime.now(timezone.utc).isoformat(), 'executable':False,
            'warning':'Research ranking only; unverified live quotes, no estimated profit probability'}


def rank_opportunities(contracts, evidence_by_ticker=None, limit=3):
    """Returns separate Top bullish calls and bearish puts; never forces a trade."""
    if not isinstance(limit,int) or not 1 <= limit <= 100: raise ValueError('limit must be 1..100')
    context=evidence_by_ticker or {}
    results={'BULLISH':[], 'BEARISH':[]}; errors=[]
    for contract in contracts:
        try:
            inputs=context.get(contract.get('ticker'), {})
            item=score_opportunity(contract, **{k:inputs.get(k) for k in ('flow','fundamentals','finra','catalyst')})
            results[item['direction']].append(item)
        except (ValueError,TypeError,AttributeError) as exc:
            errors.append(f"{contract.get('contract','unknown')}: {type(exc).__name__}")
    for side in results:
        results[side]=sorted(results[side], key=lambda r:r['score'], reverse=True)[:limit]
    return {'top_calls': results['BULLISH'], 'top_puts':results['BEARISH'], 'skipped':errors,
            'disclosure':'Scores are deterministic research heuristics, not trading advice or verified net inflow'}
