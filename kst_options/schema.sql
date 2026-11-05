-- Additive KST options research tables. Run once in the SAME Supabase project as Railway.
-- Existing ultimate_signals and its policies are not changed.
create table if not exists public.kst_option_signals (
 id uuid primary key, created_at timestamptz not null, batch_id uuid not null,
 contract text not null, underlying text not null, expiration date not null,
 option_type text not null, strike double precision not null, category text not null,
 budget double precision not null, fee_estimate double precision not null default 0, entry_ask double precision not null check(entry_ask>0),
 entry_bid double precision not null, quote_at timestamptz not null, feed text not null,
 score double precision not null, features jsonb not null, model_version text not null,
 due_at timestamptz not null, state text not null default 'OPEN',
 last_bid double precision, last_quote_at timestamptz, estimated_pl double precision,
 estimated_return double precision, max_return double precision, min_return double precision,
 closed_at timestamptz, outcome_return double precision,
 target_seen boolean not null default false, stop_seen boolean not null default false,
 unique(batch_id, contract, category, budget)
);
create index if not exists kst_options_created_idx on public.kst_option_signals(created_at desc);
create index if not exists kst_options_state_idx on public.kst_option_signals(state,due_at);
create table if not exists public.kst_option_marks (
 id uuid primary key, signal_id uuid not null references public.kst_option_signals(id),
 observed_at timestamptz not null, quote_at timestamptz not null,
 bid double precision not null, ask double precision not null,
 estimated_pl double precision not null, estimated_return double precision not null,
 unique(signal_id,quote_at)
);
create table if not exists public.kst_option_models (
 id uuid primary key, created_at timestamptz not null, version text unique not null,
 state text not null, weights jsonb not null, sample_count integer not null,
 report jsonb not null, trained_through timestamptz
);
create table if not exists public.kst_options_health (
 id text primary key, updated_at timestamptz not null, status text not null, message text not null
);
-- Broker/user-imported fills stay private. Public Worker never queries this table.
create table if not exists public.kst_imported_fills (
 fill_id text primary key, filled_at timestamptz not null, contract text not null,
 side text not null check(side in ('BUY','SELL')), quantity integer not null check(quantity>0),
 price double precision not null check(price>=0), fees double precision not null default 0,
 source text not null default 'USER_IMPORTED_NOT_BROKER_VERIFIED'
);
alter table public.kst_option_signals enable row level security;
alter table public.kst_option_marks enable row level security;
alter table public.kst_option_models enable row level security;
alter table public.kst_options_health enable row level security;
alter table public.kst_imported_fills enable row level security;
grant usage on schema public to service_role;
grant select,insert,update on public.kst_option_signals,public.kst_option_marks,public.kst_option_models,public.kst_options_health,public.kst_imported_fills to service_role;
revoke all on public.kst_option_signals,public.kst_option_marks,public.kst_option_models,public.kst_options_health,public.kst_imported_fills from anon,authenticated;
create table if not exists public.kst_trade_outcomes (
 id text primary key, created_at timestamptz not null, closed_at timestamptz not null,
 contract text not null, features jsonb not null, outcome_return double precision not null,
 realized_pl double precision not null, state text not null default 'CLOSED',
 feed text not null default 'actual', source text not null default 'USER_IMPORTED_NOT_BROKER_VERIFIED'
);
alter table public.kst_trade_outcomes enable row level security;
grant select,insert,update on public.kst_trade_outcomes to service_role;
revoke all on public.kst_trade_outcomes from anon,authenticated;
create table if not exists public.kst_session_reviews (
 id text primary key, updated_at timestamptz not null, report jsonb not null
);
alter table public.kst_session_reviews enable row level security;
grant select,insert,update on public.kst_session_reviews to service_role;
revoke all on public.kst_session_reviews from anon,authenticated;
-- Additions for news and on-demand requests; safe to apply after the earlier schema.
alter table public.kst_option_signals add column if not exists quality_label text not null default 'QUALIFIED';
create table if not exists public.kst_signal_requests (
 id text primary key, created_at timestamptz not null, category text not null,
 budget integer not null, status text not null default 'PENDING',
 completed_at timestamptz, results jsonb not null default '[]'::jsonb, message text
);
create index if not exists kst_requests_pending on public.kst_signal_requests(status,created_at);
create table if not exists public.kst_news (
 id text primary key, title text not null, url text not null, source text not null,
 published_at timestamptz not null, fetched_at timestamptz not null,
 sectors jsonb not null, importance double precision not null
);
create index if not exists kst_news_published on public.kst_news(published_at desc);
alter table public.kst_signal_requests enable row level security;
alter table public.kst_news enable row level security;
grant select,insert,update on public.kst_signal_requests,public.kst_news to service_role;
revoke all on public.kst_signal_requests,public.kst_news from anon,authenticated;
alter table public.kst_option_signals add column if not exists context_label text not null default 'STRUCTURAL_ONLY';
alter table public.kst_option_signals add column if not exists context_at timestamptz;
create table if not exists public.kst_market_proxy (
 id text primary key, updated_at timestamptz not null, payload jsonb not null
);
alter table public.kst_market_proxy enable row level security;
grant select,insert,update on public.kst_market_proxy to service_role;
revoke all on public.kst_market_proxy from anon,authenticated;
-- NEW research portfolios only. Existing/live balances are never changed.
create table if not exists public.kst_agent_accounts (
 agent text primary key, starting_balance numeric not null default 300 check(starting_balance>0),
 cash numeric not null default 300 check(cash>=0), realized_pl numeric not null default 0,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
insert into public.kst_agent_accounts(agent) values ('conservative'),('balanced'),('aggressive'),('challenge'),('daily_10pct_research') on conflict do nothing;
create table if not exists public.kst_agent_positions (
 id uuid primary key default gen_random_uuid(), agent text not null references public.kst_agent_accounts(agent),
 signal_id uuid not null references public.kst_option_signals(id), contract text not null,
 opened_at timestamptz not null default now(), entry_ask numeric not null,
 entry_cost numeric not null, last_bid numeric not null, quote_at timestamptz not null,
 due_at timestamptz not null, state text not null default 'OPEN',
 closed_at timestamptz, realized_pl numeric, exit_reason text,
 model_version text not null, regime text not null default 'UNCLASSIFIED',
 unique(agent,signal_id)
);
alter table public.kst_agent_positions add column if not exists peak_bid numeric;
create unique index if not exists kst_agent_one_contract on public.kst_agent_positions(agent,contract) where state='OPEN';
create table if not exists public.kst_agent_decisions (
 id uuid primary key default gen_random_uuid(), created_at timestamptz not null default now(),
 agent text not null, action text not null, reason text not null, signal_id uuid,
 model_version text, regime text
);
create table if not exists public.kst_market_memory (
 id uuid primary key, created_at timestamptz not null, symbol text not null,
 regime text not null, observation jsonb not null
);
create index if not exists kst_agent_decisions_date on public.kst_agent_decisions(created_at desc);
alter table public.kst_agent_accounts enable row level security;
alter table public.kst_agent_positions enable row level security;
alter table public.kst_agent_decisions enable row level security;
alter table public.kst_market_memory enable row level security;
grant select,insert,update on public.kst_agent_accounts,public.kst_agent_positions,public.kst_agent_decisions,public.kst_market_memory to service_role;
revoke all on public.kst_agent_accounts,public.kst_agent_positions,public.kst_agent_decisions,public.kst_market_memory from anon,authenticated;

create or replace function public.kst_agent_open(p_agent text,p_signal uuid,p_ask numeric,p_bid numeric,p_quote timestamptz)
returns jsonb language plpgsql security definer set search_path=public as $$
declare a public.kst_agent_accounts%rowtype; s public.kst_option_signals%rowtype;
 risk_fraction numeric; cost numeric; risk numeric; position_id uuid;
begin
 select * into a from public.kst_agent_accounts where agent=p_agent for update;
 if not found then return jsonb_build_object('action','WAIT','reason','Research account missing'); end if;
 risk_fraction:=case p_agent when 'conservative' then .005 when 'balanced' then .01 when 'aggressive' then .02 when 'challenge' then .025 when 'daily_10pct_research' then .01 else 0 end;
 select * into s from public.kst_option_signals where id=p_signal;
 if not found or s.feed<>'opra' or s.quality_label<>'QUALIFIED' or s.state<>'OPEN'
 or s.context_label not in ('BULLISH_SETUP_ALIGNED','BEARISH_SETUP_ALIGNED')
 or s.quote_at>now() or s.quote_at<now()-interval '5 minutes'
 or s.context_at is null or s.context_at<now()-interval '90 minutes' or s.due_at<=now()
 then return jsonb_build_object('action','WAIT','reason','No fresh OPRA contract aligned to a recent underlying setup'); end if;
 if p_ask is null or p_bid is null or p_quote is null or p_ask<=0 or p_bid<0 or p_ask<p_bid or p_quote>now() or p_quote<now()-interval '60 seconds'
 then return jsonb_build_object('action','WAIT','reason','Fresh executable-size option quote required'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and state='OPEN')
 then return jsonb_build_object('action','WAIT','reason','One open research position per agent'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and (signal_id=p_signal or (contract=s.contract and closed_at>now()-interval '30 minutes')))
 then return jsonb_build_object('action','WAIT','reason','Duplicate idea or 30-minute same-contract research cooldown'); end if;
  if (select coalesce(sum(realized_pl),0) from public.kst_agent_positions where agent=p_agent and state='CLOSED' and closed_at>=(date_trunc('day',now() at time zone 'America/New_York') at time zone 'America/New_York'))<=-(a.starting_balance*.10)
 then return jsonb_build_object('action','WAIT','reason','Daily research loss limit (10% of starting balance) reached'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and state='CLOSED' and realized_pl<0 and closed_at>now()-interval '15 minutes')
 then return jsonb_build_object('action','WAIT','reason','15-minute cooldown after a losing research exit'); end if;
 cost:=p_ask*100+s.fee_estimate;
 risk:=p_ask*100*.30+s.fee_estimate;
 if cost>a.cash or risk>greatest(0,a.cash)*risk_fraction
 then return jsonb_build_object('action','WAIT','reason','One contract exceeds available research cash or estimated stop-risk limit'); end if;
 insert into public.kst_agent_positions(agent,signal_id,contract,entry_ask,entry_cost,last_bid,quote_at,due_at,model_version,regime)
 values(p_agent,s.id,s.contract,p_ask,cost,p_bid,p_quote,s.due_at,s.model_version,s.context_label) returning id into position_id;
 update public.kst_agent_accounts set cash=cash-cost,updated_at=now() where agent=p_agent;
 return jsonb_build_object('action','RESEARCH_OPEN','reason','One contract modeled at recorded ask; no broker order','position_id',position_id);
end $$;
revoke all on function public.kst_agent_open(text,uuid,numeric,numeric,timestamptz) from public,anon,authenticated;
grant execute on function public.kst_agent_open(text,uuid,numeric,numeric,timestamptz) to service_role;

create or replace function public.kst_agent_mark(p_position uuid,p_bid numeric,p_quote timestamptz)
returns jsonb language plpgsql security definer set search_path=public as $$
declare p public.kst_agent_positions%rowtype; a public.kst_agent_accounts%rowtype;
 r numeric; exit_kind text; peak numeric; peak_r numeric;
begin
 -- Consistent lock order with the opener: account, then position.
 select * into p from public.kst_agent_positions where id=p_position;
 if not found then return jsonb_build_object('action','WAIT'); end if;
 select * into a from public.kst_agent_accounts where agent=p.agent for update;
 select * into p from public.kst_agent_positions where id=p_position for update;
 if p.state<>'OPEN' or p_bid<0 or p_bid is null or p_quote is null or p_quote<=p.quote_at or p_quote>now() or p_quote<now()-interval '5 minutes'
 then return jsonb_build_object('action','WAIT'); end if;
 r:=(p_bid*100-p.entry_cost)/p.entry_cost;
 peak:=greatest(coalesce(p.peak_bid,p.last_bid),p_bid);
 peak_r:=(peak*100-p.entry_cost)/p.entry_cost;
 exit_kind:=case when r<=-.30 then 'OBSERVED_STOP' when peak_r>=.20 and (p_bid*100-p.entry_cost)<=(peak*100-p.entry_cost)*.5 then 'TRAILING_GIVEBACK' when p_quote>=p.due_at then 'MEASUREMENT_HORIZON' else null end;
 update public.kst_agent_positions set last_bid=p_bid,quote_at=p_quote,peak_bid=peak where id=p.id;
 if exit_kind is not null then
  update public.kst_agent_positions set state='CLOSED',closed_at=p_quote,realized_pl=p_bid*100-p.entry_cost,exit_reason=exit_kind where id=p.id;
  update public.kst_agent_accounts set cash=cash+p_bid*100,realized_pl=realized_pl+p_bid*100-p.entry_cost,updated_at=now() where agent=p.agent;
  return jsonb_build_object('action','RESEARCH_CLOSE','reason',exit_kind);
 end if;
 return jsonb_build_object('action','RESEARCH_MARK');
end $$;
revoke all on function public.kst_agent_mark(uuid,numeric,timestamptz) from public,anon,authenticated;
grant execute on function public.kst_agent_mark(uuid,numeric,timestamptz) to service_role;
create or replace function public.kst_ai_progress()
returns jsonb language sql stable security definer set search_path=public as $$
 select jsonb_build_object('mode','PAPER_RESEARCH_ONLY','generated_at',now(),'accounts',coalesce(jsonb_agg(jsonb_build_object(
 'agent',a.agent,'starting_balance',a.starting_balance,'cash',a.cash,'realized_pl',a.realized_pl,
 'equity',a.cash+coalesce((select sum(p.last_bid*100) from public.kst_agent_positions p where p.agent=a.agent and p.state='OPEN'),0),
 'unrealized_pl',coalesce((select sum(p.last_bid*100-p.entry_cost) from public.kst_agent_positions p where p.agent=a.agent and p.state='OPEN'),0),
 'closed_trades',(select count(*) from public.kst_agent_positions p where p.agent=a.agent and p.state='CLOSED'),
 'wins',(select count(*) from public.kst_agent_positions p where p.agent=a.agent and p.state='CLOSED' and p.realized_pl>0),
 'open_positions',coalesce((select jsonb_agg(jsonb_build_object('contract',p.contract,'opened_at',p.opened_at,'entry_ask',p.entry_ask,'entry_cost',p.entry_cost,'last_bid',p.last_bid,'quote_at',p.quote_at,'unrealized_pl',p.last_bid*100-p.entry_cost,'model_version',p.model_version,'regime',p.regime)) from public.kst_agent_positions p where p.agent=a.agent and p.state='OPEN'),'[]'::jsonb),
 'last_decision',(select jsonb_build_object('created_at',d.created_at,'action',d.action,'reason',d.reason,'model_version',d.model_version,'regime',d.regime) from public.kst_agent_decisions d where d.agent=a.agent order by d.created_at desc limit 1),
 'updated_at',a.updated_at
 ) order by a.agent),'[]'::jsonb)) from public.kst_agent_accounts a;
$$;
revoke all on function public.kst_ai_progress() from public,anon,authenticated;
grant execute on function public.kst_ai_progress() to service_role;
create table if not exists public.kst_agent_outcomes (
 id uuid primary key references public.kst_agent_positions(id), created_at timestamptz not null,
 closed_at timestamptz not null, contract text not null, features jsonb not null,
 outcome_return double precision not null, state text not null default 'CLOSED',
 feed text not null default 'paper_opra', quality_label text not null default 'QUALIFIED'
);
alter table public.kst_agent_outcomes enable row level security;
grant select,insert,update on public.kst_agent_outcomes to service_role;
revoke all on public.kst_agent_outcomes from anon,authenticated;

-- A trigger attaches the features known at the paper entry to each completed paper result.
create or replace function public.kst_capture_agent_outcome()
returns trigger language plpgsql security definer set search_path=public as $$
begin
 if new.state='CLOSED' and old.state='OPEN' and new.entry_cost>0 then
  insert into public.kst_agent_outcomes(id,created_at,closed_at,contract,features,outcome_return)
  select new.id,new.opened_at,new.closed_at,new.contract,s.features,new.realized_pl/new.entry_cost
  from public.kst_option_signals s where s.id=new.signal_id and s.feed='opra' and s.quality_label='QUALIFIED'
  on conflict(id) do nothing;
 end if;
 return new;
end $$;
revoke all on function public.kst_capture_agent_outcome() from public,anon,authenticated;
drop trigger if exists kst_capture_agent_outcome on public.kst_agent_positions;
create trigger kst_capture_agent_outcome after update on public.kst_agent_positions for each row execute function public.kst_capture_agent_outcome();
-- Public paper activity; push endpoints and delivery state remain private.
create table if not exists public.kst_trade_activity (
 id uuid primary key default gen_random_uuid(), created_at timestamptz not null default now(),
 agent text not null, position_id uuid not null references public.kst_agent_positions(id),
 action text not null check(action in ('ENTRY','ADD','EXIT')), contract text not null, quote_at timestamptz,
 quantity integer not null, price numeric not null, realized_pl numeric,
 reason text not null, simulation_only boolean not null default true
);
create unique index if not exists kst_activity_once on public.kst_trade_activity(position_id,action) where action in ('ENTRY','EXIT');
create index if not exists kst_activity_date on public.kst_trade_activity(created_at desc);
create table if not exists public.kst_push_subscriptions (
 id text primary key, endpoint text unique not null, keys jsonb not null,
 token_hash text not null, event_types jsonb not null, active boolean not null default true,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.kst_push_deliveries (
 id uuid primary key default gen_random_uuid(), subscription_id text not null references public.kst_push_subscriptions(id),
 event_id uuid not null references public.kst_trade_activity(id), state text not null default 'PENDING',
 attempts integer not null default 0, lease_until timestamptz, sent_at timestamptz,
 unique(subscription_id,event_id)
);
alter table public.kst_trade_activity enable row level security;
alter table public.kst_push_subscriptions enable row level security;
alter table public.kst_push_deliveries enable row level security;
grant select,insert,update on public.kst_trade_activity,public.kst_push_subscriptions,public.kst_push_deliveries to service_role;
revoke all on public.kst_trade_activity,public.kst_push_subscriptions,public.kst_push_deliveries from anon,authenticated;

create or replace function public.kst_post_paper_activity()
returns trigger language plpgsql security definer set search_path=public as $$
begin
 if TG_OP='INSERT' then
  insert into public.kst_trade_activity(agent,position_id,action,contract,quote_at,quantity,price,reason)
  values(new.agent,new.id,'ENTRY',new.contract,new.quote_at,1,new.entry_ask,'Paper entry at recorded real ask') on conflict do nothing;
 elsif old.state='OPEN' and new.state='CLOSED' then
  insert into public.kst_trade_activity(agent,position_id,action,contract,quote_at,quantity,price,realized_pl,reason)
  values(new.agent,new.id,'EXIT',new.contract,new.quote_at,1,new.last_bid,new.realized_pl,new.exit_reason) on conflict do nothing;
 end if;
 return new;
end $$;
revoke all on function public.kst_post_paper_activity() from public,anon,authenticated;
drop trigger if exists kst_post_paper_entry on public.kst_agent_positions;
create trigger kst_post_paper_entry after insert on public.kst_agent_positions for each row execute function public.kst_post_paper_activity();
drop trigger if exists kst_post_paper_exit on public.kst_agent_positions;
create trigger kst_post_paper_exit after update on public.kst_agent_positions for each row execute function public.kst_post_paper_activity();

create or replace function public.kst_queue_push()
returns trigger language plpgsql security definer set search_path=public as $$
begin
 insert into public.kst_push_deliveries(subscription_id,event_id)
 select s.id,new.id from public.kst_push_subscriptions s where s.active and s.event_types ? new.action
 on conflict do nothing;
 return new;
end $$;
revoke all on function public.kst_queue_push() from public,anon,authenticated;
drop trigger if exists kst_queue_push on public.kst_trade_activity;
create trigger kst_queue_push after insert on public.kst_trade_activity for each row execute function public.kst_queue_push();

create or replace function public.kst_set_push(p_id text,p_endpoint text,p_keys jsonb,p_token_hash text,p_events jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare saved_id text;
begin
 insert into public.kst_push_subscriptions(id,endpoint,keys,token_hash,event_types)
 values(p_id,p_endpoint,p_keys,p_token_hash,p_events)
 on conflict(id) do update set keys=excluded.keys,event_types=excluded.event_types,active=true,updated_at=now()
 where public.kst_push_subscriptions.token_hash=excluded.token_hash
 returning id into saved_id;
 return jsonb_build_object('ok',saved_id is not null);
end $$;
revoke all on function public.kst_set_push(text,text,jsonb,text,jsonb) from public,anon,authenticated;
grant execute on function public.kst_set_push(text,text,jsonb,text,jsonb) to service_role;
create or replace function public.kst_unset_push(p_token_hash text)
returns jsonb language plpgsql security definer set search_path=public as $$
begin
 update public.kst_push_subscriptions set active=false,updated_at=now() where token_hash=p_token_hash;
 return jsonb_build_object('ok',true);
end $$;
revoke all on function public.kst_unset_push(text) from public,anon,authenticated;
grant execute on function public.kst_unset_push(text) to service_role;

create or replace function public.kst_claim_push()
returns setof public.kst_push_deliveries language sql security definer set search_path=public as $$
 update public.kst_push_deliveries set state='SENDING',attempts=attempts+1,lease_until=now()+interval '5 minutes'
 where id in (select d.id from public.kst_push_deliveries d join public.kst_push_subscriptions s on s.id=d.subscription_id
 join public.kst_trade_activity e on e.id=d.event_id
 where s.active and d.attempts<3 and e.created_at>=now()-interval '10 minutes'
 and (d.state='PENDING' or (d.state='SENDING' and d.lease_until<now()))
 order by e.created_at limit 10 for update of d skip locked) returning *;
$$;
revoke all on function public.kst_claim_push() from public,anon,authenticated;
grant execute on function public.kst_claim_push() to service_role;

-- r4: supplied risk inputs; nulls represent unavailable Greeks, never zeroes.
alter table public.kst_option_signals add column if not exists risk_snapshot jsonb;
