-- Run AFTER schema.sql. Server credentials are private; no public read policies.
create table if not exists public.notifications(id uuid primary key,created_at timestamptz not null default now(),kind text not null,payload jsonb not null default '{}'::jsonb,status text not null default 'PENDING');
create table if not exists public.signal_outcomes(id uuid primary key default gen_random_uuid(),created_at timestamptz not null default now(),signal_id uuid references public.signals(id),result jsonb not null default '{}'::jsonb);
create table if not exists public.agent_decisions(id uuid primary key default gen_random_uuid(),created_at timestamptz not null default now(),signal_id uuid references public.signals(id),agent text not null,decision jsonb not null default '{}'::jsonb);
create table if not exists public.watchlist_intents(id uuid primary key default gen_random_uuid(),created_at timestamptz not null default now(),symbol text not null,details jsonb not null default '{}'::jsonb,status text not null default 'PENDING');
create table if not exists public.paper_challenges(id uuid primary key default gen_random_uuid(),created_at timestamptz not null default now(),name text not null,initial_equity numeric not null,goal_equity numeric not null,current_equity numeric not null,status text not null default 'ACTIVE');
alter table public.notifications enable row level security;
alter table public.signal_outcomes enable row level security;
alter table public.agent_decisions enable row level security;
alter table public.watchlist_intents enable row level security;
alter table public.paper_challenges enable row level security;
