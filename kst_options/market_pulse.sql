-- Apply manually after reviewing existing Supabase migrations.
-- Service-role-only latest measured stock/sector leaderboards.
create table if not exists public.kst_market_pulse (
 id text primary key check (id='latest'),
 observed_at timestamptz not null,
 payload jsonb not null
);
alter table public.kst_market_pulse enable row level security;
revoke all on public.kst_market_pulse from anon,authenticated;
grant select,insert,update on public.kst_market_pulse to service_role;
-- Client reads must go through authenticated, entitlement-checked server routes.

-- Sampled options strike-volume ranking. Never anonymous access.
create table if not exists public.kst_options_strike_activity (
 id text primary key check(id='latest'),
 observed_at timestamptz not null,
 payload jsonb not null
);
alter table public.kst_options_strike_activity enable row level security;
revoke all on public.kst_options_strike_activity from anon,authenticated;
grant select,insert,update on public.kst_options_strike_activity to service_role;
