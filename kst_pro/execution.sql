-- Dedicated owner-account execution ledger; never accessible to website users.
create table if not exists public.kst_execution_control(
 id text primary key,killed boolean not null default true,day text,day_start_equity numeric,updated_at timestamptz not null default now()
);
create table if not exists public.kst_execution_intents(
 client_id text primary key,account_id text not null,symbol text not null,asset_type text not null,
 side text not null,quantity integer not null check(quantity>0),limit_price numeric not null check(limit_price>0),
 reserved_value numeric not null,state text not null default 'RESERVED',broker_id text,filled_qty numeric not null default 0,
 filled_avg_price numeric,plan jsonb not null,created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
alter table public.kst_execution_control enable row level security;alter table public.kst_execution_intents enable row level security;
revoke all on public.kst_execution_control,public.kst_execution_intents from anon,authenticated;
grant select,insert,update on public.kst_execution_control,public.kst_execution_intents to service_role;
create or replace function public.kst_reserve_execution(p_row jsonb,p_exposure numeric,p_equity numeric,p_day text,p_allocation numeric,p_max_trade numeric,p_max_loss numeric)
returns boolean language plpgsql security definer set search_path=public as $$
declare c public.kst_execution_control%rowtype;pending numeric;baseline numeric;value numeric:=(p_row->>'reserved_value')::numeric;
begin
 perform pg_advisory_xact_lock(842915);
 select * into c from public.kst_execution_control where id=p_row->>'account_id' for update;
 if not found then return false;end if;
 if exists(select 1 from public.kst_execution_intents where client_id=p_row->>'client_id') then return false;end if;
 baseline:=c.day_start_equity;
 if c.day is distinct from p_day then update public.kst_execution_control set day=p_day,day_start_equity=p_equity where id=c.id;baseline:=p_equity;end if;
 if p_row->>'side'='buy' then
  select coalesce(sum(reserved_value),0) into pending from public.kst_execution_intents where account_id=c.id and state not in ('filled','canceled','expired','rejected','done_for_day','replaced');
  if c.killed or p_equity<=0 or baseline is null or baseline-p_equity>=p_max_loss or value<=0 or value>p_max_trade or p_exposure+pending+value>p_allocation then return false;end if;
 end if;
 insert into public.kst_execution_intents(client_id,account_id,symbol,asset_type,side,quantity,limit_price,reserved_value,plan)
 values(p_row->>'client_id',c.id,p_row->>'symbol',p_row->>'asset_type',p_row->>'side',(p_row->>'quantity')::integer,(p_row->>'limit_price')::numeric,value,p_row->'plan');return true;
end $$;
revoke all on function public.kst_reserve_execution(jsonb,numeric,numeric,text,numeric,numeric,numeric) from public,anon,authenticated;
grant execute on function public.kst_reserve_execution(jsonb,numeric,numeric,text,numeric,numeric,numeric) to service_role;
