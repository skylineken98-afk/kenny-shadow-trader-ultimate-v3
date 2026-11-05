# KST r5 — remaining feature implementation

This release adds all seven requested development areas plus a separate guarded execution service. The code is wired into the app; provider connections, billing and real-money trading are not automatically activated. Existing r4 chart-photo analysis, stock research plans, paper portfolios and private Request 3 archives are retained.

## Deploy in this order

Apply these rerunnable SQL files to the existing Supabase project, using the current backend root:

1. kst_options/schema.sql
2. kst_options/stocks.sql
3. kst_chat/schema.sql
4. kst_pro/schema.sql
5. kst_pro/execution.sql

Install updated requirements.txt, then redeploy the options, chat and push services. Add a Pro service using railway-pro.json / python -m kst_pro.worker. It handles earnings, company-news refreshes, private position monitoring, research evaluation, incidents and optional backups. Deploy the updated Cloudflare Worker plus every public/ asset, including pro.js. Old duplicated code under sql/ is preserved but is not the deployment root.

The included Dockerfile installs the PostgreSQL backup client and runs as a non-root user. The Nixpacks configuration also requests the client. Choose the appropriate build method and each service's intended start command. Never run the execution service merely because the other services deployed.

## New configuration

The .env.example lists per-service variables without secrets.

- Pro service: shared Supabase credentials, FINNHUB_API_KEY, Alpaca read/data credentials, STOCK_FEED and configured symbols. Calendar polls about every 30 minutes; configured ticker news rotates at most once a minute; private positions poll about every 30 seconds plus other work. On-demand ticker refreshes have claim leases and retry limits. Market-data delays and entitlements still apply.
- Chat service: reuse the previously approved OPENAI_API_KEY. Add KST_ADMIN_USER_IDS on both Chat and Pro services (comma-separated verified Auth user UUIDs), KST_SITE_URL (production HTTPS origin), STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET and STRIPE_MONTHLY_PRICE_ID when testing billing. Keep BILLING_LIVE_MODE=false and MEMBERSHIP_ENFORCED=false during beta testing. No new API key is included, exposed or provisioned by this build.
- Push service: existing VAPID settings plus current database migration. In AI P/L, select My private position exits and/or System alerts, then enable/update notifications while signed in. The server binds a subscription to the authenticated account only after verifying its private management token. Existing public stock/paper opt-ins are not silently expanded.
- Backups: BACKUP_ENABLED=false by default. To enable, supply DATABASE_URL, a persistent BACKUP_DIRECTORY volume, and BACKUP_ENCRYPTION_KEY (base64 encoding of a separate random 32-byte key). Keep the encryption key backed up separately. Seven encrypted archives are retained by default. pg_dump client/server compatibility must be verified. There is a 256 MiB beta-runner dump limit.

The Finnhub key needs access to the calendar/company-news/search endpoints used. Missing or forbidden data remains unavailable; the app does not invent events, articles, expected moves or historical reactions. Repeated calendar refreshes deactivate removed/rescheduled cached events atomically. Reported dates/timing are provider schedules, not independently verified company announcements. Options-implied moves use a fresh, near-ATM same-expiry OPRA straddle midpoint where available. This is not a probability or confidence interval. Historical reactions are simple close-to-close measurements and can be distorted by corporate actions.

## Accounts and memberships

My Stocks accepts user-reported long equity positions (up to 20 actively monitored per account), including entry, quantity, stop, target and optional fractional trailing giveback. Fresh bids generate STOP_INVALIDATION, TARGET_REACHED or TRAILING_GIVEBACK alerts transactionally. The monitor state becomes ALERTED; this is not a broker sale. Stop monitoring does not sell anything. Position records and private alerts are served only to their verified owner. Quotes are checked during the weekday New York regular-session clock window; this is not after-hours monitoring or a holiday calendar.

Monthly billing uses a server-configured active monthly Stripe price, a fixed production return origin, stable checkout idempotency and verified webhook signatures with timestamp tolerance. Browser-provided prices and user IDs cannot choose entitlements. Subscription events are idempotent and ordered per subscription; an old subscription cancellation cannot revoke a different active subscription or an independent free pass. Administrators can grant a 30-day pass, grant lifetime access or revoke only the free pass. The billing portal manages/cancels paid subscriptions. Test/live key mode must match configuration. Configure webhook snapshot events for checkout.session.completed, checkout.session.async_payment_succeeded and customer.subscription.created/updated/deleted at the chat Railway domain /webhooks/stripe.

When membership enforcement is enabled, new chat answers, Request 3 queues and new private position monitors require Pro or an active gift pass/admin status. Public research feeds remain free. Existing positions can still be viewed/stopped and risk alerts can continue after expiration; read-only history and account management remain accessible. The UI checkout is disabled until configuration exists; it shows the configured amount on Stripe before any payment. No payment was taken or checkout session created during development.

## Chat and research

Chat now forwards real incremental Responses text events through an SSE proxy. Completed answers are saved privately before the final done event. An interrupted client is directed to history; partial streams are not saved as completed answers. The server bounds concurrent connections and message/image sizes. Private search resolves history only within the authenticated account. Ticker/company recognition retrieves relevant cached news, earnings and option/stock context; own positions are labeled user-reported rather than broker-verified. Images are still not retained for future visual reinspection.

