# Current release: r5

Read **RELEASE_R5.md** for deployment order and **FEATURE_MATRIX_R5.md** for the current feature status. Earlier release notes below are retained as history. Billing enforcement and the separate live execution runner default OFF. Provider/account configuration and deployed verification remain required.

---

# KST — one combined download

This ZIP includes ALL of the previous mobile connection update plus the full preserved Python backend, ranked-options research, price tracking, private fill imports and bounded adaptive ranking. You do not need the previous ZIP.

There are two deployment destinations because Cloudflare hosts the mobile website and Railway runs Python. Uploading the whole ZIP to only one service will not activate both.

## 1. Database: one additive SQL setup

In your existing Supabase project, open SQL Editor and run the contents of:

RAILWAY_BACKEND/kst_options/schema.sql

It creates new tables with RLS enabled and server-only access. It does not change ultimate_signals or its policies. No broad public SELECT policy is added. Do not run your old full bootstrap again.

## 2. Railway: preserve the working scanner and add options

Update your existing backend repository with the contents of RAILWAY_BACKEND (merge/upload the contents, rather than nesting the RAILWAY_BACKEND directory inside your existing code root). Existing files are preserved from the supplied archive; the new package is kst_options and its tests.

Keep your current working scanner service and its start command unchanged.

Add ONE additional Railway service from the same backend repository. In its Settings, set the Start Command to:

    python -m kst_options.worker

The repository railway.json still specifies the original scanner start command. If your Railway setup prioritizes that file over the service's override, point the NEW service's configuration-file path to railway-options.json instead. Confirm its logs run the options worker, not workers.scan_worker.

Add/reference these variables on the NEW options service:

| Variable | Value |
| --- | --- |
| SUPABASE_URL | Same working value as the existing scanner |
| SUPABASE_SERVICE_ROLE_KEY | Same working server key as the existing scanner |
| ALPACA_API_KEY | Your Alpaca market-data key |
| ALPACA_API_SECRET | Matching Alpaca secret |
| OPTIONS_FEED | opra |
| OPTIONS_SYMBOLS | SPY,QQQ,IWM initially; expand after coverage is verified |
| OPTIONS_SCAN_SECONDS | 300 |
| OPTIONS_TRACK_SECONDS | 60 |
| OPTIONS_ROUND_TRIP_FEE | Your estimated total fee for buying AND selling one contract; use 0 if unknown and understand fees are then excluded |

OPRA access depends on your Alpaca data entitlement. This package does not purchase a subscription. OPTIONS_FEED=indicative is supported for explicitly labeled research, but those modified quotes never train the OPRA research model. There is no automatic downgrade on an entitlement failure. SPX coverage is NOT assumed; add it only after the provider confirms support. Unsupported symbols produce health warnings, not substituted contracts.

No Python backend public domain is required for this setup: both services communicate through Supabase. No orders are submitted.

## 3. Cloudflare: replace the mobile source

Upload the CONTENTS of CLOUDFLARE_MOBILE to your existing mobile GitHub repository. worker.mjs and wrangler.jsonc belong at root; public/ is a subfolder. Do not upload RAILWAY_BACKEND to the mobile repository.

In the existing shadow-trader-mobile Cloudflare Worker, add:

- SUPABASE_URL (text): same project URL as Railway.
- SUPABASE_SERVICE_ROLE_KEY (Secret): same working backend key. Never put this key into public/ or GitHub.
- PUBLIC_SIGNALS_ENABLED (text): true, if you want public visitors to see the research feed.

Enabling the public feed exposes ONLY the allowlisted research contract/setup fields, observed estimated results and aggregate learning status. Private imported fills and realized trade outcomes are never queried by the mobile Worker. A dedicated read-only database role is a future hardening option; this implementation uses your server-only service credential and fixed read-only queries.

Deploy command: npx wrangler deploy
Build command: leave empty. Static-assets-only drag-and-drop is insufficient; the Worker must be deployed too.

Refresh Safari, then the installed mobile app. Under Scanner choose category and maximum contract cost. Under Brain check the options worker health and active model. The new service worker removes old Shadow Trader caches.

