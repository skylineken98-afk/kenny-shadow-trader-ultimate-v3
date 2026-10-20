"""Paper-only Alpaca execution boundary. Not imported by signal scanners by default.

No live trading URL or live-mode switch is provided. Fail closed on missing
credentials, broker errors, invalid contracts, or disabled execution.
"""
import hashlib
import os
import re
from decimal import Decimal, InvalidOperation
import requests

PAPER_URL = 'https://paper-api.alpaca.markets/v2'
OCC = re.compile(r'^[A-Z]{1,6}\d{6}[CP]\d{8}$')
STOCK = re.compile(r'^[A-Z][A-Z0-9.]{0,9}$')

class ExecutionError(ValueError):
    pass


def _money(value):
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d <= 0:
            raise ExecutionError('price must be positive and finite')
        return d
    except (InvalidOperation, TypeError):
        raise ExecutionError('invalid price')


def build_paper_order(symbol, side, quantity, limit_price, *, asset='option', signal_id=None, max_order_cost=250):
    """Validate a long-only buy-to-open limit order before any HTTP calls.

    Options use the standard 100-share multiplier; unusual deliverables are
    rejected upstream by a separate contract check, not assumed here.
    """
    if asset not in ('option', 'stock'):
        raise ExecutionError('Only US stocks and standard options are supported')
    symbol = str(symbol).upper().strip()
    if not (OCC.fullmatch(symbol) if asset == 'option' else STOCK.fullmatch(symbol)):
        raise ExecutionError('Invalid instrument symbol')
    if side != 'buy':
        raise ExecutionError('Only long buy-to-open orders are enabled')
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1 or quantity > 100:
        raise ExecutionError('Invalid whole-unit order quantity')
    price = _money(limit_price)
    cap = _money(max_order_cost)
    notional = price * quantity * (100 if asset == 'option' else 1)
    if notional > cap:
        raise ExecutionError('Proposed order exceeds paper order cost limit')
    if not signal_id or not str(signal_id).strip():
        raise ExecutionError('Source signal ID is required for audit and deduplication')
    unique = hashlib.sha256(f'{signal_id}:{asset}:{symbol}:buy'.encode()).hexdigest()[:30]
    return {'symbol': symbol, 'qty': str(quantity), 'side': 'buy', 'type': 'limit',
            'limit_price': str(price), 'time_in_force': 'day',
            'client_order_id': f'kstp-{unique}'}


class AlpacaPaperBroker:
    def __init__(self, key=None, secret=None, *, enabled=None, session=None):
        self.key = key if key is not None else os.getenv('ALPACA_PAPER_API_KEY')
        self.secret = secret if secret is not None else os.getenv('ALPACA_PAPER_SECRET_KEY')
        self.enabled = (os.getenv('ALPACA_PAPER_EXECUTION_ENABLED', 'false').lower() == 'true') if enabled is None else bool(enabled)
        self.session = session or requests.Session()

    def _request(self, method, path, **kwargs):
        if not self.enabled:
            raise ExecutionError('Alpaca paper execution is disabled')
        if not self.key or not self.secret:
            raise ExecutionError('Dedicated Alpaca PAPER credentials are missing')
        if not path.startswith('/') or '://' in path:
            raise ExecutionError('Invalid broker API path')
        try:
            response = self.session.request(method, PAPER_URL + path,
                headers={'APCA-API-KEY-ID': self.key, 'APCA-API-SECRET-KEY': self.secret},
                timeout=15, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ExecutionError(f'Paper broker API failure: {type(exc).__name__}') from exc

    def account(self):
        return self._request('GET', '/account')

    def order(self, order_id):
        if not re.fullmatch(r'[0-9a-fA-F-]{36}', str(order_id)):
            raise ExecutionError('Invalid order ID')
        return self._request('GET', f'/orders/{order_id}')

    def positions(self):
        return self._request('GET', '/positions')

    def orders(self):
        return self._request('GET', '/orders', params={'status':'all','limit':100})

    def submit(self, proposal, *, approved=False):
        if not approved:
            raise ExecutionError('Explicit paper-order approval required')
        if not isinstance(proposal, dict) or not set(('symbol','qty','side','type','limit_price','time_in_force','client_order_id')).issubset(proposal):
            raise ExecutionError('Invalid proposal')
        # Re-validate the payload even if caller passes a crafted dict.
        asset = 'option' if OCC.fullmatch(str(proposal['symbol'])) else 'stock'
        checked = build_paper_order(proposal['symbol'], proposal['side'], int(proposal['qty']) if str(proposal['qty']).isdigit() else -1,
            proposal['limit_price'], asset=asset, signal_id=proposal['client_order_id'],
            max_order_cost=os.getenv('PAPER_MAX_ORDER_COST', '250'))
        if proposal.get('type') != 'limit' or proposal.get('time_in_force') != 'day':
            raise ExecutionError('Only day limit orders supported')
        # Keep the deterministic client ID constructed by the research signal.
        client_id = str(proposal['client_order_id'])
        if not re.fullmatch(r'kstp-[0-9a-f]{30}', client_id):
            raise ExecutionError('Invalid deduplication key')
        checked['client_order_id'] = client_id
        account = self.account()
        if account.get('status') != 'ACTIVE' or account.get('trading_blocked'):
            raise ExecutionError('Paper account not active or is blocked')
        return self._request('POST', '/orders', json=checked)
