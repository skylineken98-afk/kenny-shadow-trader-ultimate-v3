set lock_timeout = '5s';
create table if not exists public.kst_collection_status (
 id text primary key, interval_seconds integer not null default 300 check(interval_seconds>0),
 status text not null, last_attempt_at timestamptz, last_finished_at timestamptz,
 last_success_at timestamptz, data_as_of timestamptz, rows_saved integer,
 consecutive_failures integer not null default 0, message text);
create table if not exists public.kst_historical_bars (
 id text primary key, symbol text not null,timeframe text not null,bar_at timestamptz not null,
 open double precision not null,high double precision not null,low double precision not null,
 close double precision not null,volume double precision not null,source text not null,observed_at timestamptz not null,
 unique(symbol,timeframe,bar_at));
create table if not exists public.kst_historical_trendlines (
 id text primary key,symbol text not null,timeframe text not null,kind text not null,
 anchor_a_at timestamptz not null,anchor_a_price double precision not null,
 anchor_b_at timestamptz not null,anchor_b_price double precision not null,
 identified_bar_at timestamptz not null,first_observed_at timestamptz not null,method text not null,source text not null,details jsonb not null);
create table if not exists public.kst_trendline_events (
 id text primary key,line_id text not null references public.kst_historical_trendlines(id),
 symbol text not null,timeframe text not null,bar_at timestamptz not null,observed_at timestamptz not null,
 event text not null,level double precision not null,close double precision not null,volume double precision not null,details jsonb not null);
alter table public.kst_collection_status enable row level security;
alter table public.kst_historical_bars enable row level security;
alter table public.kst_historical_trendlines enable row level security;
alter table public.kst_trendline_events enable row level security;
revoke all on public.kst_collection_status,public.kst_historical_bars,public.kst_historical_trendlines,public.kst_trendline_events from anon,authenticated;
grant all on public.kst_collection_status,public.kst_historical_bars,public.kst_historical_trendlines,public.kst_trendline_events to service_role;
create index if not exists kst_history_symbol_frame_at on public.kst_historical_bars(symbol,timeframe,bar_at desc);
create index if not exists kst_trendline_symbol_frame on public.kst_historical_trendlines(symbol,timeframe,identified_bar_at desc);
create index if not exists kst_trendline_event_symbol_at on public.kst_trendline_events(symbol,bar_at desc);
create index if not exists kst_trendline_events_line on public.kst_trendline_events(line_id);
create index if not exists kst_ultimate_symbol_created on public.ultimate_signals(symbol,created_at desc);
create index if not exists kst_options_state_feed_created on public.kst_option_signals(state,feed,created_at,id);
create index if not exists kst_memory_created on public.kst_market_memory(created_at desc);
create index if not exists kst_research_created on public.kst_research_samples(created_at desc);
notify pgrst, 'reload schema';
