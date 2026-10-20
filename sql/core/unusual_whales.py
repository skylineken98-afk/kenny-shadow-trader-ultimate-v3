"""Read-only Unusual Whales adapter. No public redistribution or broker orders."""
import os,re,requests
BASE='https://api.unusualwhales.com'
class UnusualWhalesError(RuntimeError):pass

def _ticker(t):
    s=str(t).strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',s):raise ValueError('Invalid ticker')
    return s

def _request(path,params=None,session=None):
    key=os.environ.get('UNUSUAL_WHALES_API_KEY','').strip()
    if not key:raise UnusualWhalesError('Missing UNUSUAL_WHALES_API_KEY in server secrets')
    if not path.startswith('/api/') or '..' in path or '://' in path:raise ValueError('Unsafe endpoint')
    try:
        resp=(session or requests).get(BASE+path,headers={'Authorization':'Bearer '+key,'Accept':'application/json'},params=params or {},timeout=20)
        if resp.status_code in (401,403):raise UnusualWhalesError('API access denied: check token and subscription')
        if resp.status_code==429:raise UnusualWhalesError('API rate limited')
        resp.raise_for_status();result=resp.json()
    except UnusualWhalesError:raise
    except (requests.RequestException,ValueError) as exc:raise UnusualWhalesError('HTTP or JSON request failure') from exc
    if not isinstance(result,dict) or 'data' not in result:raise UnusualWhalesError('Unexpected API response')
    return result

def flow_alerts(limit=25):
    n=int(limit)
    if not 1<=n<=200:raise ValueError('limit must be 1 through 200')
    return _request('/api/option-trades/flow-alerts',{'limit':n})
def stock_flow(ticker):return _request('/api/stock/'+_ticker(ticker)+'/flow-recent')
def greek_exposure(ticker):return _request('/api/stock/'+_ticker(ticker)+'/greek-exposure')
def darkpool(ticker):return _request('/api/darkpool/'+_ticker(ticker))
def congressional_trades():return _request('/api/congress/recent-trades')
def connection_check(session=None):
    try:
        r=_request('/api/option-trades/flow-alerts',{'limit':1},session=session)
        return {'connected':True,'records_returned':len(r['data']) if isinstance(r['data'],list) else None}
    except UnusualWhalesError as exc:return {'connected':False,'error':str(exc)}
