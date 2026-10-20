-- Additive and research-only; run after schema migrations. Never exposes records to public clients.
create extension if not exists pgcrypto;
create table if not exists public.v3_paper_accounts (
 agent text primary key check(agent in ('conservative','balanced','aggressive','challenge','daily_10pct_research')),
 starting_equity numeric not null check(starting_equity>0),
 equity numeric not null check(equity>=0), day_start_equity numeric not null check(day_start_equity>=0),
 killed boolean not null default true,
 updated_at timestamptz not null default now()
);
create table if not exists public.v3_paper_orders (
 id uuid primary key default gen_random_uuid(),
 source_signal_id text not null, agent text not null references public.v3_paper_accounts(agent),
 symbol text not null, asset text not null check(asset in ('stock','call','put')),
 direction text not null check(direction in ('BULLISH','BEARISH')),
 state text not null check(state in ('PROPOSED','SIMULATED_OPEN','CLOSED','REJECTED','CANCELLED')),
 detail jsonb not null default '{}'::jsonb,
 simulation_only boolean not null default true check(simulation_only),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(agent,source_signal_id,symbol)
);
create index if not exists v3_paper_orders_agent_state on public.v3_paper_orders(agent,state);
create table if not exists public.v3_paper_audit (
 id bigint generated always as identity primary key, order_id uuid references public.v3_paper_orders(id),
 agent text, event text not null, detail jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
alter table public.v3_paper_accounts enable row level security;
alter table public.v3_paper_orders enable row level security;
alter table public.v3_paper_audit enable row level security;
revoke all on public.v3_paper_accounts,public.v3_paper_orders,public.v3_paper_audit from anon,authenticated;
grant select,insert,update on public.v3_paper_accounts,public.v3_paper_orders to service_role;
grant select,insert on public.v3_paper_audit to service_role;
grant usage,select on all sequences in schema public to service_role;
-- Initialize agents explicitly with killed=true; don't auto-start workers.
insert into public.v3_paper_accounts(agent,starting_equity,equity,day_start_equity,killed)
values ('conservative',10000,10000,10000,true),('balanced',10000,10000,10000,true),
('aggressive',10000,10000,10000,true),('challenge',10000,10000,10000,true),
('daily_10pct_research',10000,10000,10000,true)
on conflict (agent) do nothing;
