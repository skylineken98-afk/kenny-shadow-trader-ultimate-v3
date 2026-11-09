-- Manual application required; service-role backend inserts only.
CREATE TABLE IF NOT EXISTS public.kst_nq_alerts (
  signal_id text PRIMARY KEY,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.kst_nq_alerts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.kst_nq_alerts FROM anon, authenticated;
CREATE INDEX IF NOT EXISTS kst_nq_alerts_created_idx ON public.kst_nq_alerts(created_at DESC);
-- Add user-scoped SELECT policies in the website integration after
-- establishing intended access; do not expose backend service-role credentials.
