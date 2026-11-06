alter table public.kst_agent_positions add column if not exists profit_stop_return numeric not null default -.30;
alter table public.kst_agent_positions add column if not exists quantity integer not null default 1;
alter table public.kst_agent_positions add column if not exists last_add_bid numeric;

create or replace function public.kst_paper_strong_trend(p_signal uuid)
returns boolean language sql stable security invoker set search_path=public as $$
 select coalesce((select u.status='SETUP'
 and u.created_at between now()-interval '5 minutes' and now()
 and u.side=case s.option_type when 'CALL' then 'BULLISH' else 'BEARISH' end
 and u.details->'frames'->'5m'->>'trend'=u.side
 and (u.details->'frames'->'5m'->>'bar_closed_at')::timestamptz between now()-interval '10 minutes' and now()
 from public.kst_option_signals s cross join lateral
 (select * from public.ultimate_signals where symbol=s.underlying order by created_at desc limit 1) u
 where s.id=p_signal),false);
$$;
revoke all on function public.kst_paper_strong_trend(uuid) from public,anon,authenticated;
grant execute on function public.kst_paper_strong_trend(uuid) to service_role;

create or replace function public.kst_agent_open(p_agent text,p_signal uuid,p_ask numeric,p_bid numeric,p_quote timestamptz)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare a public.kst_agent_accounts%rowtype; s public.kst_option_signals%rowtype;
 risk_fraction numeric; cost numeric; risk numeric; position_id uuid; daily_required boolean; strong_trend boolean;
begin
 if extract(isodow from now() at time zone 'America/New_York')>5 or (now() at time zone 'America/New_York')::time not between time '09:30' and time '15:59:59' then return jsonb_build_object('action','WAIT','reason','Regular session closed; no simulated entry'); end if;
 select * into a from public.kst_agent_accounts where agent=p_agent for update;
 if not found then return jsonb_build_object('action','WAIT','reason','Research account missing'); end if;
 risk_fraction:=case p_agent when 'conservative' then .005 when 'balanced' then .01 when 'aggressive' then .02 when 'challenge' then .025 when 'daily_10pct_research' then .01 else 0 end;
 daily_required:=(now() at time zone 'America/New_York')::time>=time '15:45' and not exists(select 1 from public.kst_agent_positions where agent=p_agent and opened_at>=(date_trunc('day',now() at time zone 'America/New_York') at time zone 'America/New_York'));
 if daily_required then risk_fraction:=.03; end if;
 select * into s from public.kst_option_signals where id=p_signal;
 strong_trend:=public.kst_paper_strong_trend(s.id);
 if not found or s.feed not in ('opra','indicative') or s.quality_label<>'QUALIFIED' or (s.state<>'OPEN' and not (p_agent='aggressive' and strong_trend))
 or (not daily_required and s.context_label not in ('BULLISH_SETUP_ALIGNED','BEARISH_SETUP_ALIGNED'))
 or s.quote_at>now() or s.quote_at<now()-interval '5 minutes'
 or (not daily_required and (s.context_at is null or s.context_at<now()-interval '5 minutes')) or s.due_at<=now()
 then return jsonb_build_object('action','WAIT','reason','No fresh labeled research contract aligned to a current underlying setup'); end if;
 if p_ask is null or p_bid is null or p_quote is null or p_ask<=0 or p_bid<0 or p_ask<p_bid or p_quote>now() or p_quote<now()-interval '60 seconds'
 then return jsonb_build_object('action','WAIT','reason','Fresh executable-size option quote required'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and state='OPEN')
 then return jsonb_build_object('action','WAIT','reason','One open research position per agent'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and (signal_id=p_signal or contract=s.contract) and closed_at>now()-interval '30 minutes' and not (p_agent='aggressive' and strong_trend))
 then return jsonb_build_object('action','WAIT','reason','Duplicate idea or 30-minute same-contract research cooldown'); end if;
  if (select coalesce(sum(realized_pl),0) from public.kst_agent_positions where agent=p_agent and state='CLOSED' and closed_at>=(date_trunc('day',now() at time zone 'America/New_York') at time zone 'America/New_York'))<=-(a.starting_balance*.10)
 then return jsonb_build_object('action','WAIT','reason','Daily research loss limit (10% of starting balance) reached'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and state='CLOSED' and realized_pl<0 and closed_at>now()-interval '15 minutes' and not (p_agent='aggressive' and strong_trend))
 then return jsonb_build_object('action','WAIT','reason','15-minute cooldown after a losing research exit'); end if;
 cost:=p_ask*100+s.fee_estimate;
 risk:=p_ask*100*(case when p_agent='aggressive' then .25 else .30 end)+s.fee_estimate;
 if daily_required and cost>least(100,a.cash) then return jsonb_build_object('action','WAIT','reason','Daily exploration exceeds $100 virtual premium cap'); end if;
 if cost>a.cash or risk>greatest(0,a.cash)*risk_fraction
 then return jsonb_build_object('action','WAIT','reason','One contract exceeds available research cash or estimated stop-risk limit'); end if;
 if exists(select 1 from public.kst_agent_positions where agent=p_agent and signal_id=s.id) then
  if not (p_agent='aggressive' and strong_trend) then return jsonb_build_object('action','WAIT','reason','Signal already used by agent'); end if;
  s.id:=gen_random_uuid();s.batch_id:=gen_random_uuid();s.created_at:=now();
  s.entry_ask:=p_ask;s.entry_bid:=p_bid;s.quote_at:=p_quote;s.budget:=cost;
  s.state:='OPEN';s.last_bid:=null;s.last_quote_at:=null;s.estimated_pl:=null;s.estimated_return:=null;
  s.closed_at:=null;s.outcome_return:=null;s.max_return:=null;s.min_return:=null;s.target_seen:=false;s.stop_seen:=false;
  s.risk_snapshot:=s.risk_snapshot-'profit_lock'-'observed_barrier';
  insert into public.kst_option_signals select (s).*;
 end if;
 insert into public.kst_agent_positions(agent,signal_id,contract,entry_ask,entry_cost,last_bid,quote_at,due_at,model_version,regime,profit_stop_return)
 values(p_agent,s.id,s.contract,p_ask,cost,p_bid,p_quote,case when p_agent='aggressive' then least(s.due_at,(date_trunc('day',now() at time zone 'America/New_York')+interval '16 hours') at time zone 'America/New_York') else s.due_at end,s.model_version,case when daily_required then 'DAILY_REQUIRED_RESEARCH' else s.context_label end,case when p_agent='aggressive' then -.25 else -.30 end) returning id into position_id;
 update public.kst_agent_accounts set cash=cash-cost,updated_at=now() where agent=p_agent;
 return jsonb_build_object('action','RESEARCH_OPEN','reason','One virtual contract at observed ask; source feed remains labeled; no broker order','position_id',position_id);
