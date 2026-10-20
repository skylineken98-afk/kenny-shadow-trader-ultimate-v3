# V3 nine-area integration checkpoint (development-only)

This archive **extends**, rather than replaces, previous V3 code. V2 integration backup remains included but is **not** the V3 deployment root.

## New components
- `core/v3_readiness.py`: 13 fail-closed checks across the nine areas and UW subfeeds; no actual production health asserted
- `core/v3_signal_audit.py`: schema-checked private audit events, local JSONL dev append (not cloud durable)
- `core/v3_notifications.py`: explicit opt-in Telegram send and error handling
- `core/v3_release_gates.py`: gate checks for paper scanning, broker execution, model promotion, memberships and public licensing
- `core/v3_model_validation.py`: basic chronological research split, evaluations; no automated model promotion
- `core/v3_membership.py`: entitlement transition state helper; **not** checkout, webhook verification or payment processing
- `tests/test_v3_nine_upgrade.py`: tests for safe defaults and gating

## Existing modules retained
UW read-only API, optional historical/earnings/13F adapters, market-wide scanner,
chart utilities, research backtest, paper agents, alerts, execution foundation, Supabase SQL.

## Must still be finished and independently verified
1. **UW** token entitlements, documented historical/earnings/13F paths, retention terms, licensed use.
2. **Learning** real verified fills and timestamped features; out-of-sample evaluation; supervised model lifecycle, no guaranteed returns.
3. **Market scanning** actual full-market coverage and hourly reliability on Railway, quotas and stale data checks.
4. **Charts** data feed/candle fidelity, support-resistance validation and chart UI tested on mobile.
5. **Telegram** chat destination, message delivery and retry/idempotency policy.
6. **Agents** isolated funded-paper ledgers, full trade lifecycle, slippage/fees, reconciled balance and recovery tests.
7. **Broker** broker capability and authorization, dry-run/paper checks, order-state reconciliation and hard stop; **LIVE TRADING NOT ENABLED**.
8. **Memberships** hosted billing provider, webhook signature verification, auth, provisioning, refund/cancellation handling.
9. **Public** commercial redistribution license, security, monitoring, incident response and rollback.

## Deployment caution
Never simply overwrite a running V2 Railway deployment. Make a backup/branch, verify Railway service source/start command, and run V3 tests before switching. `UNUSUAL_WHALES_API_KEY` belongs in Railway service variables, not in this ZIP.
