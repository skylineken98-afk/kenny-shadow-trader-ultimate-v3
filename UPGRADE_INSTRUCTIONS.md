# Kenny Shadow Trader Ultimate V2 — Separate safe upgrade

## Upload strategy
1. Save the original uploaded ZIP as a backup. **Do not delete the currently working scanner or project.**
2. Upload this upgrade ZIP's contents to a **new GitHub repo or an isolated test branch**, keeping the root files at root (not nested twice).
3. Original Railway scanner: leave running with its current secrets and start command. This ZIP preserves `worker.py`, `workers/scan_worker.py`, `workers/runner.py`, and `railway.json` unchanged.
4. Add the *new* additive `sql/upgrade_paper_research.sql` via Supabase SQL Editor only when ready; do not rerun old schema files blindly.
5. In a **separate Railway service**, set start command `python -m workers.paper_agent_worker`, set `PAPER_AUTO_ENABLED=false` initially, and use the same server-side Supabase variables. Run `RUN_ONCE=1` for first smoke test.
6. Once permissions and tests pass, change PAPER_AUTO_ENABLED to true on the **paper service only**. It records deterministic **research candidate events**, not executed positions or orders. No chance of sending real broker orders in this service.
7. Deploy/test the Streamlit web service separately (`streamlit run app.py --server.address 0.0.0.0 --server.port $PORT` on Railway; Streamlit Community Cloud expects `app.py` directly). `APP_PASSWORD` is a shared beta gate only, *not multi-user production auth*.
8. Confirm Dashboard > Latest tracked signals reads **ultimate_signals**. Keep service_role key on trusted back-end only. A publicly accessible dashboard must migrate to proper authentication and restricted views before public beta launch.
9. Run `python -m compileall -q .` and `pytest -q`. External integrations need separate credential-backed smoke tests; those are not verified by offline unit tests.

## Known existing configuration conflict
`railway.json` runs `python worker.py`, which does exist. Existing README inaccurately says worker.py does not exist. Prefer leaving the working Railway service unchanged. When testing new services, always explicitly set start command and root directory.

## Separation/limitations
This upgrade is additive, safe and functional for research scaffolding. It does **not** claim to implement every previously requested advanced feature. `FEATURE_STATUS.md` names all missing modules and account integrations. This avoids another misleading promise of a finished system.

## Data contract
`ultimate_signals` contains scanner research events, `paper_agent_events` contains *candidate-only decisions*. `paper_agent_positions` is reserved for independently validated simulated fill/exits; this new worker intentionally does not populate it. No automated real orders.
