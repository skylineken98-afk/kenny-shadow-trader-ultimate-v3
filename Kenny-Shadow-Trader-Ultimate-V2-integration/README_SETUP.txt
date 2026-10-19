KENNY SHADOW TRADER V2 — ULTIMATE SYSTEM SETUP & MIGRATION GUIDE
Version: 2026-10-15

PURPOSE
This file is the setup checklist for replacing the existing V2 repository with the new full system. It is NOT the executable scanner and does not by itself install features. Follow the actual new system file manifest when it is delivered. Do not assume that every requested feature is implemented merely because it is listed here.

SAFETY FIRST — BEFORE DELETING ANYTHING
1. Back up the entire current repository as a ZIP from GitHub (repository > Code > Download ZIP in the browser), or create a separate backup branch/repository. Verify that the ZIP contains app.py, market_engine.py, hourly_top10.py, requirements.txt, .github/workflows, and any other existing files.
2. Save the current Streamlit Cloud app URL, deployment settings, branch, and main module. Do NOT copy or share credential values in screenshots, chat, code, or a ZIP intended for sharing.
3. Make a list of all current GitHub Actions secret NAMES and Streamlit secret NAMES. Existing GitHub repository secrets normally remain when code files are replaced in the same repository. Verify them; never delete or expose credentials during migration. Rotate any secret accidentally committed.
4. Keep the current deployed app working while testing. Prefer a new branch (e.g. ultimate-v2-test) or a separate test repository before changing main. Deleting the existing code first can break deployment.

CURRENT FILES SEEN IN REPOSITORY SCREENSHOT
.devcontainer/
.github/
README.md
alpaca_connection_test.py
app.py
hourly_requirements.txt
hourly_top10.py
market_engine.py
requirements.txt
The previously deleted README_SETUP.txt is only documentation. Other folders such as pages/ and specific workflows must still be checked.

MIGRATION — USE THIS ORDER
1. Download and verify the complete new system package and its file list. If the new package is not complete yet, STOP: do not delete your current app.
2. Make a backup and test branch. Preserve .github workflows and configuration until you confirm their replacements exist.
3. Upload replacement files with their exact directory paths. GitHub folder structure matters: .github/workflows/ and pages/ are directories, not file prefixes to discard.
4. Replace or remove old files ONLY after comparing them to the new package's manifest. Keep README_SETUP.txt as documentation.
5. Update requirements.txt with the actual packages used by the uploaded code. If an hourly job has separate dependencies, ensure its workflow installs hourly_requirements.txt or the appropriate shared requirements.
6. Keep existing credentials in secret managers. Add only newly needed secret NAMES and values through GitHub Settings > Secrets and variables > Actions and Streamlit Cloud app settings > Secrets. Never put credentials directly in Python, YAML, README or commits.
7. Test in a non-production branch/deployment. Ensure imports and app startup pass, and scheduled workflows actually run. Fix errors before switching the live deployment to new code.
8. After testing, merge the new branch into main or point Streamlit Cloud at the tested branch. Verify app health and workflows; keep the backup for rollback.

SECRETS / INTEGRATIONS CHECKLIST (ONLY IF USED BY THE ACTUAL CODE)
Alpaca: ALPACA_API_KEY, ALPACA_API_SECRET (naming must match the code); prefer paper endpoint for testing. Some implementations may use ALPACA_KEY_ID / ALPACA_SECRET_KEY instead: choose what code expects rather than duplicating blindly.
Supabase: SUPABASE_URL and a server-side key as required by code. If using SUPABASE_SERVICE_ROLE_KEY, it must NEVER be exposed to a public Streamlit client, browser, published repo, or untrusted logs. Apply row-level security, least privilege, and appropriate authentication. Public anon/publishable keys differ from service-role keys.
Market-data/news/AI/payment providers: Add credentials only after choosing providers, their code adapters, rate limits, and licensing. An unavailable provider must show a clear data-unavailable state rather than fabricated signals.
GitHub Actions: make secrets available only to workflows that need them; set minimal permissions. Streamlit Cloud secrets and GitHub Actions secrets are separate stores; configuring one does not populate the other.

