from collections import Counter

def summarize_signals(rows):
    statuses=Counter(str(r.get('status','UNKNOWN')) for r in rows)
    symbols=Counter(str(r.get('symbol','UNKNOWN')) for r in rows)
    return {'rows':len(rows),'statuses':dict(statuses),'symbols':dict(symbols),
            'disclaimer':'Signal counts only; not accuracy, performance or realized returns.'}

def paper_metrics(positions):
    closed=[p for p in positions if p.get('status')=='CLOSED' and p.get('realized_pnl') is not None]
    pnl=sum(float(p['realized_pnl']) for p in closed)
    wins=sum(float(p['realized_pnl'])>0 for p in closed)
    return {'closed':len(closed),'wins':wins,'losses':len(closed)-wins,
            'win_rate_pct':round(100*wins/len(closed),2) if closed else None,
            'realized_pnl':round(pnl,2),'note':'Illustrative simulation, not verified market fills.'}
