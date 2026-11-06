# KST Membership, Broker Connections & Consent-Based Learning (design / not live)

## Membership and renewal price

- **Months 1–12 from signup:** USD $100/month.
- **ENZO** or **MAYVI**: month one is a 30-day free trial; monthly charges during the remaining first-year period are USD $50. Codes are mutually exclusive, one redemption per authenticated user.
- **Month 13 onward:** USD $150/month, with the amount and renewal date disclosed during signup. Future prices above USD $150 require separate product decisions, advance notices and any legally required affirmative authorization; trade success **must not** silently determine individual customer prices.
- Implement first-year/year-two transitions using verified Stripe subscription schedules with 2 phases, webhook reconciliation, cancellation handling, and test-clock coverage. This release introduces policy validation and fails checkout closed until `KST_BILLING_PHASES_VERIFIED=true` and correct prices are configured. **Do not enable that flag until actual schedule transitions are verified against Stripe test mode.**
- The first-year free-month coupon must not accidentally continue beyond year one. Stripe invoice previews and customer-facing disclosures must match the calculated price policy exactly.
- Live billing is NOT enabled by this draft. Owner admin access remains independent via the verified `KST_ADMIN_USER_IDS` entitlement.

## User account integration and consent

1. User signs into KST; account record is isolated by Supabase Auth user ID.
2. User chooses an **approved broker** and authorizes connection through broker-hosted OAuth; KST never asks for the user's brokerage password or forwards AI API keys to a broker.
3. Default is **read-only** positions, orders, fills and balance. OAuth tokens are encrypted in a dedicated managed secret store; the private database retains only references. Token scope is kept minimal, with reconnect and revoke paths.
4. Optional **collective-learning consent** is off by default. Disclose which de-identified features can be aggregated and where model-training data goes. Users can withdraw and delete retained identifiable training records. KST should stop including revoked records in future training; already-trained models require explicit retraining/deletion procedures.
5. KST privately attributes broker-confirmed fills as `USER_SELECTED_SIGNAL`, `POSSIBLE_MATCH` or `UNATTRIBUTED`. Only audited selection provenance can support `USER_SELECTED_SIGNAL`; timing/ticker correlation alone does not prove a KST recommendation caused the trade.
6. Train only on closed broker-confirmed outcomes after consent and quality controls. Separate **paper and live** trades, evaluate losers and winners, use chronological out-of-sample testing, and account for spreads, fees and survivorship bias.
7. Do not surface small cross-user cohorts or individual trade/account histories; aggregate results require at least 20 independent consenting accounts and privacy review, with suppression of thin segments and re-identification risk.
8. **Execution is disabled.** Before offering automatic trades, obtain broker approvals (including Alpaca Connect approval for commercial live execution), legal/regulatory review regarding investment-adviser status, user-specific signed authorization, explicit separate opt-in, scope-limited broker credentials, a kill switch, position/size/day-loss caps, order idempotency, confirmations, audit trail, and a user-controlled pause/revoke flow.
9. Not every broker exposes account APIs or option-order placement through approved third-party integrations. A broker connector available within ChatGPT is not an API credential KST can reuse. The broker/provider must explicitly support KST's application and endpoints.

## Implementation in this branch

- `kst_pro/pricing_policy.py` defines publicly auditable first-year, promo and renewal amounts and rejects unverified checkout schedules.
- `kst_pro/broker_learning.py` defines consent gates, read-only scope and conservative signal attribution; does NOT connect brokers or send orders.
- `kst_pro/broker_learning.sql` drafts owner-scoped consent, broker-fill and outcome tables with RLS and no raw tokens. Requires a staging migration and security review before any production database change.
- Tests in `tests_pro/test_broker_learning_pricing.py` verify costs, broker permission denial, opt-in and attribution.

**Not finished:** Broker OAuth registration/provider approval, encrypted token vault, actual fill synchronization, audited signal-click provenance, a complete collective learning service, a per-user privacy portal, licensed broker execution, verified recurring billing schedule, or production rollout. Never claim any of these are live.

**Sources to review before release:** Stripe subscription schedules, Alpaca Connect OAuth and commercial app approval, SEC digital investment adviser rules, FINRA auto-trading risk guidance.
