-- Explicit opt-in personal research journal. Apply manually after security review.
-- Service-role only: must never be exposed by an unauthenticated public dashboard.
create table if not exists public.kst_personal_trade_research (
  owner_id uuid not null,
  trade_id text not null check(length(trade_id)=64),
  research_record jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(owner_id, trade_id)
);
create index if not exists kst_personal_trade_research_created
  on public.kst_personal_trade_research(owner_id,created_at desc);
alter table public.kst_personal_trade_research enable row level security;
revoke all on public.kst_personal_trade_research from anon, authenticated;
grant select, insert, update on public.kst_personal_trade_research to service_role;
-- Owner authorization must occur in the backend before service-role use.
-- Deletion and user consent withdrawal require an audited admin workflow.