## What is implemented

- Top three qualifying contracts per category and each supported budget ($30/$50/$100/$200/$500/$1,000/$3,000).
- Categories: 0DTE = same New York date; Swings = 1–45 calendar days; LEAPS = 270–730 days. Other expirations are not included.
- Paginated Alpaca chains; structural quality rank based on spread, delta quality and affordability. Fresh quotes <=5 minutes, positive bid/ask, spread <=15%, absolute delta 0.20–0.80. Standard OCC 100-multiplier contracts only. No volume or open-interest filter is claimed.
- CALLs and PUTs are research candidates, NOT predictions of direction or automatic buy instructions. Underlying SETUP/WAIT checks remain displayed separately.
- Immutable recorded ask entry; subsequent bid-based estimated P/L for one contract; a frozen round-trip fee estimate; observed maximum gain, worst return from entry and giveback. +50% and −30% flags report observed levels, not assumed fills or automatic exits.
- Quotes are polled, not tick-by-tick. Peaks and level crossings BETWEEN polls can be missed. Bid availability does not guarantee a fill.
- Fixed measurement horizons: 0DTE one hour, Swings one day, LEAPS seven days, capped at expiration day 4pm New York. These are research measurement windows, not recommended hold times. Early-close sessions, weekends and missing quotes can produce unresolved outcomes.
- Horizon results require a fresh bid within 30 minutes after the due time. Missing/late/expired records become UNRESOLVED, not fabricated profits or zero-value settlements.
- Original stock/crypto scanner and all previous backend files retained.

## Self-adaptation: exact scope

This is bounded automatic calibration of three ranking weights, not neural-model fine-tuning and not self-editing trading code. Weights stay within a small predefined candidate grid. It does not learn market direction, an optimal exit policy, or chop detection from three contract-quality features alone.

Once at least 100 eligible contract-day outcomes exist, it uses an 80/20 chronological split, purges training outcomes not yet available at the holdout start, and requires >=60 training / >=20 holdout observations. It chooses a challenger on the earlier data, then tests it once on later data. Promotion requires improved training selection returns and a holdout advantage exceeding two percentage points over current weights. Outlier returns are clipped for evaluation. Later evaluations require 50 additional distinct contract-day outcomes. Rejected models do not replace active weights. Future published entries receive the promoted weights; historical scores are never rewritten.

OPRA research estimates and imported executed trades are not mixed into a single training set. Eligible personal executed-trade outcomes take priority once enough complete, context-matched samples exist. Otherwise the system uses OPRA research estimates. All actual fills can be retained privately; trades without contemporaneous recorded contract features cannot teach these ranking weights. This avoids inventing historical information. Sampling only published candidates creates selection bias; chronological validation does not establish profitability or guarantee improvement.

It can collect data immediately after setup. It cannot legitimately claim to improve after your first trade or to get stronger every day. Watch the Brain tab for baseline/collecting status versus an actual model promotion. The original LLM/AI features in the preserved backend are not activated by this update.

## Learn from your actual trades

The worker cannot see your main Robinhood trades automatically. Export a complete fill history or prepare the documented CSV, then import privately from a trusted backend shell. Do not commit the filled CSV or upload it to the public mobile app.

    python -m kst_options.import_fills /private/path/fills.csv

Required CSV columns:

    fill_id,filled_at,contract,side,quantity,price,fees

Use unique broker fill IDs, timezone-aware timestamps, full OCC contract symbols, BUY or SELL, positive integer contract quantities, premium per share and per-fill fees. A format-only empty header file is included. Source remains USER_IMPORTED_NOT_BROKER_VERIFIED. Re-imports of the same fill ID are idempotent; conflicting IDs abort. Partial exits and fees are included using FIFO long lots. Full opening history is required; unmatched sales and short strategies are unsupported and abort before writes.

Completed lots with an OPRA research record from <=90 minutes before entry get a private training outcome. Unmatched fills are retained but not assigned invented features. Do not manufacture historical context to fit a trade. Your SPX +$500 giveback can be reviewed from its complete fills, but intratrade peak unrealized P/L needs quotes recorded while the position was open; fills alone cannot reconstruct it. Actual-trade peak tracking and automatic Robinhood synchronization are not included. Research signal peak/giveback tracking is included.

