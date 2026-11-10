"""Ensure affordable-option underlyings get reviewed without fabricating contracts.

These tickers are candidates for scanning, not guaranteed inexpensive options.
Actual contract ask, quote timestamp, setup and liquidity still determine eligibility.
"""
PRIORITY_UNDERLYINGS = (
    "IWM", "SPY", "QQQ", "DIA", "XLF", "SLV", "GDX",
    "SOFI", "HOOD", "BAC", "F", "CCL", "AAL", "SNAP",
    "RIVN", "PFE", "NIO", "PLTR", "RIOT",
)

def add_priority_underlyings(shortlisted, priority=PRIORITY_UNDERLYINGS):
    """Union (not replacement): retain movement prescreen and always check core names."""
    seen = set()
    result = []
    for sym in (*priority, *shortlisted):
        sym = str(sym).strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            result.append(sym)
    return result
