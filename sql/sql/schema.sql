-- Run in Supabase SQL editor. Keep service-role credentials server-side only.
create extension if not exists pgcrypto;
create table if not exists public.signals (id uuid primary key default gen_random_uuid(),created_at timestamptz not null default now(), symbol text not null,status text not null,side text,entry double precision,stop double precision,target double precision,details jsonb not null default '{}'::jsonb,source text,execution_state text not null default 'NONE');
create index if not exists signals_created_idx on public.signals(created_at desc);
create table if not exists public.news_articles (article_hash text primary key,symbol text,headline text not null,summary text,url text,published_at timestamptz,created_at timestamptz not null default now());
create table if not exists public.news_analysis (id uuid primary key default gen_random_uuid(),article_hash text references public.news_articles(article_hash),model text,analysis jsonb not null,created_at timestamptz not null default now());
create table if not exists public.paper_trades (id uuid primary key,created_at timestamptz not null default now(),closed_at timestamptz,symbol text not null,asset_class text not null,side text not null,qty numeric not null,entry double precision not null,stop double precision not null,target double precision not null,exit_price double precision,pnl double precision,status text not null,agent text,simulation_only boolean not null default true);
-- No anonymous writes or reads. Dashboard works server side with a secret service-role key.
alter table public.signals enable row level security;
alter table public.news_articles enable row level security;
alter table public.news_analysis enable row level security;
alter table public.paper_trades enable row level security;
