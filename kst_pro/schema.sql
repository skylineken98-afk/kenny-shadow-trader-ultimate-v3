-- r5. Apply after options/schema.sql, options/stocks.sql and chat/schema.sql.
create table if not exists public.kst_earnings (
 id text primary key,symbol text not null,report_date date not null,timing text not null,
 eps_estimate numeric,revenue_estimate numeric,source text not null,fetched_at timestamptz not null,
 active boolean not null default true,details jsonb not null default '{}'
);
create index if not exists kst_earnings_date on public.kst_earnings(report_date,symbol);
create table if not exists public.kst_company_news (
 id text primary key,symbol text not null,title text not null,url text not null,source text not null,
 published_at timestamptz not null,fetched_at timestamptz not null,category text not null default 'Company'
);
create index if not exists kst_company_news_symbol on public.kst_company_news(symbol,published_at desc);
create table if not exists public.kst_data_requests(id text primary key,symbol text not null,status text not null default 'PENDING',created_at timestamptz not null default now());
create table if not exists public.kst_personal_positions (
 id uuid primary key,user_id uuid not null references auth.users(id) on delete cascade,
 symbol text not null,quantity numeric not null check(quantity>0),entry numeric not null check(entry>0),
 stop numeric not null,target numeric not null,trailing_pct numeric,
 state text not null default 'MONITORING',created_at timestamptz not null default now(),
 last_bid numeric,peak_bid numeric,quote_at timestamptz,alert_reason text,
 check(stop>0 and stop<entry and target>entry),check(trailing_pct is null or trailing_pct>0 and trailing_pct<1)
);
create table if not exists public.kst_private_alerts (
 id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
 position_id uuid references public.kst_personal_positions(id) on delete cascade,
 kind text not null default 'PERSONAL_EXIT',symbol text,reason text not null,price numeric,
 quote_at timestamptz,created_at timestamptz not null default now(),unique(position_id)
);
alter table public.kst_push_subscriptions add column if not exists user_id uuid references auth.users(id) on delete cascade;
create table if not exists public.kst_private_push_deliveries (
 id uuid primary key default gen_random_uuid(),subscription_id text not null references public.kst_push_subscriptions(id),
 event_id uuid not null references public.kst_private_alerts(id) on delete cascade,
 state text not null default 'PENDING',attempts integer not null default 0,lease_until timestamptz,sent_at timestamptz,unique(subscription_id,event_id)
);
create table if not exists public.kst_memberships (
 user_id uuid primary key references auth.users(id) on delete cascade,
 paid_until timestamptz,paid_lifetime boolean not null default false,
 pass_until timestamptz,pass_lifetime boolean not null default false,
 customer_id text,stripe_subscription_id text,last_event bigint not null default 0,updated_at timestamptz not null default now()
);
create table if not exists public.kst_billing_sessions(id text primary key,user_id uuid not null references auth.users(id) on delete cascade,plan text not null,created_at timestamptz not null default now());
create table if not exists public.kst_billing_events(id text primary key,created_at timestamptz not null default now());
create table if not exists public.kst_admin_audit(id uuid primary key default gen_random_uuid(),actor uuid not null,subject uuid,action text not null,created_at timestamptz not null default now());
create table if not exists public.kst_service_heartbeats(id text primary key,updated_at timestamptz not null default now(),status text not null,message text not null);
create table if not exists public.kst_system_incidents(id text primary key,service text not null,state text not null,opened_at timestamptz not null default now(),recovered_at timestamptz);
create table if not exists public.kst_research_samples(id uuid primary key,created_at timestamptz not null,contract text not null,features jsonb not null,entry_known_at timestamptz not null);
create table if not exists public.kst_research_reports(id uuid primary key default gen_random_uuid(),created_at timestamptz not null default now(),state text not null,report jsonb not null);
-- No browser writes; all private accesses also enforce ownership in the server.
do $$declare t text;begin
 foreach t in array array['kst_earnings','kst_company_news','kst_data_requests','kst_personal_positions','kst_private_alerts','kst_private_push_deliveries','kst_memberships','kst_billing_sessions','kst_billing_events','kst_admin_audit','kst_service_heartbeats','kst_system_incidents','kst_research_samples','kst_research_reports'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from anon,authenticated',t);
 execute format('grant select,insert,update,delete on public.%I to service_role',t);
 end loop;
end $$;
create or replace function public.kst_save_personal_position(p_row jsonb) returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtextextended(p_row->>'user_id',842912));
 if (select count(*) from public.kst_personal_positions where user_id=(p_row->>'user_id')::uuid and state='MONITORING')>=20 then return false;end if;
 insert into public.kst_personal_positions(id,user_id,symbol,quantity,entry,stop,target,trailing_pct)
 values((p_row->>'id')::uuid,(p_row->>'user_id')::uuid,p_row->>'symbol',(p_row->>'quantity')::numeric,(p_row->>'entry')::numeric,(p_row->>'stop')::numeric,(p_row->>'target')::numeric,(p_row->>'trailing_pct')::numeric);return true;
