-- Additive migration only; does NOT touch existing ultimate_signals or deployed workers.
create extension if not exists pgcrypto;
create table if not exists public.paper_agent_events (
  id uuid primary key, created_at timestamptz not null default now(),
  source_signal_id uuid, symbol text not null, agent text not null,
  status text not null check(status in ('CANDIDATE_ONLY')),
  detail jsonb not null default '{}'::jsonb
);
create index if not exists paper_agent_events_created_idx on public.paper_agent_events(created_at desc);
create table if not exists public.paper_agent_positions (
  id uuid primary key default gen_random_uuid(), created_at timestamptz not null default now(),
  source_event_id uuid references public.paper_agent_events(id), symbol text not null,
  agent text not null, qty numeric not null, entry numeric not null, stop numeric not null,
  target numeric not null, exit_price numeric, realized_pnl numeric,
  status text not null check(status in ('SIMULATED_OPEN','CLOSED','CANCELLED')),
  simulation_only boolean not null default true check(simulation_only)
);
create index if not exists paper_agent_positions_created_idx on public.paper_agent_positions(created_at desc);
alter table public.paper_agent_events enable row level security;
alter table public.paper_agent_positions enable row level security;
grant usage on schema public to service_role;
grant select, insert, update on public.paper_agent_events, public.paper_agent_positions to service_role;
-- No anon/authenticated policies added. Do not expose service credentials to web users.
