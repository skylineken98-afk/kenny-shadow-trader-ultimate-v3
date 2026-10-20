# Execution architecture (development)

This release includes **only a paper Alpaca order adapter**, not a running
execution worker or automated order placement. The API base URL is permanently
set to Alpaca's paper environment. Signal workers do not invoke the adapter.

## Safe activation prerequisites

1. Create separate Alpaca **paper trading** API credentials and store in
   Railway secrets as `ALPACA_PAPER_API_KEY`, `ALPACA_PAPER_SECRET_KEY`.
2. Leave `ALPACA_PAPER_EXECUTION_ENABLED=false` until dedicated paper order
   accounting, approval, verification, and reconciliation are tested.
3. When testing later, confirm the account reports active and use only
   authenticated, user-approved signals; enforce daily loss and portfolio
   limits using current broker balances **before** and after any order.
4. Resolve each OCC option contract through Alpaca contract APIs. Check
   `tradable`, multiplier/deliverable, expiration, spread, quote age, market
   hours, options permissions, buying power and possible exercise/assignment.
5. Record proposal, client_order_id, submitted order, broker response, fill
   events, cancels, rejects, positions, and exits in Supabase. Confirm a
   successful POST does not mean a fill. Build restart-safe reconciliation
   before scheduling any automatic submission.
6. Add dashboard kill switch, risk policy enforcement, manual override,
   emergency cancellation, audit log, circuit breakers and alerting.
7. Paper-test options with realistic fills, slippage, costs, expiry and
   exercise. Separately review and authorize **live** execution in a future
   release; this package contains no live brokerage endpoint.

Signals must include the precise OCC option contract. For a bearish thesis,
this stage should **buy a put**, not short the underlying or sell uncovered
options. Quotes and pricing data are not the same as execution privileges.

## V3 offline lifecycle addition (not broker-automated)

`core/paper_lifecycle.py` provides a pure simulated long-stock / long-call / long-put
entry/exit model with independent agent risk fractions, kill flags, daily loss and
aggregate exposure checks, deterministic OHLC stop-first assumptions and P&L.
No background worker automatically opens or closes these trades yet.

`sql/v3_execution_research.sql` adds separate agent accounts, deduplicated paper
orders and audit tables. Accounts default to killed=true. Do not run this against
production without reviewing migrations and backing up existing Supabase data.

Before automatic execution: implement transaction-safe reservations, real quote
feeds for *specific* OCC contracts, idempotent event processing, complete
reconciliation, nonblocking alerts, status/control UI and broker paper-account
trade testing. For actual broker accounts, one Alpaca paper account is not five
independent cash balances: they require virtual account accounting or separate
broker accounts. No Robinhood API integration is included.
