# Robinhood live execution: development checkpoint

**No unattended orders are enabled by this release.** Do not set `ROBINHOOD_ENABLED=true` or `LIVE_TRADING_ENABLED=true` based on this package. No API keys or account credentials are bundled.

## Current implementation

- `core/robinhood_gateways.py`: MCP URL validation, read-only signed Crypto API GET adapter, blocked submit methods.
- `core/robinhood_live_controls.py`: $100 allocation risk plan, max $60 per order, $60 cumulative open exposure, $5 realized daily-loss threshold; deterministic proposal IDs; research ledger; fail-closed recovery checks.
- `tests/test_robinhood_live_controls.py`: isolated tests with no live orders or API access.

These are **example initial conservative caps** pending user approval; they are not enforced at Robinhood and cannot authorize an order.

## Missing before actual Railway execution

1. Confirm with Robinhood that this independently deployed Railway MCP client is supported and complete the appropriate OAuth permissions without copying the ChatGPT session token.
2. Build and test the authenticated Streamable HTTP MCP client with token lifecycle and permission scoping; verify account access for the separate agent (it may not be the same account).
3. For Crypto Trading API, enroll through Robinhood and configure independent Ed25519 credentials and supported trading permissions; verify signed GETs and order eligibility.
4. Add separately verified broker adapters for preview/submit/cancel and authoritative order, fills and position histories. Verify execution responses on a supervised small test only after the user explicitly approves.
5. Replace local SQLite development ledger with transactional Supabase tables with unique client IDs, atomic reservations, and broker-order reconciliation; no duplicate submission after timeouts.
6. Implement exit-order lifecycle, market-hours eligibility, stale-quote rejection, unsupported contract restrictions, position and buying-power reconciliation, broker-side protection where available, a persistent kill switch and crash recovery.
7. Demonstrate end-to-end supervised validation before allowing a bounded unattended agent. Model-generated strategies must not alter risk caps or bypass security gates.

The research scanner is separate from broker permission. Passing unit tests does not show that orders can be placed or closed.
