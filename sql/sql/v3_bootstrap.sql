-- V3 ONLY: execute in V3 Supabase project if setting up a separate DB.
-- Non-destructive create-if-absent; do NOT execute blindly against an unrelated project.
create extension if not exists pgcrypto;
create table if not exists public.ultimate_signals (
 id uuid primary key default gen_random_uuid(),
 created_at timestamptz not null default now(),
 symbol text not null, status text not null, side text,
 entry double precision, stop double precision, target double precision,
 details jsonb not null default '{}'::jsonb, source text,
 execution_state text not null default 'NONE'
);
create index if not exists ultimate_signals_created_at_desc_idx on public.ultimate_signals(created_at desc);
alter table public.ultimate_signals enable row level security;
grant usage on schema public to service_role;
grant select, insert, update, delete on public.ultimate_signals to service_role;
-- The other schemas are in schema.sql, additions.sql and upgrade_paper_research.sql.
