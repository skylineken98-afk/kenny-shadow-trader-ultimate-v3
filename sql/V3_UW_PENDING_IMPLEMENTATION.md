# V3 Unusual Whales pending-work package — private development

This ZIP extends `kenny-shadow-trader-v3-sec-verified-unusual-whales-dev.zip`,
which itself extends the saved SEC-verified V3 baseline. V2 remains untouched.

## Added now
- Private ticker-level concurrent-source *sequential* collector for flow, Greeks and dark-pool
- Fail-closed missing data/entitlement handling, normalized operational status (not market data)
- Optional Supabase private-storage adapter, explicitly disabled by default
- SQL for private, RLS-enabled UW research table (not executed)
- 4H/1H/5M alignment readiness indicator; vendor flow impact intentionally UNVALIDATED
- CLI connection/permissions check and mock unit tests

## Must still be verified or implemented
1. Run `python check_uw_pending.py` privately on **V3 Railway**, with your existing key.
2. Confirm actual endpoint paths and vendor response fields against current OpenAPI docs;
   validate returned 200/401/403/429 statuses and rate limits.
3. Confirm commercial licensing for public app and whether private historical storage is permitted.
   `UW_PRIVATE_STORAGE_ENABLED=true` is deliberately not set. Table SQL is not applied.
4. Add historical data-lake, earnings IV and 13F endpoint adapters AFTER schema validation.
   No speculative endpoint requests have been introduced for these feeds.
5. Develop tested as-of timestamps, feature normalization, backtests, and signal attribution
   before using data in ranking, trade execution or a published chart.
6. Add private scheduling and deduplication only after plan quota/retention rules are known.
7. Real money trading remains gated and inactive; no broker order calls added.

Published UW terms say personal API plans prohibit redistribution. **Do not serve raw or
vendor-derived proprietary information on a public site without license.**
Documentation: https://unusualwhales.com/public-api

Tests: `python -m pytest -q tests/test_uw_pending.py` (or run full suite).