FEATURE ACCEPTANCE CHECKLIST — VERIFY IN CODE, NOT JUST THE MENU
[ ] Main Streamlit application starts and has navigation: 0DTE, Swings, LEAPS, Stocks, Crypto, Forex, Request a Signal, Market Sentiment.
[ ] 4H + 1H + 5M trend confluence required; 5M alone never authorizes a trade.
[ ] Candlestick charts and independently searchable support/resistance, structure, entries, stops and targets.
[ ] Daily Top 5 watchlist and hourly Top 10 candidates/contracts, with actual scheduled scans.
[ ] Options: contract symbol, side, strike, expiry, quotes, bid/ask spread, volume, open interest, Greeks as available; liquidity checks and premium-based performance.
[ ] Persistent signals database tracks proposed, triggered, untriggered, closed, winners, and losers; distinguish real/simulated fills and touches.
[ ] Winners Club uses verified 30%+ premium returns, not underlying movement alone.
[ ] News/catalysts, SEC/company events, macro calendar, timestamps, source quality, and stale-data safeguards.
[ ] Paper trading and historical backtesting with realistic fees, slippage, market hours, no look-ahead bias, and full audit records.
[ ] Multiple independent challenge agents and 1-year 10%-daily-growth experiment, clearly marked as high-risk simulation with no promised returns.
[ ] Market sentiment, crypto 24/7 monitoring and separate risk model, forex analytics.
[ ] Champion/challenger model evaluation; no unrestricted self-modifying live code.
[ ] User controls for signal budget, paper/live mode, membership, and authorized access.
[ ] Broker order integration, if implemented, remains DISABLED in live mode until explicitly enabled after paper validation; include broker reconciliation, max position loss, daily loss cap, kill switch, outages, and duplicate-order prevention.
[ ] Membership/payment setup uses a vetted provider and secure webhook verification; never store raw card data.
[ ] Failure alerts, scan timestamps, data provenance, monitoring and restart/rollback paths.

GITHUB ACTIONS CHECKS
- Inspect .github/workflows/ for the actual hourly scanning workflow (often hourly_top10.yml) and any other workflows.
- Confirm the cron schedule and that the workflow is enabled. GitHub Actions schedules are best-effort and can be delayed; do not assume exact hourly execution.
- Ensure workflows use the correct branch, Python version, install commands, filenames and secrets.
- Manually run a workflow where workflow_dispatch is provided; inspect logs for real completion and Supabase inserts.
- Scheduled jobs should not depend on a laptop staying on. Streamlit page views alone are not a reliable background scheduler.

SUPABASE / STORAGE CHECKS
- Apply versioned SQL migrations (tables, indexes, policies) delivered with the actual system, not guessed schemas.
- Verify the app can read only authorized records and write through server-side code without leaking elevated keys.
- Validate retention, backups, idempotent inserts, timestamp/timezone handling and reconnect behavior.

TESTS BEFORE LAUNCH
1. App boots, imports succeed, sidebar tabs render, secret-missing messages are helpful.
2. Historical and live data indicate source and as-of time; stale feeds block new orders.
3. Scheduled hourly scan runs at least once successfully; expected records appear in database.
4. Paper trading records order requests, fills, rejections, fees and daily P/L.
5. No duplicate orders on retries/restarts; kill switch prevents trade placement.
6. Clear fail-closed behavior when Alpaca, Supabase, market data or news sources are down.
7. Check mobile view and public/private permissions; never expose private tokens.
8. Deploy only after tests pass. Roll back using saved ZIP/branch or prior known-good commit if needed.

IMPORTANT LIMITATIONS
- A setup file cannot prove or activate unimplemented features. Every module and integration must exist in delivered source files and be tested.
- Free market data often has limited coverage, delay and rate limits. Whole-market hourly full options scanning and reliable news feeds may require paid services.
- Backtesting and paper profits do not guarantee future returns. Automated live trading is high risk. Keep execution disabled until independently validated and explicitly authorized.

RECOVERY
If changes break the project, restore the previous known-good commit or switch Streamlit back to the backup branch. Do not erase git history. The prior README_SETUP.txt described an hourly scanner and is recoverable from the deletion commit if ever needed.
