-- KST V3 additive migration. Preserves public.ultimate_signals and all existing rows.
-- Run as project owner in Supabase SQL Editor. Never place a service-role key in browser code.
BEGIN;

CREATE TABLE IF NOT EXISTS public.v3_paper_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile text NOT NULL CHECK (profile IN ('conservative','balanced','aggressive','challenge','daily_10pct_research')),
  account_label text NOT NULL,
  initial_equity numeric(20,6) NOT NULL CHECK (initial_equity > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (profile, account_label)
);

CREATE TABLE IF NOT EXISTS public.v3_paper_trades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id uuid REFERENCES public.ultimate_signals(id) ON DELETE RESTRICT,
  account_id uuid NOT NULL REFERENCES public.v3_paper_accounts(id) ON DELETE RESTRICT,
  asset_class text NOT NULL CHECK(asset_class IN ('stock','option','crypto','forex','future')),
  instrument text NOT NULL,
  side text NOT NULL CHECK(side IN ('LONG','SHORT')),
  state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','OPEN','CLOSED','CANCELED','REJECTED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  opened_at timestamptz,
  closed_at timestamptz,
  model_version text,
  market_regime text,
  source text NOT NULL DEFAULT 'paper',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT v3_paper_trade_dates CHECK (closed_at IS NULL OR (opened_at IS NOT NULL AND closed_at >= opened_at)),
  CONSTRAINT v3_paper_trade_close_state CHECK (state <> 'CLOSED' OR closed_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS public.v3_paper_fills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_id uuid NOT NULL REFERENCES public.v3_paper_trades(id) ON DELETE RESTRICT,
  filled_at timestamptz NOT NULL,
  action text NOT NULL CHECK (action IN ('ENTRY','EXIT')),
  quantity numeric(20,8) NOT NULL CHECK (quantity > 0),
  price numeric(20,8) NOT NULL CHECK (price > 0),
  multiplier numeric(20,8) NOT NULL DEFAULT 1 CHECK (multiplier > 0),
  fee numeric(20,8) NOT NULL DEFAULT 0 CHECK (fee >= 0),
  slippage numeric(20,8) NOT NULL DEFAULT 0 CHECK (slippage >= 0),
  source_event_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(trade_id,source_event_id)
);

CREATE TABLE IF NOT EXISTS public.v3_paper_outcomes (
  trade_id uuid PRIMARY KEY REFERENCES public.v3_paper_trades(id) ON DELETE RESTRICT,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  realized_pnl numeric(20,8) NOT NULL,
  realized_return_pct numeric(16,6),
  total_fees numeric(20,8) NOT NULL DEFAULT 0 CHECK(total_fees>=0),
  calculation_version text NOT NULL,
  inputs_verified boolean NOT NULL DEFAULT false,
  notes text,
  CONSTRAINT v3_return_finite CHECK(realized_return_pct IS NULL OR realized_return_pct BETWEEN -1000000 AND 1000000)
);

CREATE TABLE IF NOT EXISTS public.v3_ai_model_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_name text NOT NULL,
  version text NOT NULL,
  role text NOT NULL DEFAULT 'challenger' CHECK (role IN ('champion','challenger','retired')),
  created_at timestamptz NOT NULL DEFAULT now(),
  training_cutoff timestamptz,
  code_ref text,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  evaluation jsonb NOT NULL DEFAULT '{}'::jsonb,
  live_approved boolean NOT NULL DEFAULT false,
  UNIQUE(model_name, version)
);

CREATE TABLE IF NOT EXISTS public.v3_ai_evaluations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id uuid NOT NULL REFERENCES public.v3_ai_model_versions(id) ON DELETE RESTRICT,
  signal_id uuid REFERENCES public.ultimate_signals(id) ON DELETE RESTRICT,
  trade_id uuid REFERENCES public.v3_paper_trades(id) ON DELETE RESTRICT,
  evaluated_at timestamptz NOT NULL DEFAULT now(),
  asof_timestamp timestamptz NOT NULL,
  evaluation_kind text NOT NULL CHECK(evaluation_kind IN ('backtest','walk_forward','forward_paper')),
  eligible boolean NOT NULL DEFAULT false,
  metric_set jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (trade_id IS NOT NULL OR signal_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS public.v3_ai_adaptations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposed_at timestamptz NOT NULL DEFAULT now(),
  champion_id uuid REFERENCES public.v3_ai_model_versions(id) ON DELETE RESTRICT,
  challenger_id uuid NOT NULL REFERENCES public.v3_ai_model_versions(id) ON DELETE RESTRICT,
  decision text NOT NULL DEFAULT 'PROPOSED' CHECK(decision IN ('PROPOSED','REJECTED','PAPER_APPROVED')),
  reason text NOT NULL,
  validation jsonb NOT NULL DEFAULT '{}'::jsonb,
  decided_at timestamptz,
  CHECK (champion_id IS DISTINCT FROM challenger_id)
);

CREATE INDEX IF NOT EXISTS v3_paper_trades_account_state_idx ON public.v3_paper_trades(account_id,state,created_at DESC);
CREATE INDEX IF NOT EXISTS v3_paper_trades_signal_idx ON public.v3_paper_trades(signal_id);
CREATE INDEX IF NOT EXISTS v3_paper_fills_trade_time_idx ON public.v3_paper_fills(trade_id,filled_at);
CREATE INDEX IF NOT EXISTS v3_ai_evals_model_date_idx ON public.v3_ai_evaluations(model_id,asof_timestamp DESC);

-- Fail-closed: browser clients get no access. Server-side service role bypasses RLS.
ALTER TABLE public.v3_paper_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_paper_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_paper_fills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_paper_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_ai_model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_ai_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_ai_adaptations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.v3_paper_accounts,public.v3_paper_trades,public.v3_paper_fills,public.v3_paper_outcomes,public.v3_ai_model_versions,public.v3_ai_evaluations,public.v3_ai_adaptations FROM anon,authenticated;
COMMIT;