## Validation and remaining setup

Locally verified: nine Python calculation/learning/session/news/proxy tests, ten Cloudflare API tests, and syntax/compile checks. These cover stale/crossed quotes, immutable entry estimates, fees, partial exits, look-ahead purging, model promotion/rejection, private-field exclusion, key headers and configuration failures. Provider/database integration and deployment were not tested with live credentials. No keys are embedded. Use Brain status and Railway logs after setup; an active deployment alone does not prove data entitlement or database connectivity.


## Session giveback review (private)

The fill importer also creates private New York daily session reviews: realized P/L, running realized-profit peak, dollar/fraction giveback, BUY/SELL fill counts, losing-exit streaks, and same-contract re-entry within five minutes after a sale. This captures the difference between giving back profit inside the first position and losing it in later positions. It does not infer emotion or identify price chop from fills alone. Partial fills can increase fill counts; they are not necessarily separate decisions.

Reports are printed privately after import and saved in kst_session_reviews under RLS. They are NOT published by the mobile site. They do not automatically stop your main Robinhood trading or train an exit/regime classifier. Adaptive contract ranking remains the bounded, validated module described above. A future broker-connected private dashboard and contemporaneous market-regime data are needed for those additional capabilities.


## News, fresh Top 3 requests and SPY-based SPX proxy — latest additions

This replaces earlier package descriptions that said news and requests were missing. Reapply kst_options/schema.sql if you ran an older version: its new CREATE TABLE IF NOT EXISTS and ADD COLUMN IF NOT EXISTS statements are additive. Deploy both repositories again.

- News: the Railway options service also polls CNBC RSS every five minutes, even if option data is unavailable. Public visitors see headlines, source links, published times and heuristic sector/importance labels. No full articles are copied. The default top-news feed is configured, but live feed reachability was not verified here; failures are visible in the News tab. You can configure up to eight comma-separated CNBC RSS URLs with NEWS_RSS_URLS. NEWS_POLL_SECONDS defaults to 300. This is not an independently verified newswire or an earnings calendar.
- Fresh Top 3: the button queues a real new scan, bypassing the normal five-minute cadence. It uses the chosen category and budget across OPTIONS_SYMBOLS, not an arbitrary user ticker. The browser polls request status for up to three minutes; longer jobs remain visible through the regular feed and Railway logs. Requests in the same category/budget/minute share one job. The included Cloudflare REQUEST_LIMITER binding allows three submissions per client IP per minute per Cloudflare location. The binding must be deployed from wrangler.jsonc; no IP address is saved in the request table.
- Requests aim to return three contracts. Strict-quality candidates come first; remaining slots may use explicitly labeled WATCHLIST candidates with spread up to 25% and absolute delta 0.15–0.85. Fresh quotes, positive bid/ask, affordability and standard-contract checks are never bypassed. Fewer valid candidates means fewer results. Watchlist fallback records never teach the research ranking model. Their estimated outcomes can still be tracked for review.
- Context: a recent underlying SETUP can label a CALL/PUT BULLISH_SETUP_ALIGNED or BEARISH_SETUP_ALIGNED. Otherwise it is STRUCTURAL_ONLY or COUNTER_TREND_RESEARCH. The preserved underlying scanner supplies its existing 4H/1H/5M rules. These labels do not turn every request into a confirmed entry or activate 1H/15M/1M scalping rules.
- SPY/SPX: the Home panel uses matched regular-session SPY and ^GSPC minute closes from Yahoo Finance as an anchor, and a later Alpaca SPY trade. The formula is SPX_anchor × latest_SPY / SPY_anchor. The regular-session clock window shows no synthetic estimate. Outside that window a fresh SPY trade (<=5 minutes) and a reference <=96 hours old are required. Missing data produces no estimate. Sources and timestamps are shown. This is not an official index quote or next-open prediction; dividends, basis differences and new information can break the relationship.
- Add STOCK_FEED=sip to the new Railway options service if entitled. iex is an explicit alternative with more limited venue coverage; there is no silent substitution. This package does not activate a 24-hour/overnight stock venue. If your feed is stale after its trading session, the panel withholds the estimate. The service can run continuously while its data sources have gaps.

