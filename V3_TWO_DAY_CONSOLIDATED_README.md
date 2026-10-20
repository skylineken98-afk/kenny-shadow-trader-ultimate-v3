# Kenny Shadow Trader V3 — Two-day consolidation (October 19–20, 2026)

This ZIP is a COMPLETE **development** project rooted at `kenny-shadow-trader-ultimate-v3-main/`; previous source, workers, tests, UI, SQL and documentation were retained. This is not a working unattended live trader.

## New in this consolidation

- `core/strategy_discovery.py`: 60+ named *strategy research specifications* across trend, momentum, pullback, reversal, mean-reversion, volatility, options, event, quantitative, crypto and FX themes. Six underlying bounded, runnable baseline strategy families generate many independently versioned candidate hypotheses. The other names are research specifications; **not falsely claimed as executable strategies**.
- Signal decisions from completed bars, hypothetical next-open execution, non-overlapping trades, configurable costs, chronological train/holdout comparison. Not a faithful options/futures/crypto execution simulator and **not suitable as sole live validation**.
- `core/robinhood_gateways.py`: Verified official MCP endpoint constant, explicit connection-authorization status, fail-closed live submission; separately signed *read-only* crypto API queries using optional PyNaCl, $100 allocation guard illustration. No real orders can be sent by either adapter.
- Tests verify safe behavior and absence of live order submission.

## Preserved earlier architecture
Scanner `core/market.py` and `confluence` compatibility remain unchanged, along with Supabase and Unusual Whales, SEC/FINRA/FRED work, AI learning journal, paper-agent runtime and related scripts. These remain at their prior degree of completion; not all are deployed or integrated.

## Current user database
Existing Supabase tables `ultimate_signals`, `paper_trades`, `paper_fills`, `ai_training_outcomes`, `ai_model_versions`, `v3_paper_accounts`, `v3_paper_orders`, `v3_paper_audit` were created separately by the user. This archive **does not assume** the Supabase migration / RPC is safe to run automatically. No schema changes are deployed by this ZIP.

## Robinhood prerequisites
- ChatGPT's connected MCP account authorization is NOT reusable in Railway.
- Railway-hosted external Trading MCP authorization must be confirmed with Robinhood support and implemented independently with supported OAuth handling.
- Crypto API credentials must be created in Robinhood crypto account settings; configure server-side only. Private key must be kept secret. Signed GET code is read-only. Verify API permissions, live responses and behavior before adding any execution method.
- Do not turn `ROBINHOOD_ENABLED`, `LIVE_TRADING_ENABLED` or any other live flags on based on this archive.
- Need broker-confirmed order IDs, filled quantities, partial fills, cancels, account/position reconciliation after outages, automatic exit logic, and independent loss/exposure halt **before** a live-capable build.

## Test
`python -m pytest -q tests/`

## References
https://robinhood.com/us/en/support/articles/agentic-trading-overview/
https://docs.robinhood.com/