end $$;
revoke all on function public.kst_agent_open(text,uuid,numeric,numeric,timestamptz) from public,anon,authenticated;
grant execute on function public.kst_agent_open(text,uuid,numeric,numeric,timestamptz) to service_role;

create or replace function public.kst_agent_mark(p_position uuid,p_bid numeric,p_quote timestamptz)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare p public.kst_agent_positions%rowtype; a public.kst_agent_accounts%rowtype;
 r numeric; exit_kind text; peak numeric; peak_r numeric; gross_r numeric; next_stop numeric;
begin
 -- Consistent lock order with the opener: account, then position.
 select * into p from public.kst_agent_positions where id=p_position;
 if not found then return jsonb_build_object('action','WAIT'); end if;
 select * into a from public.kst_agent_accounts where agent=p.agent for update;
 select * into p from public.kst_agent_positions where id=p_position for update;
 if p.state<>'OPEN' or p_bid<0 or p_bid is null or p_quote is null or p_quote<=p.quote_at or p_quote>now() or p_quote<now()-interval '5 minutes'
 then return jsonb_build_object('action','WAIT'); end if;
 r:=(p_bid*100*p.quantity-p.entry_cost)/p.entry_cost;
 peak:=greatest(coalesce(p.peak_bid,p.last_bid),p_bid);
 peak_r:=(peak*100-p.entry_cost)/p.entry_cost;
 gross_r:=(p_bid-p.entry_ask)/p.entry_ask;
 peak_r:=(peak-p.entry_ask)/p.entry_ask;
 next_stop:=case when p.agent='aggressive' and peak_r>=1 then floor(peak_r*2)/2 when peak_r>=1 then floor(peak_r*4)/4 when peak_r>=.75 then .75 when peak_r>=.50 then .50 when peak_r>=.40 then .40 when peak_r>=.30 then .30 else case when p.agent='aggressive' then -.25 else -.30 end end;
 if p.agent='aggressive' and peak_r>=.30 then next_stop:=greatest(next_stop,.85*peak_r); end if;
 exit_kind:=case when gross_r<=p.profit_stop_return then case when p.profit_stop_return<0 then 'OBSERVED_STOP' else 'PROFIT_LOCK_STOP' end when p_quote>=p.due_at then 'MEASUREMENT_HORIZON' else null end;
 update public.kst_agent_positions set last_bid=p_bid,quote_at=p_quote,peak_bid=peak,profit_stop_return=greatest(profit_stop_return,next_stop) where id=p.id;
 if exit_kind is not null then
  update public.kst_agent_positions set state='CLOSED',closed_at=p_quote,realized_pl=p_bid*100*p.quantity-p.entry_cost,exit_reason=exit_kind where id=p.id;
  update public.kst_agent_accounts set cash=cash+p_bid*100*p.quantity,realized_pl=realized_pl+p_bid*100*p.quantity-p.entry_cost,updated_at=now() where agent=p.agent;
  return jsonb_build_object('action','RESEARCH_CLOSE','reason',exit_kind);
 end if;
 return jsonb_build_object('action','RESEARCH_MARK');
