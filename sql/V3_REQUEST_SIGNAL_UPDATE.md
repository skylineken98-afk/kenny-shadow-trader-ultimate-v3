# V3 Request a Signal — Top 3 per options category

This is a complete **V3 repository ZIP** to upload to the **separate V3 GitHub repo**. It does not alter V2 or automatically deploy anything.

## User-facing feature
- Open V3 Streamlit dashboard `app.py` → **Request a Signal**.
- Enter a comma-separated set of underlyings (default SPY, QQQ, IWM, TSLA, NVDA, AAPL, MSFT), budget $30–$3,000 (max ask cost for one standard 100-share option contract), and click **Request Top 3**.
- The program researches **0DTE** (today in America/New_York), **Swings** (2–60 calendar DTE), and **LEAPS** (365+ calendar DTE) **independently**, returning at most 3 ranked vendor-reported contracts per category.
- A **V1-inspired quote card** displays OCC-like option ticker, expiration, strike, call/put, last premium and change when supplied, bid, ask, approximate ask cost, volume, open interest, and a transparent *liquidity/fit score*, NOT win probability.
- If no actual eligible option chain rows are returned, it displays an empty-state. **No fabricated signals and no 3-per-category guarantee.**
- The scanner requires `confluence()` status SETUP and aligned 4H/1H/5M direction; call for bullish and put for bearish. It excludes zero or crossed quotes, option contracts over budget, spread above 20%, OI under 50, volume under 5, or last-trade timestamp outside the configured allowance.
- Data source: `yfinance` option chain. Vendor quotes may be delayed, inaccurate, limited, or rate-limited. **Last-trade timestamp is NOT bid/ask quote timestamp.** Cards warn about this; no claim of real-time execution suitability.
- It does not calculate credible option-contract premium entries, stops, targets, or actual paper fills, and does not place live orders.

## Deploy and testing
1. Backup V3 before updating; preserve V2 repository and Railway project.
2. Extract this ZIP and upload its **contents** into your separate V3 GitHub repo root, replacing duplicate paths. Preserve folder structure (`core/`, `tests/`, `workers/`).
3. Streamlit Cloud V3 should point to `main` / `app.py`; redeploy or reboot V3 only.
4. Do not copy secret values into GitHub. Configure your private V3 Streamlit secrets independently. Rotate previously exposed secrets/passwords. Prefer dedicated V3 Supabase project and never give service-role key to web clients.
5. Run `python -m pytest -q tests/test_request_signals.py` or all root tests.
6. Open **Request a Signal**. Vendor service and live quote validation must still be checked on your deployed V3 app.

## Remaining limitations
Even with real vendor-reported contracts, quote accuracy, exchange data entitlements, and executable trading functionality are **not verified**. No self-training, broker trade execution, dark-pool data, or paid authentication is added in this specific upgrade. Do not promote it as a fully autonomous live trading platform.
