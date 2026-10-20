"""Read-only Alpaca option quotes for research and paper simulations.

Indicative market data is NOT an executable broker quote. This adapter never
submits orders and rejects stale/wide/invalid quotes. It deliberately does not
invent option-premium stops or targets from underlying-stock levels.
"""
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import requests

ENDPOINT = 'https://data.alpaca.markets/v1beta1/options/quotes/latest'
OCC = re.compile(r'^[A-Z]{1,6}\d{6}[CP]\d{8}$')

class QuoteError(ValueError):
    pass


def validate_quote(symbol, item, *, now=None, max_age_seconds=60,
                   max_spread_fraction=Decimal('.20')):
    if not OCC.fullmatch(str(symbol)):
        raise QuoteError('Invalid OCC option symbol')
    if not isinstance(item, dict):
        raise QuoteError('Quote missing')
    try:
        bid, ask = Decimal(str(item['bp'])), Decimal(str(item['ap']))
        stamp = datetime.fromisoformat(str(item['t']).replace('Z', '+00:00'))
        current = now or datetime.now(timezone.utc)
        age = (current - stamp).total_seconds()
        if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask <= bid:
            raise QuoteError('Invalid bid/ask')
        if stamp.tzinfo is None or not 0 <= age <= max_age_seconds:
            raise QuoteError('Stale or future-dated quote')
        if (ask - bid) / ask > max_spread_fraction:
            raise QuoteError('Spread too wide')
    except QuoteError:
        raise
    except (KeyError, ValueError, InvalidOperation, TypeError, OverflowError) as exc:
        raise QuoteError('Missing or invalid quote fields') from exc
    return {'symbol': symbol, 'bid': str(bid), 'ask': str(ask),
            'quote_timestamp': stamp.isoformat(), 'spread_fraction': str((ask-bid)/ask)}


class AlpacaOptionQuoteReader:
    def __init__(self, *, key=None, secret=None, feed='opra', session=None):
        self.key = key if key is not None else os.getenv('ALPACA_DATA_API_KEY')
        self.secret = secret if secret is not None else os.getenv('ALPACA_DATA_SECRET_KEY')
        if feed != 'opra':
            raise QuoteError('Only real-time OPRA quotes allowed for execution simulations')
        self.session = session or requests.Session()

    def latest(self, symbols):
        symbols = list(dict.fromkeys(symbols))
        if not 1 <= len(symbols) <= 100 or any(not OCC.fullmatch(str(s)) for s in symbols):
            raise QuoteError('Expected 1-100 valid OCC option symbols')
        if not self.key or not self.secret:
            raise QuoteError('Alpaca market-data credentials missing')
        try:
            response = self.session.get(ENDPOINT,
                params={'symbols': ','.join(symbols), 'feed': 'opra'},
                headers={'APCA-API-KEY-ID': self.key, 'APCA-API-SECRET-KEY': self.secret},
                timeout=15)
            response.raise_for_status()
            rows = response.json().get('quotes', {})
            if not isinstance(rows, dict):
                raise QuoteError('Unexpected quote response')
            return {symbol: validate_quote(symbol, rows[symbol]) for symbol in symbols if symbol in rows}
        except requests.RequestException as exc:
            raise QuoteError('Alpaca option quote request failed or OPRA access unavailable') from exc
