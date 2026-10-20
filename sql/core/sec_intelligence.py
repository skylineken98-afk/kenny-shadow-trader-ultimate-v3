"""SEC EDGAR read-only research adapter. No API key; identifies client via SEC_USER_AGENT.

Public filings are delayed disclosures, NOT real-time institutional money flow.
"""
import re
import time
from functools import lru_cache
import requests
from core.settings import get

BASE = 'https://data.sec.gov'
TICKERS = 'https://www.sec.gov/files/company_tickers.json'
_last_request = 0.0


def _headers():
    ua = get('SEC_USER_AGENT')
    if not ua or '@' not in ua or len(ua) < 12:
        raise ValueError('Set SEC_USER_AGENT to an identifying app name and contact email in server secrets')
    return {'User-Agent': ua, 'Accept-Encoding': 'gzip, deflate', 'Accept': 'application/json'}


def _get(url, session=None):
    global _last_request
    if not url.startswith((BASE + '/', 'https://www.sec.gov/files/')):
        raise ValueError('SEC URL not allowed')
    wait = max(0.0, 0.25 - (time.monotonic() - _last_request))
    if wait: time.sleep(wait)
    _last_request = time.monotonic()
    r = (session or requests).get(url, headers=_headers(), timeout=25)
    r.raise_for_status()
    return r.json()


@lru_cache(maxsize=1)
def ticker_index():
    result = _get(TICKERS)
    return {v['ticker'].upper(): str(v['cik_str']).zfill(10) for v in result.values()}


def cik_for_ticker(symbol):
    symbol = str(symbol).strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,15}', symbol):
        raise ValueError('Invalid ticker')
    return ticker_index().get(symbol)


def company_facts(symbol):
    cik = cik_for_ticker(symbol)
    if not cik: return {'status': 'not_found', 'ticker': symbol}
    return {'status': 'ok', 'ticker': symbol.upper(), 'cik': cik,
            'data': _get(f'{BASE}/api/xbrl/companyfacts/CIK{cik}.json'),
            'source': 'SEC EDGAR companyfacts', 'classification': 'delayed_filing_data'}


def recent_filings(symbol, forms=('10-K','10-Q','8-K','4','13F-HR')):
    cik = cik_for_ticker(symbol)
    if not cik: return {'status': 'not_found', 'ticker': symbol}
    data = _get(f'{BASE}/submissions/CIK{cik}.json')
    rec = data.get('filings',{}).get('recent',{})
    keys = ('form','filingDate','accessionNumber','primaryDocument','reportDate')
    rows = [dict(zip(keys, vals)) for vals in zip(*(rec.get(k,[]) for k in keys))]
    return {'status': 'ok', 'ticker': symbol.upper(), 'cik': cik,
            'filings': [r for r in rows if r['form'] in forms][:100],
            'note': 'Recent filing list only; may omit older or institutional-manager holdings'}
