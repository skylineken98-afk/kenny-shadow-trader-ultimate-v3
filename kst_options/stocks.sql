-- Apply AFTER kst_options/schema.sql. Public research plans, not user holdings.
create table if not exists public.kst_stock_plans (
 id uuid primary key, symbol text not null, created_at timestamptz not null, quote_at timestamptz not null,
 feed text not null, state text not null default 'OPEN' check(state in ('OPEN','CLOSED')),
 entry_ask numeric not null check(entry_ask>0),last_bid numeric not null,peak_bid numeric not null,
 stop numeric not null,target numeric not null,risk_per_share numeric not null check(risk_per_share>0),
 due_at timestamptz not null,score numeric not null,reason text not null,exit_reason text,closed_at timestamptz,
 check(stop<entry_ask and target>entry_ask)
);
create unique index if not exists kst_one_stock_plan on public.kst_stock_plans(symbol) where state='OPEN';
create table if not exists public.kst_stock_alerts (
 id uuid primary key default gen_random_uuid(),plan_id uuid not null unique references public.kst_stock_plans(id),
 symbol text not null,created_at timestamptz not null default now(),quote_at timestamptz not null,
 price numeric not null,reason text not null,research_only boolean not null default true
);
create table if not exists public.kst_stock_push_deliveries (
 id uuid primary key default gen_random_uuid(),subscription_id text not null references public.kst_push_subscriptions(id),
 event_id uuid not null references public.kst_stock_alerts(id),state text not null default 'PENDING',
 attempts integer not null default 0,lease_until timestamptz,sent_at timestamptz,unique(subscription_id,event_id)
);
alter table public.kst_stock_plans enable row level security;
alter table public.kst_stock_alerts enable row level security;
alter table public.kst_stock_push_deliveries enable row level security;
revoke all on public.kst_stock_plans,public.kst_stock_alerts,public.kst_stock_push_deliveries from anon,authenticated;
grant select,insert,update on public.kst_stock_plans,public.kst_stock_alerts,public.kst_stock_push_deliveries to service_role;

create or replace function public.kst_mark_stock(p_id uuid,p_bid numeric,p_quote timestamptz)
returns jsonb language plpgsql security definer set search_path=public as $$
declare p public.kst_stock_plans%rowtype;peak numeric;why text;
begin
 select * into p from public.kst_stock_plans where id=p_id for update;
 if not found or p.state<>'OPEN' then return jsonb_build_object('action','SKIP');end if;
 if p_bid is null or p_bid<=0 or p_bid::text in ('NaN','Infinity','-Infinity') or p_quote is null or p_quote<=p.quote_at or p_quote>now() or p_quote<now()-interval '60 seconds' then return jsonb_build_object('action','SKIP');end if;
 peak:=greatest(p.peak_bid,p_bid);
 if p_bid<=p.stop then why:='STOP_INVALIDATION';
 elsif p_bid>=p.target then why:='TARGET_REACHED';
 elsif peak>=p.entry_ask+p.risk_per_share and p_bid<=peak-p.risk_per_share then why:='TRAILING_GIVEBACK';
 elsif p_quote>=p.due_at then why:='REVIEW_DEADLINE';end if;
 update public.kst_stock_plans set last_bid=p_bid,peak_bid=peak,quote_at=p_quote,
 state=case when why is null then 'OPEN' else 'CLOSED' end,exit_reason=why,
 closed_at=case when why is not null then now() else null end where id=p_id;
 if why is not null then
  insert into public.kst_stock_alerts(plan_id,symbol,quote_at,price,reason) values(p.id,p.symbol,p_quote,p_bid,why) on conflict do nothing;
 end if;
 return jsonb_build_object('action',case when why is null then 'MARK' else 'RESEARCH_EXIT_ALERT' end,'reason',why);
end $$;
revoke all on function public.kst_mark_stock(uuid,numeric,timestamptz) from public,anon,authenticated;
grant execute on function public.kst_mark_stock(uuid,numeric,timestamptz) to service_role;

create or replace function public.kst_queue_stock_push()
returns trigger language plpgsql security definer set search_path=public as $$
begin
 insert into public.kst_stock_push_deliveries(subscription_id,event_id)
 select id,new.id from public.kst_push_subscriptions where active and event_types ? 'STOCK_EXIT' on conflict do nothing;
 return new;
end $$;
revoke all on function public.kst_queue_stock_push() from public,anon,authenticated;
drop trigger if exists kst_queue_stock_push on public.kst_stock_alerts;
create trigger kst_queue_stock_push after insert on public.kst_stock_alerts for each row execute function public.kst_queue_stock_push();
create or replace function public.kst_claim_stock_push()
returns setof public.kst_stock_push_deliveries language sql security definer set search_path=public as $$
 update public.kst_stock_push_deliveries set state='SENDING',attempts=attempts+1,lease_until=now()+interval '5 minutes'
 where id in(select d.id from public.kst_stock_push_deliveries d join public.kst_push_subscriptions s on s.id=d.subscription_id
 join public.kst_stock_alerts e on e.id=d.event_id where s.active and s.event_types ? 'STOCK_EXIT' and d.attempts<3 and e.created_at>=now()-interval '10 minutes'
 and (d.state='PENDING' or (d.state='SENDING' and d.lease_until<now())) order by e.created_at limit 10 for update of d skip locked) returning *;
$$;
revoke all on function public.kst_claim_stock_push() from public,anon,authenticated;
grant execute on function public.kst_claim_stock_push() to service_role;
