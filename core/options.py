"""Options research only. Indicative vendor snapshots, not executable quotes."""
from datetime import datetime, timezone

def rank_contracts(chain,underlying_price,budget=100,limit=10):
    out=[]
    for c in chain:
        try:
            bid=float(c.get('bid',0)); ask=float(c.get('ask',0));volume=int(c.get('volume') or 0); oi=int(c.get('openInterest') or 0)
            strike=float(c['strike']);exp=str(c['expiration']);right=str(c['right']).lower()
            if bid<0 or ask<=0 or ask<bid or right not in ('call','put'):continue
            mid=(ask+bid)/2; cost=ask*100; spread=(ask-bid)/mid if mid else 10
            if cost>budget or spread>0.25 or oi<50 or volume<5:continue
            score=(min(volume,1000)/1000+min(oi,5000)/5000)-spread-abs(strike-underlying_price)/max(underlying_price,1)
            out.append({'symbol':c.get('contractSymbol'),'strike':strike,'expiration':exp,'right':right,'bid':bid,'ask':ask,'estimated_ask_cost_per_contract':round(cost,2),'volume':volume,'open_interest':oi,'spread_pct':round(spread*100,2),'score':round(score,5),'snapshot_at':datetime.now(timezone.utc).isoformat(),'executable':False})
        except (KeyError,ValueError,TypeError):continue
    return sorted(out,key=lambda x:x['score'],reverse=True)[:limit]

def yfinance_contracts(symbol,max_expirations=3):
    import yfinance as yf
    t=yf.Ticker(symbol); options=[]
    for exp in list(t.options)[:max_expirations]:
        chain=t.option_chain(exp)
        for side,frame in [('call',chain.calls),('put',chain.puts)]:
            for c in frame.to_dict('records'):
                c['right']=side;c['expiration']=exp;options.append(c)
    return options
