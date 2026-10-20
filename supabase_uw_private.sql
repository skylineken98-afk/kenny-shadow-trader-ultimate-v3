-- Execute manually ONLY after reviewing vendor retention/storage terms.
-- Service-role server-only writes. No client/public access policies are granted.
create table if not exists public.uw_private_research_snapshots (
  id text primary key,
  ticker text not null,
  observed_at timestamptz not null,
  source_names jsonb not null,
  payload jsonb not null,
  access_scope text not null default 'private_research',
  created_at timestamptz not null default now()
);
alter table public.uw_private_research_snapshots enable row level security;
revoke all on public.uw_private_research_snapshots from anon, authenticated;
create index if not exists uw_private_research_ticker_time
 on public.uw_private_research_snapshots (ticker,observed_at desc);
