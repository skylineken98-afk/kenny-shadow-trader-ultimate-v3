# V3 Paper Database — Staged Transactional Bridge

This upgrade retains all previous V3 code, including the standalone SQLite research runtime.
Added `sql/v3_atomic_paper_entry.sql` and `core/v3_paper_bridge.py` plus tests.

**NOT DEPLOYMENT READY.** The migration is unexecuted; the RPC adapter is not wired
into `paper_automation.py` or a scheduled worker. Both environment toggles
`V3_PAPER_AUTOMATION_ENABLED` and `V3_ATOMIC_PAPER_BRIDGE_ENABLED` must remain false.

The RPC reserves simulated account exposure and records assumed option ask entry,
order, trade, fill and audit atomically. It uses a DB row lock, unique orders and
source-signal checks. This is a *research-only development draft* requiring validation
against the actual Supabase schema, role privileges and timestamp behavior.

Missing before activation: atomic exit/settlement, quote entitlement/freshness checks
in the trusted caller, identity & risk verification, partial fills/reconciliation,
account daily reset, real testing against Supabase, model outcome validation,
worker scheduling/recovery and robust permission/least-privilege review.

Never call the RPC from browser/anon. Never provide service-role credentials to UI.
No real-money/broker execution is added.
