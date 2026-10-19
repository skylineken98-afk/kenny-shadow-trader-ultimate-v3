from concurrent.futures import ThreadPoolExecutor,as_completed
from market_engine import analyze
from config import DEFAULT_TICKERS

def scan(tickers=None,workers=3):
    results=[];errors={}
    with ThreadPoolExecutor(max_workers=max(1,min(workers,4))) as pool:
        fs={pool.submit(analyze,t):t for t in (tickers or DEFAULT_TICKERS)}
        for f in as_completed(fs):
            try:results.append(f.result())
            except Exception as ex:errors[fs[f]]=str(ex)
    results.sort(key=lambda s:(not s['valid'],s['ticker']))
    return results,errors
