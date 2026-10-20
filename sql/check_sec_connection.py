"""Manual SEC EDGAR smoke test. Read-only; never places trades.

Usage: SEC_USER_AGENT='KennyShadowTrader contact@your-real-domain.com' python check_sec_connection.py
Replace the example email with your own. Requires network access to SEC hosts.
"""
import json
import sys
from core.sec_intelligence import cik_for_ticker, company_facts, recent_filings


def main():
    try:
        cik = cik_for_ticker('AAPL')
        if not cik:
            raise RuntimeError('SEC ticker directory did not resolve AAPL')
        facts = company_facts('AAPL')
        filings = recent_filings('AAPL')
        if facts.get('status') != 'ok' or filings.get('status') != 'ok':
            raise RuntimeError('SEC returned an unexpected status')
        print(json.dumps({
            'sec_reachable': True,
            'ticker': 'AAPL',
            'cik': cik,
            'company_facts_available': bool(facts.get('data', {}).get('facts')),
            'recent_filings_returned': len(filings.get('filings', [])),
            'important': 'Connectivity only; V3 database ingestion and scheduled monitoring not validated',
        }, indent=2))
        return 0
    except Exception as exc:
        print(f'SEC connectivity check failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