end $$;
revoke all on function public.kst_agent_mark(uuid,numeric,timestamptz) from public,anon,authenticated;
grant execute on function public.kst_agent_mark(uuid,numeric,timestamptz) to service_role;
create or replace function public.kst_ai_progress()
returns jsonb language sql stable security invoker set search_path=public as $$
 select jsonb_build_object('mode','PAPER_RESEARCH_ONLY','feed_notice','Virtual simulations may use indicative quotes; no broker fills or calibrated win rates','generated_at',now(),'accounts',coalesce(jsonb_agg(jsonb_build_object(
 'agent',a.agent,'starting_balance',a.starting_balance,'cash',a.cash,'realized_pl',a.realized_pl,
 'equity',a.cash+coalesce((select sum(p.last_bid*100*p.quantity) from public.kst_agent_positions p where p.agent=a.agent and p.state='OPEN'),0),
 'unrealized_pl',coalesce((select sum(p.last_bid*100*p.quantity-p.entry_cost) from public.kst_agent_positions p where p.agent=a.agent and p.state='OPEN'),0),
 'closed_trades',(select count(*) from public.kst_agent_positions p where p.agent=a.agent and p.state='CLOSED'),
 'wins',(select count(*) from public.kst_agent_positions p where p.agent=a.agent and p.state='CLOSED' and p.realized_pl>0),
 'open_positions',coalesce((select jsonb_agg(jsonb_build_object('contract',p.contract,'opened_at',p.opened_at,'entry_ask',p.entry_ask,'entry_cost',p.entry_cost,'last_bid',p.last_bid,'quote_at',p.quote_at,'unrealized_pl',p.last_bid*100*p.quantity-p.entry_cost,'quantity',p.quantity,'model_version',p.model_version,'regime',p.regime,'feed',(select feed from public.kst_option_signals where id=p.signal_id),'stop_return',p.profit_stop_return)) from public.kst_agent_positions p where p.agent=a.agent and p.state='OPEN'),'[]'::jsonb),
 'last_decision',(select jsonb_build_object('created_at',d.created_at,'action',d.action,'reason',d.reason,'model_version',d.model_version,'regime',d.regime) from public.kst_agent_decisions d where d.agent=a.agent order by d.created_at desc limit 1),
 'updated_at',a.updated_at
 ) order by a.agent),'[]'::jsonb)) from public.kst_agent_accounts a;
$$;
revoke all on function public.kst_ai_progress() from public,anon,authenticated;
grant execute on function public.kst_ai_progress() to service_role;
create or replace function public.kst_capture_agent_outcome()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
 if new.state='CLOSED' and old.state='OPEN' and new.entry_cost>0 then
  insert into public.kst_agent_outcomes(id,created_at,closed_at,contract,features,outcome_return,feed)
  select new.id,new.opened_at,new.closed_at,new.contract,s.features,new.realized_pl/new.entry_cost,case when new.regime='DAILY_REQUIRED_RESEARCH' then 'paper_daily_exploration' when s.feed='opra' then 'paper_opra' else 'paper_indicative' end
  from public.kst_option_signals s where s.id=new.signal_id and s.feed in ('opra','indicative') and s.quality_label='QUALIFIED'
  on conflict(id) do nothing;
 end if;
 return new;
