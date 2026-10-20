# V3 Unusual Whales research integration (development only)

This update builds upon the latest saved **V3 SEC-verified ZIP**, preserving its existing files. V2 is untouched.

Railway V3 secret: `UNUSUAL_WHALES_API_KEY` (never store or publish actual key in ZIP).

Read-only functions in `core/unusual_whales.py`: `flow_alerts`, `stock_flow`, `greek_exposure`, `darkpool`, `congressional_trades`. These use the documented Bearer auth endpoints and handle missing credentials, 401/403, 429, transport errors, and invalid tickers. Read-only flow is **not** a trade execution signal.

Test locally: `python -m pytest -q tests/test_unusual_whales.py`

**After deploying V3 code to its private Railway service**, run `python check_unusual_whales_connection.py` in that service to verify actual credentials and subscription entitlements. The key being saved alone does not activate this adapter in deployed code.

Not yet integrated: data-lake historical collection, 13F analytics, earnings-volatility strategy, WebSockets, automated Supabase ingestion, signal ranking, chart/UI display. These still need coding and tests. No live orders. No automatic posting of licensed data to public users.

**Licensing:** Personal API subscriptions do not authorize public redistribution. Secure commercial licensing before exposing raw or derived Unusual Whales data in the public app.

Official endpoint references: https://unusualwhales.com/developers and https://unusualwhales.com/public-api/examples/get-all-flow-alerts
