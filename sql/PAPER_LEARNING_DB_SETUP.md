# V3 paper-learning database migration

1. Backup your Supabase database. In Supabase SQL Editor, paste `sql/v3_paper_learning.sql` and click Run once. This **adds** tables and indexes; it does not change `ultimate_signals`.
2. Check Table Editor for seven new tables: `v3_paper_accounts`, `v3_paper_trades`, `v3_paper_fills`, `v3_paper_outcomes`, `v3_ai_model_versions`, `v3_ai_evaluations`, `v3_ai_adaptations`.
3. Do not turn on public RLS access. These tables are for server-side research processes only, and must not use your service-role key in public Streamlit client views.
4. Schema creation alone **does not record paper fills or train a model**. The worker still needs fill reconciliation, realized-P&L calculation (including multipliers and fees), event deduplication, and controlled writing to these tables.
5. Preserve the old `ultimate_signals` records. They are candidate research events, **not** proof of executed or profitable trades.
6. Do not enable live brokerage execution from this migration. No live-trading model promotion is supported by these tables.