The public feed flag also enables public research-request jobs, news headlines and the proxy. Personal imported fills remain private. Existing setup instructions and limitations still apply. Local checks: 19 tests passed plus syntax/compile and ZIP integrity checks. Live CNBC, Alpaca, Yahoo Finance, Supabase and Cloudflare integration still require deployment and verification.

## AI Progress tab — $300 paper accounts with live option prices

The mobile AI P/L tab now shows five separate PAPER accounts: Conservative, Balanced, Aggressive, Challenge and Daily 10% Research. Each NEW account starts at $300 virtual cash. The SQL uses ON CONFLICT DO NOTHING; rerunning setup never resets existing research balances or erases losses. Your personal brokerage allocation and other legacy simulation accounts are not modified.

Apply the updated kst_options/schema.sql and redeploy both repositories. The same options worker runs the paper ledger; OPTIONS_PAPER_AI_ENABLED defaults to true (set false to pause new research-account processing). No extra service, brokerage order permissions or OpenAI key is needed. The manual local journal remains accessible under More.

- Paper entries require an OPRA contract, strict contract quality, a recent matching BULLISH/BEARISH underlying setup, and a separate latest premium quote no older than 60 seconds. The ask must have displayed size; spread must remain <=15%. The paper entry uses THAT quote's ask, not an old scanner premium. Quotes are real; fills are simulated and are not guaranteed executable.
- Each agent holds at most one standard 100-multiplier long option at once. Cash is actually reserved in a persistent research ledger. SQL row locks serialize entry/exit accounting. Duplicate signals and same-contract re-entry within 30 minutes after closing are rejected.
- Estimated stop-risk limits use the original profile fractions: Conservative 0.5%, Balanced 1%, Aggressive 2%, Challenge 2.5%, Daily 10% Research 1%. A modeled 30% premium loss plus the frozen fee estimate must fit that budget; a full contract must fit available cash. With $300, many candidates WILL be unaffordable under those constraints and the account will show WAIT. No fractional option contract or fabricated trade is used to force activity. A gap through a stop can lose more than the estimated stop risk, up to the premium.
- Realized paper P/L comes from a modeled exit at a later observed bid: an observed −30% net return, +50% return or the measurement deadline triggers closure. Full round-trip fees are reserved at entry, so equity and realized results include that estimate. Polling gaps/slippage/queue position/assignment/expiry settlement are not simulated. Missing prices keep the position unresolved with a stale-value warning; they do not turn into invented fills. Agent measurement exits are independent of the research signal's strict horizon training labels.
- Account value = cash + last observed bid × 100 for open contracts. Starting balance, cash, realized/unrealized/total P/L, return, closed-trade count, wins, open positions and last decision reason are shown. The backend continues processing while the mobile page is closed. Quote availability still depends on the feed and market session.
- These are public demonstration/research accounts when PUBLIC_SIGNALS_ENABLED=true, not your personal imported fill accounts. Private personal fills remain excluded from the public API.

## How paper results help the Brain

Completed eligible OPRA paper positions automatically create kst_agent_outcomes rows with their entry-known features. They can teach the same bounded ranking learner after its sample/validation gates. Sources are kept separate: eligible actual imports take priority when sufficiently populated, followed by paper OPRA outcomes, followed by fixed-horizon OPRA signal estimates. Models still need at least 100 eligible contract-day samples; five agents trading the same contract do NOT count as five independent contract-day examples.

The update also records current underlying market snapshots, deterministic timeframe-regime labels, WAIT/entry/exit decisions and paper outcomes. Mixed timeframes are labeled mixed, not falsely identified as chop. This establishes a context/memory foundation. It is NOT a completed human-like brain, a learned exit policy, a self-modifying strategy engine or proof of live profitability. Next stages need richer features (news at decision time, volatility, order flow and regime), historical replay with realistic execution, and prospectively evaluated strategy/exit challengers. A reasoning model could propose experiments, but results must be measured before adoption.