end $$;
revoke all on function public.kst_capture_agent_outcome() from public,anon,authenticated;
drop trigger if exists kst_capture_agent_outcome on public.kst_agent_positions;
create trigger kst_capture_agent_outcome after update on public.kst_agent_positions for each row execute function public.kst_capture_agent_outcome();

alter table public.kst_agent_accounts alter column starting_balance set default 1000;
alter table public.kst_agent_accounts alter column cash set default 1000;
update public.kst_agent_accounts set cash=cash+(1000-starting_balance),starting_balance=1000,updated_at=now() where starting_balance<>1000;

create or replace function public.kst_agent_add(p_position uuid,p_ask numeric,p_bid numeric,p_quote timestamptz)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare p public.kst_agent_positions%rowtype; a public.kst_agent_accounts%rowtype;
 cost numeric; absolute_stop numeric; average_entry numeric;
begin
 select * into p from public.kst_agent_positions where id=p_position;
 if not found then return jsonb_build_object('action','WAIT'); end if;
 select * into a from public.kst_agent_accounts where agent=p.agent for update;
 select * into p from public.kst_agent_positions where id=p_position for update;
 if p.agent<>'aggressive' or p.state<>'OPEN' or p.quantity>=3 or p.due_at<=now()
 or not public.kst_paper_strong_trend(p.signal_id)
 or extract(isodow from now() at time zone 'America/New_York')>5
 or (now() at time zone 'America/New_York')::time not between time '09:30' and time '15:59:59'
 then return jsonb_build_object('action','WAIT','reason','Scale-in requires a current strong trend and fewer than 3 contracts'); end if;
 if p_ask is null or p_bid is null or p_quote is null or p_bid<=0 or p_ask<p_bid
 or p_quote<p.quote_at or p_quote>now() or p_quote<now()-interval '60 seconds'
 or (p_ask-p_bid)/((p_ask+p_bid)/2)>.15
 or p_bid<coalesce(p.last_add_bid,p.entry_ask)*1.30
 then return jsonb_build_object('action','WAIT','reason','No fresh 30%-higher scale-in quote'); end if;
 absolute_stop:=p.entry_ask*(1+p.profit_stop_return);
 cost:=p_ask*100+(select fee_estimate from public.kst_option_signals where id=p.signal_id);
 if cost>a.cash or greatest(0,p_ask-absolute_stop)*100>a.cash*.02
 then return jsonb_build_object('action','WAIT','reason','Scale-in exceeds virtual cash or added stop-risk limit'); end if;
 average_entry:=(p.entry_ask*p.quantity+p_ask)/(p.quantity+1);
 update public.kst_agent_positions set quantity=quantity+1,entry_ask=average_entry,
 entry_cost=entry_cost+cost,last_add_bid=p_bid,quote_at=p_quote,last_bid=p_bid,
 profit_stop_return=absolute_stop/average_entry-1 where id=p.id;
 update public.kst_agent_accounts set cash=cash-cost,updated_at=now() where agent=p.agent;
 insert into public.kst_trade_activity(agent,position_id,action,contract,quote_at,quantity,price,reason)
 values(p.agent,p.id,'ADD',p.contract,p_quote,1,p_ask,'Virtual scale-in after fresh strong-trend confirmation; no broker fill');
 return jsonb_build_object('action','RESEARCH_ADD','reason','One virtual contract added; absolute stop preserved');
end $$;
revoke all on function public.kst_agent_add(uuid,numeric,numeric,timestamptz) from public,anon,authenticated;
grant execute on function public.kst_agent_add(uuid,numeric,numeric,timestamptz) to service_role;

create or replace function public.kst_post_paper_activity()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
 if TG_OP='INSERT' then
  insert into public.kst_trade_activity(agent,position_id,action,contract,quote_at,quantity,price,reason)
  values(new.agent,new.id,'ENTRY',new.contract,new.quote_at,1,new.entry_ask,'Virtual entry at observed source-feed ask; no broker fill') on conflict do nothing;
 elsif old.state='OPEN' and new.state='CLOSED' then
  insert into public.kst_trade_activity(agent,position_id,action,contract,quote_at,quantity,price,realized_pl,reason)
  values(new.agent,new.id,'EXIT',new.contract,new.quote_at,new.quantity,new.last_bid,new.realized_pl,new.exit_reason) on conflict do nothing;
 end if;
 return new;
end $$;
revoke all on function public.kst_post_paper_activity() from public,anon,authenticated;
