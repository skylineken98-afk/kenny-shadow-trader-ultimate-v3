# Kenny Shadow Trader Ultimate V2 — integration package (beta / paper-only)

## What is actually implemented

- Preserves the uploaded V2 Streamlit dashboard, yfinance underlying trend scan, basic manual paper journal, and risk gate.
- Archives the supplied V1 Python source under `legacy_v1/` for reference; **the original V1 options logic is not yet wired into V2 runtime.**
- Bundles the supplied Supabase CSV under `imports/` and a safe local `legacy_signal_archive` importer. **Importing a CSV is not syncing with Supabase.**
- Adds a News Intelligence page and `news_worker.py`: fetches public source-linked RSS headlines, ranks by keywords, tags potentially related markets, and deduplicates stories locally. **No article generator, push alerts, automated trade triggers, paid news rights, or guarantees of news latency are implemented.**
- No actual live execution or autonomous paper orders; do not enter live brokerage keys in this repository.

## Easiest installation (keep V1 and current V2 safe)

1. Keep backups of both existing GitHub repositories and Supabase export. **Create a new GitHub repository** for this ZIP; don't delete or replace your existing V1/V2 yet.
2. Extract ZIP, upload its CONTENTS (including `app.py` at repository root). Never commit `.env`, `.streamlit/secrets.toml`, broker keys or service-role keys.
3. In Streamlit Community Cloud create a separate app from the new repository: main module `app.py`; requirements will be installed from `requirements.txt`.
4. Open **News Intelligence** in the sidebar and press **Fetch newest articles**. Errors are shown if remote sources reject/block connections. Configure licensed feeds before a public production launch.
5. In a local terminal, or an isolated Railway environment with persistent volume, run `pip install -r requirements.txt`, then `python import_v1_history.py` to import 90 original raw CSV rows (duplicates remain in archive for audit), then `python news_worker.py` to populate stories.
6. For 24/7 updates, run `python news_worker.py` on a recurring worker (Railway scheduled job, for example). **Streamlit Community Cloud and GitHub Actions local SQLite files are not a reliable shared permanent database.** For public release migrate app and worker to one secured Supabase/Postgres project with Row Level Security and server-only service-role credentials.
7. Run `pytest -q` to check included offline unit tests. Check workflow secrets, APIs and actual market data manually.

## Important unfinished production features

- Bring V1 Alpaca stock/options contract generation into isolated V2 service with verified market-data entitlements; validate expirations and OCC symbols.
- Durable Postgres persistence, stable signal IDs and quote tracking; keep 90 imported duplicates separate from actual independent recommendations.
- Real options quotes/Greeks, spreads, historical fills, true paper broker simulator, crypto/forex/futures-specific data.
- Verified time-stamped news/article summaries, premium provider licensing, topic classification, original long-form articles, push alerts/Telegram notifications, reliable 24/7 service.
- Authentication, paid subscriptions, staff management, privacy policy, moderation, audit logs, backup, public-app load tests.
- Broker execution only after explicit account authorization, broker-supported routes, exchange rules, independent kill switch, reconciliation, limits, and extensive paper testing.

## Security

The archived V1 source may contain the *names* of environment variables; scan it for accidentally included literal secrets before publishing. This package never includes your API secrets. Never deploy a public Streamlit app that lets unauthenticated users submit unlimited scans or access server credentials.
