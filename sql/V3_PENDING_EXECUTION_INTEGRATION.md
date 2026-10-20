# V3 execution integration tracker

## Added in this ZIP
- Read-only authenticated Alpaca option latest-quote adapter (`core/alpaca_option_quotes.py`) with OCC validation, positive bid/ask, freshness and maximum spread checks.
- OPRA-only policy for automatic simulated execution; the free indicative feed is deliberately rejected for fill-quality purposes.
- Offline unit tests for quote parsing and request behavior. It does not submit orders.

## Not implemented / not verified
- Signal-to-specific OCC contract resolution and independently justified **option-premium** stops and targets. Underlying levels must never be substituted.
- Quote-provider hookup to Railway worker; require valid real-time OPRA entitlements and credentials, verified in deployment.
- Atomic PostgreSQL reservation / fill / balance update with concurrent workers, plus recovery and closing reconciliation.
- Broker-confirmed paper fills/cancels and order status polling; end-to-end integration tests against Alpaca paper sandbox.
- Secure authenticated dashboard kill switch, including canceling broker orders and handling open positions (the current stop only blocks new paper simulations).
- Authenticated tenant isolation; notifications and Robinhood watchlist integration (dependent on supported authorized integration).
- Live brokerage execution, which remains intentionally absent and must require a separate safety review.

## Activation rule
Keep `V3_PAPER_AUTOMATION_ENABLED=false` and `ALPACA_PAPER_EXECUTION_ENABLED=false` until the above safety prerequisites are complete and staging tests succeed. Run `sql/v3_execution_research.sql` only in a separately approved Supabase staging database.
