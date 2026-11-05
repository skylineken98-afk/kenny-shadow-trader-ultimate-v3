# KST r5 feature map

| Requested area | Implemented code | Activation / practical boundary |
|---|---|---|
| Upcoming earnings | Provider calendar, timing, date windows/ticker filters, optional near-ATM straddle move and historical reactions | Finnhub credentials and endpoint access; options estimate also needs fresh OPRA/stock quotes. Dates remain provider-reported until independently confirmed. |
| Ticker/company news | Company lookup, provider-tagged ticker articles, company/earnings/filing filters, separately labeled broad market context | Configure Finnhub; CNBC sector feed remains available. No full articles are republished. |
| Personal stock tracking | Private user-reported entries, shares, stop/target/trailing rules, fresh-bid marks, durable private alerts and linked Web Push | Apply r5 migration and run Pro/push workers. Long equities only; monitoring never sells shares. |
| Reliability | Bounded HTTP concurrency, heartbeat/status/incident reporting, opted-in admin push, retry leases, interrupted-chat recovery, encrypted backups/restore utility, CI and database/browser tests | Configure operator UUIDs, push and a persistent backup volume/key. External uptime monitoring and restore rehearsals remain deployment tasks. |
| Adaptive research | Entry-known Greeks/IV, regime, volume and news-availability features; chronological/purged ridge challengers; recorded-quote exit replay with fees/slippage | Collect adequate data. Retrospective pass does not change trading rules or establish profitability; validate prospectively. |
| Memberships | Monthly Stripe Checkout, signed replay-safe webhooks, subscription portal, server-side Pro gates, admin 30-day/lifetime/revoke passes, audit trail | Configure production site origin, Stripe test credentials and active monthly price first. Enforcement and live billing default off. |
| Chat improvements | Real Responses streaming through proxy, private history search, ticker-specific market/earnings retrieval and own user-reported positions | Existing approved OpenAI key/model and deployed authenticated chat backend. Chart images remain current-request inputs only. |
| Automated execution | Separate owner-only Alpaca equities/eligible long-option runner, broker account checks, stable order IDs, transactional allocation reservations, reconciliation, kill/daily-loss entry stops and risk exits | Defaults OFF. Requires dedicated account, separate live keys, exact account ID, explicit risk acknowledgment and owner enable command. No Robinhood execution or SPX coverage is claimed. No live orders were submitted here. |

Read RELEASE_R5.md for deployment order and verification evidence. Existing r4 chart uploads and private Request 3 archives are retained.
