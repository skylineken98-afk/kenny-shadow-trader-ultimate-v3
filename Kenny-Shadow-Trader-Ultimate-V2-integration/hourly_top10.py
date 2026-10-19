import json
from datetime import datetime,timezone
from scanners import scan
from storage import record_signal
from config import DEFAULT_TICKERS
if __name__=='__main__':
    results,errors=scan(DEFAULT_TICKERS)
    for s in results: record_signal(s)
    print(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'type':'underlying watchlist NOT verified options contracts','top10':results[:10],'errors':errors},indent=2))
