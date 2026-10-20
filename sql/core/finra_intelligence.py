"""Read-only FINRA API adapter. FINRA credentials and licensing required.

FINRA short sale volume != net short positions and OTC/ATS prints do not
identify which side initiated a trade. Do not infer net institutional inflow.
"""
import re
import requests
from core.settings import get

TOKEN_URL = 'https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials'
BASE = 'https://api.finra.org/data/group/otcMarket/name/'
DATASETS = {
    'short_interest': 'consolidatedShortInterest',
    'short_sale_volume': 'regShoDaily',
    'ats_blocks': 'blocksSummary',
    'otc_blocks': 'otcBlocksSummary',
}


def _credentials():
    client_id = get('FINRA_CLIENT_ID')
    secret = get('FINRA_CLIENT_SECRET')
    if not client_id or not secret:
        raise ValueError('FINRA credentials missing: configure FINRA_CLIENT_ID and FINRA_CLIENT_SECRET')
    return client_id, secret


def access_token(session=None):
    r = (session or requests).post(TOKEN_URL, auth=_credentials(), timeout=25)
    r.raise_for_status()
    payload = r.json()
    if not payload.get('access_token'):
        raise ValueError('FINRA token response missing access_token')
    return payload['access_token']


def query(dataset, *, limit=50, offset=0, token=None, session=None):
    if dataset not in DATASETS:
        raise ValueError('Unsupported FINRA dataset')
    if not isinstance(limit,int) or not 1 <= limit <= 500:
        raise ValueError('limit must be 1..500')
    if not isinstance(offset,int) or offset < 0:
        raise ValueError('Invalid offset')
    token = token or access_token(session)
    response = (session or requests).get(
        BASE + DATASETS[dataset],
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        params={'limit': limit, 'offset': offset}, timeout=30)
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list):
        raise ValueError('Unexpected FINRA dataset response')
    return {'dataset':dataset,'rows':records,'offset':offset,
            'disclosure':'Delayed aggregated regulatory data, not real-time net institutional flow',
            'licensing':'Check FINRA commercial access and redistribution permissions'}
