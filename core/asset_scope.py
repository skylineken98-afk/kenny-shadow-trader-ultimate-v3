"""Active Shadow Trader V3 asset scope: equity options, stocks, spot crypto.

Only known in-scope Yahoo-style symbols are admitted to the default scanner.
An allowlist is deliberately conservative: arbitrary ticker symbols cannot be
reliably classified without an instrument metadata provider.
"""

import re

CRYPTO_QUOTES = ('-USD', '-USDT')
DISALLOWED_SUFFIXES = ('=F', '=X')


def in_scope_symbol(symbol: str) -> bool:
    if not isinstance(symbol, str):
        return False
    symbol = symbol.strip().upper()
    if not symbol or symbol.startswith('^') or symbol.endswith(DISALLOWED_SUFFIXES):
        return False
    if symbol.endswith(CRYPTO_QUOTES):
        return bool(re.fullmatch(r'[A-Z0-9]{2,20}-(?:USD|USDT)', symbol))
    # Stocks and ETFs use listed-style letters and limited punctuation.
    # Option contracts are discovered separately from eligible stock/ETF chains.
    return bool(re.fullmatch(r'[A-Z]{1,6}(?:[.-][A-Z]{1,2})?', symbol))