Local checks now comprise 22 unit/API tests plus syntax/compile checks. The PostgreSQL ledger functions/triggers have not been exercised against your live database. After deployment verify all five fresh accounts display $300, an eligible paper entry reserves cash, a later observed bid updates equity, and a closed paper position creates its learning outcome. Do not call paper trading active solely because the site deployed.

## Paper trade activity and opt-in mobile notifications — newest update

AI P/L now includes a public chronological activity feed (last 100 events, refreshed every 15 seconds while visible). Each paper ENTRY/EXIT is posted transactionally by database triggers alongside the ledger update. Cards show agent, contract, quantity, premium, price quote time, posting time, exit reason and realized paper P/L. No event is invented merely because a scanner finds an idea. Historical entries before this migration are not backfilled or pushed.

The event schema and notification preferences include ADD. Current portfolios still hold one contract and do not pyramid or partially exit; automatic add-on events are not claimed. Future scaling must update the ledger and append a real ADD event in the same transaction. The current migration automatically generates ENTRY and full EXIT only.

### Enable push while the mobile app is closed

1. Apply the latest kst_options/schema.sql and update both repositories.
2. Install the updated backend requirements, which include pywebpush.
3. In a PRIVATE environment, run:

       python -m kst_options.generate_push_keys /private/kst-push-keys

   This writes vapid_private.txt (base64 DER, mode 0600) and vapid_public.txt. Do NOT put these files into the repository, public folder, shared ZIP, screenshots or chat. Keep a secure backup; replacing the key pair requires visitors to subscribe again.
4. Add the CONTENTS of vapid_public.txt to Cloudflare as VAPID_PUBLIC_KEY. This key is intentionally public. Keep the included REQUEST_LIMITER binding.
5. Add a separate Railway service from the same backend repository, start command:

       python -m kst_options.push_worker

   If needed, select railway-push.json as this service's config file. Add SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, VAPID_PRIVATE_KEY (the CONTENTS of vapid_private.txt, stored as a secret), and VAPID_SUBJECT (mailto: followed by your contact email). The private key is never sent to the mobile browser. The options service continues recording trades independently of notification delivery.
6. Deploy the push service and Cloudflare. On iPhone/iPad, add KST to the Home Screen, open that installed app and tap Enable / update notifications in AI P/L. On supported desktop/Android browsers use the same button. Permission is requested only after the visitor taps; there is no automatic opt-in.
7. Visitors select ENTRY / ADD / EXIT and can turn notifications off in the tab or device settings. Saving preferences does not prove successful delivery. Validate an actual future paper event on a subscribed device after deployment.

Subscription endpoints, encryption keys and hashed private management tokens live in RLS-protected tables; the public activity API never exposes them. The backend queues only NEW matching events for active opt-ins, supports delivery leases/retries, disables expired endpoints on 404/410, checks preferences again before sending, and uses provider-domain restrictions to reject arbitrary endpoints. No IP address is stored. A 3-attempt retry cap and ten-minute event freshness window avoid replaying an old backlog. Delivery can be delayed, fail, expire or be duplicated after an ambiguous network error; notification tags reduce duplicate displays. This is not a guaranteed trading execution or emergency-alert channel.

The push worker checks for jobs every five seconds. Event generation still follows the options paper worker's real quote cadence (roughly once a minute plus processing delays). Providers can deliver to opted-in installed apps when the page is closed, subject to browser/OS support, permissions and connectivity. A constantly running server does not create continuous market data outside feed coverage.

Validation: 27 local tests passed (13 Python, 14 Worker API) plus syntax/compile and ZIP integrity checks. Live PostgreSQL trigger behavior, encrypted end-to-end push delivery, Apple/Google/Mozilla/Windows endpoints and VAPID provisioning were not exercised here. The package contains setup code, not live push credentials or verified subscriptions.

## KST Chat — private market assistant (latest addition)

