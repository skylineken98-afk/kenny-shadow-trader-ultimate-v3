# ONE-PASS DEPLOY GUIDE

1. Extract the ZIP. Open the inner `kenny-shadow-trader-ultimate-v2` directory and upload **its contents**, preserving `workers/`, `core/`, and `sql/`, to the Ultimate repository root (not nested inside another folder). Verify `worker.py` is visible at the GitHub root.
2. In Supabase SQL Editor run `sql/schema.sql`, then `sql/additions.sql`.
3. In Railway connect to **the Ultimate repository** on `main`, Root Directory `/` (blank is also acceptable when using repo root); set Start Command `python worker.py` and `WORKER_ROLE=orchestrator`.
4. Set server secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optionally `OPENAI_API_KEY`, `SCAN_SYMBOLS`, and `WORKER_INTERVAL_SECONDS=3600`. Keep the service-role key PRIVATE. Do not store it in GitHub.
5. Deploy. The logs should show `Ultimate V2 starting role=orchestrator`. If import fails, verify `worker.py`, `workers/__init__.py`, and `core/__init__.py` are in GitHub root layout; avoid a nested ZIP root.
6. Deploy Streamlit separately using `app.py`, same private credentials.
7. Verify rows appear in `signals` and `news_analysis` as appropriate. Lack of news source data means news processing may produce zero rows. Never interpret startup as verification of data or profitability.

## Caveats
- Live trading is **hard disabled**. No deposits or orders are made.
- Stock/crypto/forex/futures paper mechanics are simplistic; this is not broker grade fill simulation. Options contract research is NOT an options execution engine.
- News ingestion, Stripe membership billing, Dark Pool vendor access, webhook delivery and Robinhood watchlist write require credentials, licensing, and custom integrations, and are NOT operational by default.
- Rule-based agents are research variants, not proven continuously self-learning models.
- Do not upload `.env` or credentials.
