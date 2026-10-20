"""Additional research feeds. Explicit reviewed endpoint mapping required.

No default guesses: set UW_*_PATH from approved official API docs and confirm license.
No storing/publishing raw vendor data by default.
"""
import os
from .unusual_whales import _request, _ticker

FEEDS = {'history':'UW_HISTORY_PATH', 'earnings':'UW_EARNINGS_PATH',
         'institutional_13f':'UW_INSTITUTIONAL_13F_PATH'}

def get_feed(feed, ticker, *, approved=False):
    if feed not in FEEDS: raise ValueError('Unsupported feed')
    if not approved: return {'status':'DISABLED','reason':'Endpoint and entitlement unverified'}
    template=os.getenv(FEEDS[feed],'').strip()
    if not template: return {'status':'NOT_CONFIGURED','reason':f'Set {FEEDS[feed]} after endpoint verification'}
    if not template.startswith('/api/') or '..' in template or '://' in template:
        raise ValueError('Invalid API endpoint configuration')
    # Format only recognized safe ticker input. Other path placeholders are forbidden.
    if any(c in template for c in '{}') and template.count('{ticker}') != 1:
        raise ValueError('Only {ticker} placeholder permitted')
    safe=_ticker(ticker)
    path=template.replace('{ticker}',safe)
    return {'status':'AVAILABLE','feed':feed,'ticker':safe,'payload':_request(path),
            'PRIVATE_RESEARCH_ONLY':True}
