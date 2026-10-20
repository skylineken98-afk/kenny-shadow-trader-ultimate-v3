# Kenny Shadow Trader V3 – consolidated execution development build

## Added this round
- `core/paper_runtime.py`: local SQLite-backed, transaction-serialized **research simulation** for five independent agents, opt-in paper arming, emergency stop, idempotent entries, OCC call/put direction checking, fresh quote validation, cash reservation, premium-based target/stop exits, realized P&L and immutable event rows.
- `tests/test_paper_runtime.py`: replay/restart, deduplication, stop, call/put and exit tests.
- Prior SEC, FINRA, FRED/Alpaca connector code, opportunity ranking, charts and research scripts remain in the package.

## What has NOT been activated
- The new ledger is a *local development simulator*. It is not wired to Railway's startup command or Supabase. Do NOT put a mutable SQLite ledger on an ephemeral Railway disk or run concurrent worker replicas against it.
- The existing `workers/paper_execution_worker.py` remains disabled by default and still needs a secured verified-contract quote callback and production Supabase atomic transactions.
- No authenticated multi-user app, commercial FINRA/OPRA feed entitlements, Robinhood API watchlist changes, production Alpaca broker submit/reconcile loop, or live-money execution is enabled.
- No external API credentials are bundled. Research fills are assumed at ask and exits at bid; they are not exchange/broker confirmations. Open positions are not marked to market, expiration/assignment and fees are not yet modeled accurately. The local simulator should only be used for controlled replay/testing.

## Before deploying from laptop
1. Keep V2 as-is; create an independent private V3 repository/deployment and dedicated Supabase project.
2. Review SQL migrations in `sql/`, connect a test-only Supabase instance and confirm row policies and server secrets.
3. Verify Alpaca paper account permissions and OPRA option quote entitlements with a real (read-only) request; never expose secrets in GitHub/browser.
4. Add transactional Supabase account/order procedures, worker leasing, option expiration/settlement and broker reconciliation, then prove concurrency/failure recovery.
5. Add authenticated control console (not shared beta password), alerts/outbox, market sessions, budget gates and separate quote monitoring from order execution.
6. Run historical out-of-sample replay and end-to-end paper broker testing, compare observed vs simulated fills, confirm day loss and kill behavior.
7. Enable paper workers only after those prerequisites are met. Live order execution is not implemented or authorized in this package.

## Offline demonstration (in an isolated virtual environment)
Run `PYTHONPATH=. python -m pytest -q tests` from the package root.
For the new local module, import `PaperRuntime` and create a database at a durable local file path, arm explicitly with `paper_only_ack=True`, supply authentic recent OCC option quote dictionaries (`bp`, `ap`, `t`) and close it after testing. Keep research records separate from actual brokerage fills.