end $$;
create or replace function public.kst_mark_personal(p_id uuid,p_bid numeric,p_quote timestamptz) returns jsonb language plpgsql security definer set search_path=public as $$
declare p public.kst_personal_positions%rowtype;peak numeric;why text;
begin
 select * into p from public.kst_personal_positions where id=p_id for update;
 if not found or p.state<>'MONITORING' or p_bid is null or p_bid<=0 or p_bid::text in ('NaN','Infinity','-Infinity') or p_quote is null or p_quote<=coalesce(p.quote_at,p.created_at) or p_quote>now() or p_quote<now()-interval '60 seconds' then return jsonb_build_object('action','SKIP');end if;
 peak:=greatest(coalesce(p.peak_bid,p.entry),p_bid);
 if p_bid<=p.stop then why:='STOP_INVALIDATION';elsif p_bid>=p.target then why:='TARGET_REACHED';
 elsif p.trailing_pct is not null and peak>p.entry and p_bid<=peak*(1-p.trailing_pct) then why:='TRAILING_GIVEBACK';end if;
 update public.kst_personal_positions set last_bid=p_bid,peak_bid=peak,quote_at=p_quote,alert_reason=why,state=case when why is null then 'MONITORING' else 'ALERTED' end where id=p.id;
 if why is not null then insert into public.kst_private_alerts(user_id,position_id,symbol,reason,price,quote_at) values(p.user_id,p.id,p.symbol,why,p_bid,p_quote) on conflict do nothing;end if;
 return jsonb_build_object('action',case when why is null then 'MARK' else 'ALERT' end);
end $$;
create or replace function public.kst_queue_private_push() returns trigger language plpgsql security definer set search_path=public as $$
begin
 insert into public.kst_private_push_deliveries(subscription_id,event_id) select id,new.id from public.kst_push_subscriptions where active and user_id=new.user_id and event_types ? new.kind on conflict do nothing;return new;
end $$;
drop trigger if exists kst_queue_private_push on public.kst_private_alerts;
create trigger kst_queue_private_push after insert on public.kst_private_alerts for each row execute function public.kst_queue_private_push();
create or replace function public.kst_claim_private_push() returns setof public.kst_private_push_deliveries language sql security definer set search_path=public as $$
 update public.kst_private_push_deliveries set state='SENDING',attempts=attempts+1,lease_until=now()+interval '5 minutes'
 where id in(select d.id from public.kst_private_push_deliveries d join public.kst_push_subscriptions s on s.id=d.subscription_id join public.kst_private_alerts e on e.id=d.event_id where s.active and s.user_id=e.user_id and s.event_types ? e.kind and d.attempts<3 and e.created_at>=now()-interval '10 minutes' and (d.state='PENDING' or (d.state='SENDING' and d.lease_until<now())) order by e.created_at limit 10 for update of d skip locked) returning *;
