"""Exchange-listing discovery plus bounded/liquidity pre-screen. Not a complete real-time whole market scan."""
from io import StringIO
import pandas as pd
import requests

FALLBACK = ('SPY QQQ IWM DIA XLK XLF XLE SMH SOXX TLT GLD SLV '
            'AAPL MSFT NVDA TSLA AMZN GOOGL META AMD AVGO MU INTC NFLX COIN PLTR '
            'HOOD SOFI RIVN NIO MARA RIOT JPM BAC WFC GS C CCL AAL UAL DAL '
            'F GM SNAP PINS LYFT UBER SHOP SQ PYPL SHOP DIS V XOM CVX PFE '
            'LLY UNH COST WMT TGT BA CAT DE IBM ORCL CRM ADP NET CRWD TSM').split()

LISTINGS = (
 ('https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt','Symbol'),
 ('https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt','ACT Symbol'),
)

def listed_symbols(limit=3000):
    found=set(FALLBACK); notices=[]
    for url,col in LISTINGS:
        try:
            r=requests.get(url,timeout=15);r.raise_for_status()
            df=pd.read_csv(StringIO(r.text),sep='|',dtype=str)
            df=df[df['Test Issue'].fillna('N').eq('N')]
            for x in df[col].dropna():
                if x.isalpha() and 1<=len(x)<=5:found.add(str(x).upper())
        except Exception as ex:notices.append(f'Listing unavailable: {type(ex).__name__}')
    # deterministic rotating sample for fairer discovery; not claiming exhaustive coverage
    priority=list(dict.fromkeys(FALLBACK))
    others=sorted(found.difference(priority))
    return (priority+others)[:limit],notices

def shortlist(tickers, sample_size=160, shortlist_size=18, offset=0, downloader=None):
    """Batch daily-bar liquidity/movement screen before costly multi-frame/options queries."""
    import yfinance as yf
    downloader=downloader or yf.download
    unique=list(dict.fromkeys(tickers))
    if not unique:return [],['Universe is empty']
    size=min(max(1,int(sample_size)),400)
    pool=(unique[offset%len(unique):]+unique[:offset%len(unique)])[:size]
    scored=[]; notices=[]
    for start in range(0,len(pool),40):
        batch=pool[start:start+40]
        try:
            raw=downloader(batch,period='10d',interval='1d',progress=False,threads=True,auto_adjust=True,group_by='ticker')
            for sym in batch:
                try:
                    d=raw[sym] if isinstance(raw.columns,pd.MultiIndex) else raw
                    d=d.dropna(subset=['Close','Volume'])
                    if len(d)<3:continue
                    p=float(d['Close'].iloc[-1]);v=float(d['Volume'].tail(5).mean())
                    if p<2 or p*v<2_000_000:continue
                    ret=abs(float(d['Close'].iloc[-1]/d['Close'].iloc[-3]-1))
                    scored.append((sym,p*v*(1+min(ret,0.3)*12)))
                except (KeyError,TypeError,ValueError,ZeroDivisionError):continue
        except Exception as exc:notices.append(f'Daily screening batch unavailable: {type(exc).__name__}')
    scored.sort(key=lambda x:x[1],reverse=True)
    return [s for s,_ in scored[:shortlist_size]],notices
