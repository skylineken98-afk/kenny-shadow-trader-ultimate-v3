# KST unified distribution — release candidate 0 (NOT A PUBLIC RELEASE)

**Account correction:** The owner does NOT currently have an Apex account.
Apex is a prospective future integration and must not be represented as connected.

## One KST product, separate trust boundaries

Main existing application: **options, stocks and spot crypto**. Retain
sector rotation, signal ledger, paper research, news, Request a Signal,
and optional connectors as their present implementations permit.

Added in this staging branch:
* NQ/MNQ read-only alert engine, Telegram and Supabase outbox, SQL schema
* Private futures risk guard for **simulation only**. There is no NinjaTrader
  order adapter or Windows VPS here.
* Explicit distribution manifest with all new modules disabled by default.

Avoid combining broker secrets, consumer data and owner private strategy data.
Apex is **future-only**, not an onboarding prerequisite.

## User-facing module model

1. Market Research — options/stocks/crypto watchlists, source timestamps,
   provider data licensing, labels for actual versus synthetic prices.
2. Futures Signals — opt-in alerts, **only after licensed CME data**, clear
   signal-only label; no position execution.
3. Private Futures Lab — owner-only simulation dashboard, no public
   subscription access, no brokerage keys on public servers.
4. Connector Center — user authorizes their own ChatGPT/Claude access to
   permitted KST data; requires OAuth, scopes, revocation and user isolation.
5. Account and Billing — **not launch-ready** until secure customer auth,
   prices, payments, entitlement enforcement and privacy terms are tested.

## Release steps (ordered, do not skip)

1. Run full repo tests and both new test files; fix failing cases.
2. Review alert code for data edge cases: partial-session VWAP, holiday schedule,
   futures contract rollover, tick-size rounding and provider timestamps.
3. Protect all public customer routes with per-user auth and tested RLS.
   Shared APP_PASSWORD is **not** sufficient for multi-user distribution.
4. Create future data provider adapter; confirm license covers bot-generated
   alerts and any publication to users. Do not assume free retail chart feeds
   permit back-end redistribution/automated analysis.
5. Integrate Telegram bot user opt-in, message throttling, unsubscribe,
   per-user channel access and persistent outbox; dashboard UI pending.
6. Stage Supabase migration with service-role backend only and approved
   customer-readable RLS; don't expose service-role key.
7. Verify external AI connector OAuth scopes and user-specific read isolation;
   protect intellectual property and private futures data.
8. Validate billing/paywalls, rate limits, account onboarding/email redirects,
   privacy/terms, cancellation, customer support, secrets and health checks.
9. QA end-to-end on a staging deployment and run historical + forward testing.
10. Only then approve main merge, public deploy and customer invitations.

## Quick verification

```sh
python -m unittest discover -s tests -p 'test_nq_signal_alerts.py' -v
python -m unittest discover -s tests -p 'test_private_futures_risk_guard.py' -v
python -m unittest discover -s tests -v
```

The new test modules have been committed; they have NOT been executed as part
of this integration pass. No successful customer signup, live feed, NinjaTrader
session, or Telegram delivery is claimed. This branch does not enable orders,
change Railway, apply database migrations, buy data, or deploy.

## Prior review branches
- PR #21: Futures signal alerts (draft)
- PR #22: Private futures simulation guard (draft)
- PR #13: KST read-only connector
- PR #18: owner-only paper P/L and SPX candidate policy
- PR #19: offline options-flow detector
- PR #20: SPY paper opening model

Those other drafts should be reviewed independently; they have **not** been
merged into this release candidate. Do not advertise their draft functionality
as a production feature.