$$;
create or replace function public.kst_apply_billing(p_event text,p_user uuid,p_created bigint,p_until timestamptz,p_lifetime boolean,p_customer text,p_subscription text) returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,842913));
 if exists(select 1 from public.kst_billing_events where id=p_event) then return true;end if;
 insert into public.kst_memberships(user_id) values(p_user) on conflict do nothing;
 update public.kst_memberships set paid_until=case when p_subscription is null then paid_until else p_until end,paid_lifetime=paid_lifetime or p_lifetime,customer_id=coalesce(p_customer,customer_id),stripe_subscription_id=coalesce(p_subscription,stripe_subscription_id),last_event=greatest(last_event,p_created),updated_at=now()
 where user_id=p_user and (p_subscription is null or p_created>=last_event);
 insert into public.kst_billing_events(id) values(p_event) on conflict do nothing;return true;
end $$;
-- Every SECURITY DEFINER function is service-only.
revoke all on function public.kst_save_personal_position(jsonb),public.kst_mark_personal(uuid,numeric,timestamptz),public.kst_queue_private_push(),public.kst_claim_private_push(),public.kst_apply_billing(text,uuid,bigint,timestamptz,boolean,text,text) from public,anon,authenticated;
grant execute on function public.kst_save_personal_position(jsonb),public.kst_mark_personal(uuid,numeric,timestamptz),public.kst_claim_private_push(),public.kst_apply_billing(text,uuid,bigint,timestamptz,boolean,text,text) to service_role;
create or replace function public.kst_replace_earnings(p_rows jsonb,p_from date,p_to date) returns void language plpgsql security definer set search_path=public as $$
begin
 update public.kst_earnings set active=false where report_date between p_from and p_to;
 insert into public.kst_earnings select * from jsonb_populate_recordset(null::public.kst_earnings,p_rows)
 on conflict(id) do update set timing=excluded.timing,eps_estimate=excluded.eps_estimate,revenue_estimate=excluded.revenue_estimate,fetched_at=excluded.fetched_at,active=true;
end $$;
revoke all on function public.kst_replace_earnings(jsonb,date,date) from public,anon,authenticated;
grant execute on function public.kst_replace_earnings(jsonb,date,date) to service_role;
alter table public.kst_data_requests add column if not exists user_id uuid references auth.users(id) on delete cascade;
create or replace function public.kst_queue_market_data(p_user uuid,p_id text,p_symbol text) returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,842914));
 if (select count(*) from public.kst_data_requests where user_id=p_user and created_at>=now()-interval '1 minute')>=3 then return false;end if;
 insert into public.kst_data_requests(id,symbol,user_id) values(p_id,p_symbol,p_user) on conflict do nothing;return true;
end $$;
create or replace function public.kst_link_private_push(p_user uuid,p_hash text) returns boolean language plpgsql security definer set search_path=public as $$
declare n integer;begin
 update public.kst_push_subscriptions set user_id=p_user where token_hash=p_hash and active;
 get diagnostics n=row_count;return n>0;
end $$;
create or replace function public.kst_search_chat_history(p_user uuid,p_query text) returns table(conversation_id uuid,title text,preview text,created_at timestamptz) language sql stable security definer set search_path=public as $$
 select c.id,c.title,left(t.user_text||' — '||coalesce(t.assistant_text,''),320),t.created_at from public.kst_chat_turns t join public.kst_chat_conversations c on c.id=t.conversation_id
 where t.user_id=p_user and c.user_id=p_user and t.status='COMPLETE' and to_tsvector('simple',t.user_text||' '||coalesce(t.assistant_text,''))@@websearch_to_tsquery('simple',left(p_query,120)) order by t.created_at desc limit 30;