The research pipeline captures entry-known spread/Greeks/IV, timeframe regime, volume context and first-observed news availability. It deduplicates contract-days and separates/purges chronological training, validation and holdout periods. Ridge challengers use training-only imputation/scaling; selection uses validation and is measured on the untouched holdout. Exit replay uses ordered observed bid marks with one-cent premium slippage each way and configured round-trip fees. Incomplete histories do not get invented exits. Minimum sample/partition gates can leave the system COLLECTING. RESEARCH_PASS is evidence from retrospective data, not an automatic trading-rule/model promotion, a calibrated probability or a profitability guarantee. Collect prospective evidence before using a challenger in execution. Existing bounded ranking learning is retained separately.

## Dedicated live runner — disabled

A new, separate owner CLI supports an explicitly configured dedicated Alpaca account for whole equity shares or eligible standard long options, subject to broker approval/data access. It is not accessible to the website/chat, does not support arbitrary user broker accounts, does not automate Robinhood login and does not claim SPX support.

Do not activate until the transport, database concurrency, reconciliation, order lifecycle and risk exits have been tested against the selected broker's non-production environment. The adapter is pinned to the live endpoint; tests must inject a sandbox transport, not change production secrets. No live request or order was made here.

Execution requires all explicit environment gates in .env.example, separate LIVE_ALPACA_API_KEY/SECRET, an exact LIVE_ACCOUNT_ID, a dedicated-account acknowledgment and LIVE_RISK_ACK. Risk defaults are $100 allocation, $60 maximum order reference value and $10 daily equity-loss trigger. LIVE_TRADING_ENABLED and LIVE_DEDICATED_ACCOUNT default false; database entry control starts killed. Owner CLI: python -m kst_pro.execution status, enable, kill or run. Enabling changes only the control record; it does not run orders until the runner is started.

The runner verifies broker identity/eligibility, market clock, supported/tradable assets, buying power, whitelisted symbols, fresh bid/ask quotes, spread, available owned quantity and reconciled inventory. Stock entries use fresh public stock plans; options use fresh OPRA direction-aligned qualified records. It places bounded day limit orders, reserves exposure transactionally, and uses deterministic client order IDs. Unknown acknowledgments are reconciled by ID and are never blindly resent. Unmanaged positions/orders or unresolved intents block entries. Kill blocks new entries while risk-reducing exits continue. A daily loss trigger kills entries and attempts exits. Stock exits follow plan stop/target; initial option exits use -30%/+100% premium reference levels. These are basic explicit rules, not the research challenger's learned policy.

All risk exits are polled limit orders and can fail to fill, gap through a threshold, be rejected or be delayed by outages. The daily trigger is not a guaranteed maximum loss. Options can lose their premium. Corporate actions, exercise/assignment and unmatched manual activity require owner reconciliation and can stop automation. This first runner does not have a public order interface, fractional shares, short positions, multi-leg strategies, broker-native protective brackets or multi-user OAuth. A deployable adapter and controls are included, not a production-certified execution system.

## Reliability, backups and tests

Workers report heartbeats and job status. Missing/error heartbeats or failed tasks create operator incidents; opted-in linked admin subscriptions receive system alerts. Recovered heartbeats mark incidents recovered. Interrupted pending chat turns and exhausted data-request leases are recovered to explicit failure states. /health is process liveness; /ready checks database access, not all provider entitlements. Configure an independent external uptime check because a total database/host outage cannot reliably record its own alert. The admin panel displays heartbeat, job, incident, research and execution status without exposing keys.

Encrypted backup utility: python -m kst_pro.backup backup; verify an archive with python -m kst_pro.backup verify PATH. A restore requires a separate RESTORE_DATABASE_URL and the explicit --confirm-disposable-target switch. It does not restore automatically into the production database. Encryption authentication is tested; real dump/restore and volume durability still need a deployment rehearsal.

Local validation: 167 Python tests passed, with five optional full-server PostgreSQL tests skipped because that disposable server was unavailable; 22 Cloudflare API tests passed. An embedded PostgreSQL engine executed all five migrations and passed six assertion groups covering private alert atomicity/ownership, billing ordering/gifts, allocation reservations, durable per-user requests, RLS and restricted execution privileges. A Happy DOM interaction smoke passed earnings, ticker news, sign-in, personal position saving, account/admin display, streamed chat and logout clearing. JavaScript syntax, Python compilation, HTML ID/script checks and SQL/PLpgSQL parsing passed. ZIP CRC is checked during packaging.

Included CI runs the full-server PostgreSQL tests, including concurrent allocation reservation, plus embedded migration tests. Frontend CI includes actual mobile-viewport Chromium interactions with synthetic API fixtures. Real Chromium could not be downloaded in this session, so that browser test was not run here; DOM interaction tests are not a visual/mobile-device verification. No live Supabase RLS/Auth deployment, provider feed, OpenAI response, Stripe payment/webhook delivery, pg_dump/restore, VAPID delivery or broker order was tested. Keep billing enforcement and execution off until those deployment checks pass.

References used for integration contracts: official OpenAI Responses streaming documentation, Finnhub earnings/company-news API documentation, Stripe Checkout/webhook documentation and Alpaca Trading API/options documentation.