The mobile Chat tab now includes sign-in/account creation, conversation history, conversation deletion, user-controlled memory (add/edit/delete), retrieval from your own past conversations, and timestamped KST snapshot references. The assistant reads current stored news, contracts, underlying setup checks, public paper activity/accounts, model status and the SPY/SPX proxy. It has no trading, strategy-changing or account-configuration tools. It cannot access main Robinhood positions or private imported fills. It uses the OpenAI Responses API, with model responses not retained as retrievable API response state (store=false); your own chat history is saved privately in Supabase. This does not imply zero retention across all provider security/operational systems.

Reuse the existing OPENAI_API_KEY you confirmed is in Railway; do not paste it here or copy it into public code. A variable on the OLD service is NOT automatically present on a NEW service unless you reference/share it explicitly.

### Activate chat

1. Apply the separate RAILWAY_BACKEND/kst_chat/schema.sql in the existing Supabase project. It creates private conversation, turn, memory and quota tables. Each user's direct reads are protected by RLS; authenticated browser users cannot directly mutate these tables. The chat service checks ownership again on every private operation. Apply the main options SQL separately for KST snapshot data.
2. In Supabase Auth, enable email/password sign-in and configure your production Site URL and confirmation redirect URLs. Keep email confirmation enabled. New users create an account and confirm their email before using chat; the server rejects unconfirmed and anonymous users. Configure email delivery for a public launch. Password reset UI is not included in this initial chat version. Session tokens are stored only in this browser tab's session storage, not permanent local storage; passwords are never saved by the application.
3. Add a separate Railway service from the same backend repository. Start command:

       python -m kst_chat.server

   If the original railway.json overrides the command, select railway-chat.json for this service. Generate its HTTPS public domain. This initial transport uses a bounded, dependency-light Python HTTP service behind Railway HTTPS; it is intended for a limited beta, not an enterprise traffic claim. A production framework/gateway, broader load testing and operational monitoring remain follow-up hardening.
4. Add/reference these variables on the NEW chat service:

   | Variable | Value |
   | --- | --- |
   | OPENAI_API_KEY | Reference your existing working Railway key |
   | SUPABASE_URL | Same project URL |
   | SUPABASE_SERVICE_ROLE_KEY | Existing backend secret, server-side only |
   | SUPABASE_PUBLISHABLE_KEY | Public sb_publishable_ key (or SUPABASE_ANON_KEY with the legacy anon key) |
   | CHAT_PROXY_TOKEN | A new random secret of at least 32 characters, shared ONLY with Cloudflare |
   | OPENAI_CHAT_MODEL | gpt-5-mini by default; must be available to your API project |
   | CHAT_ALLOWED_EMAILS | Recommended for initial beta: your email, or comma-separated invited emails; empty permits all confirmed Auth users |
   | CHAT_DAILY_LIMIT | 40 by default, capped at 100 per user/day |
   | CHAT_GLOBAL_DAILY_LIMIT | 500 by default, capped at 2,000 for the whole site/day |

   Generate CHAT_PROXY_TOKEN with a password manager or another trusted random-secret generator. Do not commit it, print it in deployment logs or put it in the ZIP. Public/publishable Supabase keys are different from service/secret keys; the chat config refuses secret/service keys as browser auth keys. API usage is billed to your OpenAI project; the code does not assume ChatGPT subscription billing covers it. Counts are message allowances, not dollar spending caps. Configure appropriate provider/project spend controls separately.