$$;
revoke all on function public.kst_queue_market_data(uuid,text,text),public.kst_link_private_push(uuid,text),public.kst_search_chat_history(uuid,text) from public,anon,authenticated;
grant execute on function public.kst_queue_market_data(uuid,text,text),public.kst_link_private_push(uuid,text),public.kst_search_chat_history(uuid,text) to service_role;
alter table public.kst_data_requests add column if not exists attempts integer not null default 0;
alter table public.kst_data_requests add column if not exists lease_until timestamptz;
create or replace function public.kst_claim_data_requests() returns setof public.kst_data_requests language sql security definer set search_path=public as $$
 update public.kst_data_requests set status='RUNNING',attempts=attempts+1,lease_until=now()+interval '5 minutes' where id in (
 select id from public.kst_data_requests where attempts<3 and created_at>=now()-interval '1 hour' and (status='PENDING' or status='RUNNING' and lease_until<now()) order by created_at limit 3 for update skip locked) returning *;
$$;
revoke all on function public.kst_claim_data_requests() from public,anon,authenticated;
grant execute on function public.kst_claim_data_requests() to service_role;
-- Track each subscription independently: an old cancellation cannot revoke a
-- different active subscription or a free pass.
create table if not exists public.kst_paid_subscriptions (
 id text primary key,user_id uuid not null references auth.users(id) on delete cascade,
 paid_until timestamptz,last_event bigint not null default 0
);
alter table public.kst_paid_subscriptions enable row level security;
revoke all on public.kst_paid_subscriptions from anon,authenticated;
grant select,insert,update on public.kst_paid_subscriptions to service_role;
insert into public.kst_paid_subscriptions(id,user_id,paid_until,last_event)
 select stripe_subscription_id,user_id,paid_until,last_event from public.kst_memberships where stripe_subscription_id is not null on conflict do nothing;
create or replace function public.kst_apply_billing(p_event text,p_user uuid,p_created bigint,p_until timestamptz,p_lifetime boolean,p_customer text,p_subscription text) returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,842913));
 if exists(select 1 from public.kst_billing_events where id=p_event) then return true;end if;
 insert into public.kst_memberships(user_id) values(p_user) on conflict do nothing;
 if p_subscription is not null then
  insert into public.kst_paid_subscriptions(id,user_id,paid_until,last_event) values(p_subscription,p_user,p_until,p_created)
  on conflict(id) do update set paid_until=excluded.paid_until,last_event=excluded.last_event where public.kst_paid_subscriptions.user_id=p_user and excluded.last_event>=public.kst_paid_subscriptions.last_event;
 end if;
 update public.kst_memberships set paid_until=(select max(paid_until) from public.kst_paid_subscriptions where user_id=p_user),paid_lifetime=paid_lifetime or p_lifetime,customer_id=coalesce(p_customer,customer_id),stripe_subscription_id=coalesce(p_subscription,stripe_subscription_id),last_event=greatest(last_event,p_created),updated_at=now() where user_id=p_user;
 insert into public.kst_billing_events(id) values(p_event) on conflict do nothing;return true;
end $$;
-- Preserve first-observed availability even when a cached headline is refreshed.
alter table public.kst_company_news add column if not exists first_seen_at timestamptz not null default now();
create or replace function public.kst_admin_grant_pass(p_actor uuid,p_subject uuid,p_action text) returns boolean language plpgsql security definer set search_path=public as $$
begin
 if p_action not in ('month','lifetime','revoke') then raise exception 'Invalid pass action';end if;
 insert into public.kst_memberships(user_id,pass_lifetime,pass_until) values(p_subject,p_action='lifetime',case when p_action='month' then now()+interval '30 days' else null end)
 on conflict(user_id) do update set pass_lifetime=excluded.pass_lifetime,pass_until=excluded.pass_until,updated_at=now();
 insert into public.kst_admin_audit(actor,subject,action) values(p_actor,p_subject,'PASS_'||upper(p_action));return true;
end $$;
revoke all on function public.kst_admin_grant_pass(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.kst_admin_grant_pass(uuid,uuid,text) to service_role;
