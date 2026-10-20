# V3: Six remaining items — updated development status

1. **Historical data lake** — Configurable read-only endpoint adapter now added. Endpoint URL, plan entitlement, and data retention must be verified; historical Data Shop downloads are a distinct product. No production warehouse is claimed.
2. **Earnings volatility** — Configurable read-only endpoint adapter added. No implied-volatility strategy or earnings forecast validated.
3. **Institutional 13F** — Configurable read-only adapter added. Filings are delayed, not live trading signals. No claim of live holdings.
4. **AI learning and performance backtesting** — Reproducible point-in-time analysis of verified paper trades, champion/challenger summaries, prevents automatic strategy promotion. No self-learning AI deployed; needs outcomes and walk-forward tests.
5. **Automated scanning and alerts** — Bounded one-shot, private summary collector with opt-in `UW_SCAN_ENABLED=true`, disabled by default. Schedule/delivery not deployed and no customer messaging implemented; needs Railway worker setup, rate/quota checks and webhook permissions.
6. **Public Unusual Whales features** — Explicitly NOT enabled. Vendor API prohibits redistribution under personal plans, including derivatives unless separately authorized. Must obtain written commercial redistribution permission before public display or published derivative market intelligence.

## Safe activation sequence
- Keep V2 unchanged. Test V3 in separate Railway staging service.
- Verify `UNUSUAL_WHALES_API_KEY` works in V3 service using `python check_uw_pending.py`.
- Confirm endpoints in vendor OpenAPI spec and plan; then set `UW_HISTORY_PATH`, `UW_EARNINGS_PATH`, and `UW_INSTITUTIONAL_13F_PATH` accordingly. Review code and API data shapes before treating returned data as reliable.
- Review licensing for storage and configure private Supabase table only if permitted.
- Run `pytest -q tests/test_uw_extended.py`; backtest with true dated records.
- Only then schedule bounded private scans, with secure notification delivery; do not activate public vendor-data endpoints.
- Broker real-money execution stays separate and disabled.

Docs: https://unusualwhales.com/public-api ; https://api.unusualwhales.com/docs
