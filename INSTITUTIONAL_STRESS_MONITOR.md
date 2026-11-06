# Institutional selling pressure monitor

KST V3 adds a **read-only, fail-closed, intraday stress overlay** to scanner signal details.

- Inputs: fresh completed 5-minute SPY, QQQ, XLK bars (from the existing `core.market.history` provider).
- Flags: `HIGH_SELLING_PRESSURE`, `ELEVATED_SELLING_PRESSURE`, `NO_BROAD_STRESS_SIGNAL`, or `UNAVAILABLE`.
- These statuses reflect **ETF price movement only**, not prime-broker flow, margin calls, clearinghouse liquidations, dark pools or forced hedge-fund sales.
- `forced_liquidation_confirmed` stays false without a separate verified documentary source. Never present inferred selling as a verified liquidation.
- Every scanner record may include `institutional_stress` under its existing `details` JSON. No new database migration is necessary.
- Outside market hours, stale timestamps, missing data, or provider failure means `UNAVAILABLE` rather than "safe".
- The module **does not generate orders, change execution risk gates, or send push alerts**. Existing notification delivery and frontend presentation require separate wiring/testing.
- Before release, test the app, scanner and historical false-positive behavior; verify 5-minute bars and market data licensing. The Yahoo price feed is indicative, not a licensed execution feed.

Suggested future sources: Cboe options and volatility data, market breadth feeds, verified prime-broker reports and documented liquidation notices. Mark each as dated independently sourced evidence; never claim named forced liquidations from OHLCV.
