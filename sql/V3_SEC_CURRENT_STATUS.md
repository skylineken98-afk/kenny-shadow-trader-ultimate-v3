# V3 SEC EDGAR current status

Existing SEC adapter `core/sec_intelligence.py` was retained **without replacement** from the newest master development archive. The earlier SEC/FINRA development ZIP contains byte-identical SEC and FINRA adapters and regulatory tests; no older files were copied over the newer master.

## Available in code
- SEC ticker -> CIK lookup, Company Facts JSON, recent filings JSON.
- Read-only access with required identifying `SEC_USER_AGENT` and conservative per-process request pacing.
- Standalone connectivity check: `python check_sec_connection.py` (requires real contact email and outbound internet).
- Existing regulatory unit tests: `python -m pytest tests/test_regulatory_sources.py -q` (six passed in archive preparation environment).

## Not verified or not integrated
- Live SEC network connectivity has **not** been tested in this offline archive assembly environment.
- SEC filing data is **not yet** scheduled for persistence to Supabase or scored by the market-wide AI ranking pipeline.
- SEC data is not real-time insider or institutional order flow. Do not use it as an execution trigger by itself.
- FINRA credentials and commercial licensing remain pending.

## Later, on V3 Railway (not the V2 service)
1. Set `SEC_USER_AGENT` to an application name plus a real monitored contact email.
2. Verify installation with `python -m pytest tests/test_regulatory_sources.py -q`.
3. Run `python check_sec_connection.py` to confirm SEC requests succeed.
4. Only then implement dated data storage, deduplication, retry/backoff, scheduled ingestion, and research-only scoring. Test all of this in V3 before deployment or live execution.

No brokerage live-order enablement is included or authorized by this check.
