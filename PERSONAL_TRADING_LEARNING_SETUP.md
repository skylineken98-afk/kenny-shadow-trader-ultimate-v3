# KST personal trade intelligence — opt-in research foundation

This change adds read-only **normalized trade intake** and private storage for reconciled,
broker-verified, fully closed long equity and long option positions. It does not
authenticate to Robinhood or import any existing Robinhood records automatically.

## Workflow
1. Implement authorized **read-only** broker data retrieval in a separate private server-side
   integration; do not put tokens, account numbers, or raw brokerage exports into GitHub.
2. Reconcile all entry/exit partial fills, multipliers and fees into one fully closed
   position. Supply unique broker trade IDs and audited fill verification.
3. Optionally attach historical features that were actually available at entry;
   require `feature_available_at <= entry_time`. No post-exit chart hindsight as
   an entry-time feature.
4. Obtain explicit user opt-in and verified ownership from the backend authentication
   session. Do not trust a user ID supplied by the browser.
5. Apply `sql/kst_personal_trade_research.sql` after security review.
6. Invoke `persist_verified_trade(..., enabled=True)` only from a secured backend,
   with owner authorization already verified. It upserts idempotently.
7. Aggregate outcomes via `research_summary`, and validate any candidate
   strategy out-of-sample before changing signal rankings.

## Status and limits
- **Implemented in code:** validation, deduplicated stable pseudonymous IDs,
  point-in-time feature checks, net realized return, descriptive analytics,
  opt-in service-only persistence contract, security-focused SQL, unit tests.
- **Not connected:** Robinhood OAuth or brokerage ingestion; continuous sync;
  production migration; app dashboard; model retraining; alert delivery.
- No account secrets, raw brokerage identifiers, balances, or user trade data are
  committed. All data remains private and opt-in when deployed.
- Fee-inclusive P/L must be based on broker-confirmed notionals. Short options,
  multi-leg positions, assignments, FX conversions and partial open positions
  are excluded until instrument-aware reconciliation is implemented.
- Market regime classifications and sector pressure are proxies, not confirmed
  institutional flows or actual hedge-fund liquidations.
- No trades placed, no broker permissions changed, no risk gates modified.

Test: `python -m unittest tests.test_personal_trade_learning -v`.
