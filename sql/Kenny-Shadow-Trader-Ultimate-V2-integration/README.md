# Kenny Shadow Trader V2 — replacement research foundation

**Current status: FUNCTIONAL FOUNDATION / NOT COMPLETE ULTIMATE SYSTEM**.

Runs a Streamlit interface with 8 requested market tabs plus watchlists, manually logged paper journal, SQLite research history, yfinance price retrieval, 4H/1H/5M alignment, support/resistance, conservative research risk gate and optional hourly GitHub Actions console scan. No execution of live orders.

**Not yet implemented:** broker-integrated paper/autonomous execution, Supabase synchronization, true whole-market universe, verified options contracts/chain/Greeks, market/news/social/SEC catalysts, payment membership, historical strategy trainer, agentic challenges, rich sentiment feeds, durable shared cloud database, winners/losers validation, commercial-grade uptime, or verified signal outcomes. UI tabs are not substitutes for these services.

## Start locally
`pip install -r requirements.txt` then `streamlit run app.py`; run `pytest`.

## Cloud deployment
Point Streamlit Cloud at `app.py` on your test branch. GitHub Action prints output in job logs; it does not populate the Streamlit site's SQLite database. SQLite on Streamlit Cloud is not durable, and separate GitHub Actions runner files do not sync with it. Set up vetted persistent storage before expecting long-term history.

## Important
Source yfinance is limited/possibly delayed, not a trading-quality feed. No credentials required for this basic foundation. Keep Alpaca, Supabase and payment secrets in their respective secret manager, not in source control. No live trading endpoints are present.
