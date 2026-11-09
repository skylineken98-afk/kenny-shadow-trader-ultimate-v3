# KST NQ/MNQ research-only alerts (development branch)

This worker has **no** broker SDK, brokerage credentials, order route, order placement,
cancel, or modification actions. Do not attach Apex or Tradovate logins. No deployment
is made by this PR. No historical performance or fill results are claimed.

## Data contract (not yet fulfilled)
A separately licensed, permissioned CME futures market-data provider (for the user's
and KST application's usage) must provide **current, completed, UTC-aware, contiguous
one-minute OHLCV bars** for individual NQ and MNQ active contracts:
`GET ${KST_NQ_DATA_URL}?symbol=NQ` (and MNQ)
returns `{"symbol":"NQ","bars":[{"timestamp":"2026-11-09T15:00:00Z","open":1,"high":2,"low":1,"close":2,"volume":100},...]}`.
Those example prices are schema placeholders, not a valid or live quote.
At least 75 consecutive bars are needed per symbol, ending no more than 90s after
the last bar's close. For valid **session VWAP**, the feed must return all continuous
bars since the CME 18:00 ET session start, potentially more than 75 bars; the
current engine calculates VWAP on *the supplied session subset*, so partial session
history biases it. Before real alerting, require the full session or pass a
provider-verified session VWAP. Contracts must be explicitly mapped by the provider,
including roll schedules; never silently mix expiries. Data must include session
and holiday/early-close calendar metadata; the built-in schedule is indicative,
not authoritative. Provider data agreement must permit webhook/UI alerts and
internal KST processing, and any redistribution to users.

## Signal algorithm v1
Closed one-minute breakout over prior 20-bar high, or below prior low, with
relative volume >=1.2, EMA20/EMA50 directional agreement, and session VWAP
agreement. Uses previous six candles including signal candle to set stop;
alert trigger is the signal close (not guaranteed entry). Target is 1.5x that
reference risk. A-grade at RVOL>=1.8 plus VWAP separation threshold; B-grade
otherwise. Grades are rules-based, **not calibrated probabilities**. Each bar
can generate at most one deterministic signal ID per symbol/direction, though
consecutive qualifying bars may produce separate signals. NQ and MNQ can
produce correlated duplicate opportunities; downstream UI should group them.

Signals include UTC close/as-of timestamp, trigger, stop, target, grade,
direction and status SIGNAL_ONLY_NOT_EXECUTED. No simulated trade performance.

## Notifications and operations
The persistent SQLite outbox is deduplicated by (signal_id, channel), with
independent Telegram/website delivery states. Use a Railway persistent volume
for KST_NQ_OUTBOX_PATH or replace with durable Postgres storage before deployment.
Telegram may deliver duplicates if the network fails after Telegram accepts a
message but before our outbox acknowledges it; deduplication is best-effort.
Website insert uses a unique signal_id for retry safety.

Website integration: create the restricted Supabase table using
`docs/sql/kst_nq_alerts.sql` and then connect the application frontend or
Cloudflare Worker to its authenticated read endpoint. The SQL table alone does
**not** add a dashboard component.

Required environment variables on a **new isolated read-only Railway worker**:
- KST_NQ_DATA_URL (HTTPS provider adapter endpoint)
- KST_NQ_DATA_TOKEN (if provider uses bearer authentication)
- KST_NQ_TELEGRAM_TOKEN, KST_NQ_TELEGRAM_CHAT_ID
- SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (backend only, never in browser)
- KST_NQ_OUTBOX_PATH (persistent disk path)
- KST_NQ_POLL_SECONDS (10–60, default 15)
Never configure KST_NQ_ORDERS_ENABLED, broker keys, or API trading permissions.
Do not reuse unrelated binary Telegram bot credentials without approval.

Run locally: `python -m unittest discover -s tests -p test_nq_signal_alerts.py -v`
Worker entrypoint when approved: `python -m core.nq_signal_worker`.

## Railway inventory checked 2026-11-09
- vivacious-analysis / kenny-shadow-trader-ultimate-v3: existing paper/scan
  variables, Supabase configuration; no listed Telegram credential.
- patient-stillness / kst-push: VAPID and Supabase variables; not a Telegram
  notification bot.
- KST Binary / kst-binary-telegram: separate binary/OTC research service;
  variable list shows BOT_USERNAME, but no Telegram bot token or chat ID.
  Do not conflate the two bots.

## Must complete before deployment
1. Confirm licensed provider, CME agreements, tick/volume definitions, NQ/MNQ
   expiry mapping and a completed-bar API; implement and test its adapter.
2. Require full session VWAP data, actual CME holiday calendar and instrument
   tick-size rounding (NQ/MNQ both 0.25 points); validate regular/extended
   session classifications; show source and feed latency.
3. Configure Telegram bot token and destination chat ID securely and test
   delivery with a non-trading synthetic alert to a private test chat.
4. Apply Supabase schema with appropriate RLS/read access; implement website
   authenticated alert feed and verify on mobile.
5. Attach persistent outbox storage, metrics/healthcheck, retries/backoff,
   privacy policy, alert throttle, correlated symbol suppression, and
   post-restart deduplication. Configure per-user notifications.
6. Run synthetic tests, historical replay, data outages, deployment staging,
   and an observed forward paper period before production approval.
7. Verify Apex and Tradovate rules; user retains all manual trading authority.
