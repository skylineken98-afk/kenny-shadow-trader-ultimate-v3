# KST Unusual Options Flow Detector — offline approval candidate

**Status:** development only. No provider subscription, production deployment, real notifications,
database migrations, live orders, or modification of kill switches.

## Config
- Minimum single-print gross premium: **$250,000** (option premium × standard 100 multiplier × contracts).
- Both CALL and PUT. Intended scope: entire US listed options market **only when a licensed
  provider supplies a complete tape**. Current code processes the records received; coverage
  is NOT implied by the presence of a symbol.
- Telegram and website alert *intents* enabled in previews; delivery is hard-disabled.
- Store event time (UTC), OCC contract, strike, expiry, contracts, price, bid/ask, source and
  event ID. Deduplicate by provider + event ID.
- Multi-leg heuristics: same symbol, right, expiry and size; opposing bid/ask-side execution;
  within 1 second; different strikes. Label **POSSIBLE** spread, not confirmed.
- Option prints do not reveal whether trades were opening or closing, the identity of the
  buyer, or institutional sentiment. A print at the ask is not proof of a bullish buy.
- Response: verified underlying prices at +5/+15/+30/+60 minutes from event;
  no future lookahead, no interpolation, missing horizons stay null.
- Reject malformed, stale, duplicated and below-threshold prints. Suppress directional
  assertions on indicative/delayed or missing bid/ask. Provider condition codes must be
  normalized by the future adapter. Complex trade corrections/cancels and nonstandard
  multipliers require additional handling **before** production.
- Stored provider data must be protected by licensed-use access controls and retention
  requirements. No raw or derived data to beta users without permission.

## Existing infrastructure and integration boundary
KST's `kst_options/provider.py` currently supplies contract-chain quotes and delayed/indicative
volume bars; `kst_options/strike_volume.py` correctly cautions those are NOT trade prints.
The new pure module `kst_options/unusual_flow.py` takes provider-neutral records so
offline fixtures can be tested without market-data keys.

**Not yet integrated:** WebSocket ingestion, durable store/migration, historical response
scheduler, Telegram/web push gateway, credentials, data-entitlement enforcement and operational
dashboard. Any of these requires a separately reviewed production PR and live staging test.

## Provider/licensing approval gates
1. Confirm OPRA/venue licenses, complete tape coverage, nonstandard contract multipliers,
   transaction correction/cancel indicators, bid/ask quote synchronization, timestamps,
   conditions, rate limits, SLA and historical replay.
2. Get **written commercial rights** for internal processing, derived alerts, beta member
   delivery, ChatGPT-connected users, historical storage, caching, redistribution and
   retention. Per-user entitlements may be needed.
3. Massive: verify separately quoted business/redistribution contract; individual plans do
   not permit distribution to KST members. Unusual Whales: personal API forbids even derived
   redistribution; enterprise agreement required for a shared KST product. Alpaca indicative
   option prints are derived/delayed, insufficient for immediate flow classification.
4. Security review for secrets, RLS, admin-only ingestion, audit logging, idempotency,
   replay on reconnect and no unintended public raw-data endpoints.
5. Full offline integration tests, provider sandbox, delayed replay, one-session staging
   shadow mode, historical false-positive evaluation, cost and alert-volume review.
6. Only after separate approval: activate provider and notifications. No brokerage execution.
