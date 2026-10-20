# V3 execution integration status

This development package does NOT place any real-money trades. The new automatic paper worker is intentionally disabled by default and does not yet have a trusted live contract premium quote ingestion callback.

## Included and tested
- Five research profiles with separate database account rows and hard stop settings (default killed=true).
- Quote checks that reject absent, stale or underlying-only option premium data.
- Simulated open-trade records with database uniqueness for each agent, signal and contract.
- A read-only opportunity retrieval worker, a research paper emergency-stop control in the password-protected Streamlit dashboard, and a paper broker adapter.

## Still required before unattended paper execution
1. Apply `sql/v3_execution_research.sql` to your dedicated V3 Supabase project, inspect permissions and keep the service role key server-only.
2. Build and test Alpaca real-time options quote ingestion; validate OCC contract metadata, ask/bid quote timestamps, market hours and option-premium stops and targets. Never reuse underlying stop/target prices.
3. Add an atomic Supabase stored procedure to reserve paper buying power, update open exposure and acquire a worker lock; enforce per-agent exposure and daily loss across worker restarts. Current row insert is not sufficient for concurrency.
4. Add persistent bid-priced exits, expiry, partial fills/fees, and full mark-to-market accounting to simulated positions.
5. Integrate Alpaca paper broker polling/reconciliation, including status transitions, order replacements, cancel retries, and restart recovery; keep this separate from the offline simulation ledger.
6. Add idempotent alert delivery with per-user access control and a secure dashboard authentication system (a shared password is not sufficient for a public platform).
7. Build Robinhood watchlist workflow only with supported authorized API access; do not automate undocumented endpoints or assume stock/options order permissions.
8. Only after paper validation, design a separate live broker integration with explicit authorization, account designation, independent risk limits, kill switch and end-to-end tests.

## Activation defaults
- `V3_PAPER_AUTOMATION_ENABLED=false` (do not enable until ingestion/reservations/exit lifecycle above are finished).
- `ALPACA_PAPER_EXECUTION_ENABLED=false` (independently gated).
- Never put brokerage API keys or Supabase service role keys in the public repo.
- Keep V2 independent. V3 is a development ZIP, not yet a verified Railway deployment.
