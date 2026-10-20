# V3 — NEW EMPTY GITHUB REPOSITORY: START HERE

**This ZIP is a complete standalone repository upload, not a patch.** It includes all available source from the uploaded V2 foundation and the previous independent upgrade. However, it is **not** a completed autonomous AI trading platform: read `FEATURE_STATUS.md` before public release.

## Upload to your EMPTY V3 repository
1. Download this ZIP and **extract** it locally.
2. Open the extracted folder. Select its contents (including `app.py`, `core`, `workers`, `sql`, `.env.example`, and `requirements.txt`), not just the outer folder or zipped archive. Hidden dotfiles may need `show hidden files`.
3. In V3 GitHub: **Add file → Upload files**. Preserve folder paths and **Commit**.
4. Confirm `app.py`, `requirements.txt`, `railway.json`, `core/`, `workers/` appear at repository ROOT.
5. Do NOT modify V2 Railway services, their variables, or V2 GitHub repo.

## Deploy V3 separately
- First deploy only V3 Streamlit dashboard with entrypoint `app.py`.
- For new V3 Supabase project, run `sql/v3_bootstrap.sql`, then `sql/schema.sql`, then `sql/additions.sql`, then `sql/upgrade_paper_research.sql` using Supabase SQL Editor. Tables have RLS enabled; no public policies are created.
- For a shared existing Supabase project, **do not rerun migrations without comparing with existing schema**, and be aware signals will be mixed between V2 and V3 unless you segregate them. Prefer a separate V3 Supabase project.
- Add secrets separately to V3 deployment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `APP_PASSWORD`. Never commit these values. Server-side service role must never be sent to a public browser.
- V3 Railway scanner **new service**: `python -m workers.scan_worker` (also default in railway.json). Only activate after confirming V3 DB.
- V3 news **new service**: `python -m workers.ai_news_worker`; OpenAI API key optional if supported by code.
- Candidate-only simulated agent **new separate service**: `python -m workers.paper_agent_worker`, and only turn on `PAPER_AUTO_ENABLED=true` after SQL migration. It stores candidates, NOT fills.
- To run Streamlit on Railway: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`.
- Do not connect a live broker or add real money. The project contains no verified live-trading execution system.

## Test locally
`python -m compileall -q app.py core workers tests`
`python -m pytest -q tests`
Actual cloud behavior, data access, auth and external APIs require separate validation.

## Folder layout
- `app.py`: main Streamlit V3 dashboard
- `worker.py`: alternate legacy orchestrator entrypoint (not default)
- `core/`: market research, rules, DB, paper candidate logic
- `workers/`: scheduled scanner, news and opt-in paper candidate services
- `sql/`: database migrations
- `tests/`: research unit tests
- `Kenny-Shadow-Trader-Ultimate-V2-integration/`: **ARCHIVED REFERENCE**, not launched by V3