5. Add CHAT_BACKEND_URL (the new Railway service's HTTPS *.up.railway.app domain) and the SAME CHAT_PROXY_TOKEN secret to the Cloudflare mobile Worker. The included CHAT_LIMITER binding is deployed from wrangler.jsonc. Do not put OPENAI_API_KEY into Cloudflare's public folder or the mobile JavaScript.
6. Deploy the updated mobile repository. Tap Chat, create/sign into a confirmed account, and send a test question such as “How are the paper agents doing?” Verify the answer's reference timestamps, then sign in as a SECOND test user and verify that histories and memories are separate before opening chat to the public.

### Memory and data boundaries

KST Chat retrieves the most recent bounded conversation window, your explicit memories and a few relevant completed turns from other private conversations. It does not have unlimited recall of every message. User memory changes do not retrain the underlying model; the existing statistical trading learner remains a separate component. AI responses cannot save a memory or change a trading agent without an explicit user action and corresponding implemented tool (no such trading tools are exposed here).

Deleting a conversation deletes its saved turns and removes them from future retrieval. Explicit memories are separate and must be edited/deleted through My saved memories. Sign-out clears this tab's session, not your stored history. The website explains that messages, relevant recalled context and KST snapshots are sent to OpenAI for generation. Do not submit broker credentials or API keys to the chatbot.

Market reference data and previous conversations are passed as untrusted evidence, not privileged instructions. The model is instructed to distinguish fresh quotes, stale snapshots, paper results, forecasts and actual fills. This lowers some error risks but does not guarantee correct financial analysis. Source metadata is shown separately; no unrestricted web-search tool, live chart interpretation, attachments, voice mode, streaming tokens, membership billing or autonomous strategy changes are included in this chat build.

### Verification

The existing 27 local tests remain passing. Chat adds six Python logic/privacy tests and two Cloudflare proxy tests (35 total), plus a local HTTP transport smoke check for health, proxy-secret enforcement, safe public config and mandatory sign-in. Static HTML/JavaScript references and syntax/compile checks are verified. No live OpenAI request was made because the reused key is in your Railway account, not this workspace. Live Supabase auth/RLS, SQL quota/search procedures and end-to-end deployment still require verification with your account. The ZIP contains no OpenAI key, chat proxy secret or user passwords.


## Update r2 — guardrails, runners, setup fixes, password reset

Re-run RAILWAY_BACKEND/kst_options/schema.sql in Supabase (additive and rerunnable: new peak_bid column, replaced ledger functions), then redeploy both repositories.

**Paper-agent exit rules (changed).** The fixed +50% profit cap was REMOVED so winning paper trades can run past +100%. Exits are now: observed -30% stop; TRAILING_GIVEBACK (once a position's peak gain reaches +20%, exit if the gain falls to half of the peak gain); or the measurement deadline. Example: peak +100% exits near +50%. Quotes are polled about once a minute, so real peaks and giveback can occur between polls. Past paper outcomes keep their old labels; new outcomes will include larger returns.

**Paper guardrails (new).** Each agent stops opening trades for the New York day once realized losses reach 10% of its starting balance, and waits 15 minutes after any losing exit, on top of the existing 30-minute same-contract cooldown. These are paper-ledger rules in SQL; they do not control your Robinhood account.

**Chat password reset (new).** "Forgot password?" sends a Supabase recovery email; the link returns to the app and prompts for a new password. In Supabase Auth, add your production site URL to the allowed redirect URLs and confirm the recovery email template works. Not tested in a live browser.

**Setup fixes.** .env.example now lists every variable per service; the stray ".env - Copy.example" was removed; pytest moved to requirements-dev.txt; the service-worker cache version was bumped so phones load the new files. The root Procfile still defines the old scanner and Streamlit processes; give each Railway service its own railway-*.json start command. The nested RAILWAY_BACKEND/sql/ folder duplicates older code; do not copy it over newer root files.

**Not verified:** the new SQL has not been executed against Postgres, and nothing was tested live. Verify after deploying: close a test position and confirm TRAILING_GIVEBACK appears, and confirm the loss lock shows WAIT.


## Update r3 — review and deployment checks (November 5, 2026)

Changes:
- Scheduled and requested option selections reserve the configured full round-trip fee inside the selected budget. Decimal arithmetic prevents floating-point cent-boundary errors. Requested result cards now receive the fee estimate and both card types show cost including reserved fees. Existing saved signals retain their historical entry and budget labels.
- A blank NEWS_RSS_URLS now uses the default CNBC feed, matching the supplied environment template. Previously it polled zero feeds and could report OK with zero items.
- Added check_deployment.py for offline, per-service configuration diagnostics. It prints variable names and actionable issues, never environment values. It checks required fields, the project URL, options feed/fee/intervals, public chat auth configuration and proxy-secret length, and push contact configuration.
- Updated the mobile cache version so the changed price labels refresh.

Run from RAILWAY_BACKEND on each configured service:

    python check_deployment.py options
    python check_deployment.py chat
    python check_deployment.py push

Run only the command for that service. Exit 0 means these local configuration checks passed; it does not verify credentials, database schema, data entitlement, billing, VAPID cryptography or live operation. No new SQL migration is introduced in r3; the r2 migrations are still required if not applied.

Review findings and remaining work:
- Live deployments, Supabase migrations/RLS, email recovery, end-to-end push and OpenAI requests were not verified here. The supplied ZIP contains no account configuration that would establish those connections.
- Chat has private retrieval memory, not automatic neural training; the options Brain is a separate bounded ranking learner. Paper portfolios remain separate from broker accounts.
- Older scan requests are handled by the regular scan cycle; only requests from the latest ten minutes trigger an early scan. Normal scans can still take multiple minutes depending on data-provider response times.
- The legacy duplicated code in sql/ and the older integration folder was preserved. Deploy the current RAILWAY_BACKEND root, not the duplicate folder.
- Upcoming earnings, richer market features, execution replay, streaming chat and membership billing still require further implementation and verification. This update does not claim those features are complete.

Validation results are recorded in REVIEW_R3.md at the bundle root.


## Update r4 — chart photos, stock research and private Request 3 accounts

Read RELEASE_R4.md at the bundle root for activation and boundaries. This replaces older statements that chat has no image input and that Request 3 is anonymous-only.

New files require all three migrations, in order:

1. RAILWAY_BACKEND/kst_options/schema.sql (rerunnable; adds risk_snapshot).
2. RAILWAY_BACKEND/kst_options/stocks.sql (new public stock plans, rule alerts and separate push queue).
3. RAILWAY_BACKEND/kst_chat/schema.sql (rerunnable; adds image metadata and personal request archive with atomic queue/ownership recording).

Then update backend dependencies and redeploy options, chat and push services, plus the Cloudflare mobile app. Request 3 now requires a signed-in, confirmed KST account and configured chat backend; it records the private ownership link at queue time, independent of the browser staying open. The archive refreshes pending records from completed scanner results when opened. It shows the most recent 50 requests. A new request-specific signal baseline tracks each suggestion's own ask and timestamp, rather than borrowing an older scheduled contract entry. Queued requests with no eligible contracts are still recorded. Suggestions are not broker holdings or orders.

Chart photos use the previously approved OPENAI_API_KEY on Railway. No new key is included or required by the code. No live API call was made during development. Image analysis requires a vision-capable configured model and project access. New dependency: Pillow>=12,<13.

Stock research defaults: STOCK_RESEARCH_ENABLED=true, STOCK_FEED=iex, STOCK_SYMBOLS=AAPL,MSFT,NVDA,TSLA,AMD,AMZN,META,GOOGL,SOFI,HOOD. Set the same feed deliberately for the SPY proxy; changing from SIP to IEX changes coverage. The stock scanner polls in the existing options worker, approximately once a minute plus other work; it considers at most 40 configured symbols and operates only in the New York weekday 09:30–16:00 clock window with fresh quotes. This is not a full-market scanner, a holiday calendar, or continuous extended-hours monitoring.

For closed-page stock notifications, apply stocks.sql, redeploy the push service, and select Stock research exits under AI P/L → Trade notifications → Enable/update notifications. Existing opt-ins do not gain stock alerts automatically. Current stock subscriptions cover all public stock research exit events, not user-selected tickers or personal holdings.

Validation and remaining work are described in RELEASE_R4.md.


## Update r5 — all requested development areas

Read RELEASE_R5.md and FEATURE_MATRIX_R5.md first. They supersede earlier “still needed” lists for earnings, ticker news, private stock monitors, memberships, streaming/history search, operations and research replay. The new separate execution adapter is OFF by default and does not execute through chat or Robinhood.

Apply kst_pro/schema.sql and kst_pro/execution.sql after the existing r4 migrations, install updated requirements, add the Pro service, and redeploy chat/options/push plus the complete mobile folder. Provider/billing/live-account credentials are not bundled. Each integration needs the account configuration and deployment validation described in RELEASE_R5.md; local test success does not establish live operation.
