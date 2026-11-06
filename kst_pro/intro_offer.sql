-- KST intro promotion redemption ledger. Apply with service-role migration privileges.
-- ENZO and MAYVI are mutually exclusive: at most one successful intro per user.
alter table public.kst_billing_sessions add column if not exists intro_code text;
create table if not exists public.kst_intro_redemptions(
 user_id uuid primary key references auth.users(id) on delete cascade,
 code text not null check(code in ('ENZO','MAYVI')),
 state text not null check(state in ('RESERVED','REDEEMED')),
 reserved_until timestamptz not null,
 checkout_session_id text,
 redeemed_at timestamptz,
 created_at timestamptz not null default now()
);
alter table public.kst_intro_redemptions enable row level security;
revoke all on public.kst_intro_redemptions from anon,authenticated;
grant select,insert,update,delete on public.kst_intro_redemptions to service_role;

create or replace function public.kst_reserve_intro(p_user uuid,p_code text)
returns boolean language plpgsql security definer set search_path=public as $$
declare prior public.kst_intro_redemptions%rowtype;
begin
 if p_user is null or p_code not in ('ENZO','MAYVI') then return false;end if;
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,84622));
 select * into prior from public.kst_intro_redemptions where user_id=p_user for update;
 if found and (prior.state='REDEEMED' or prior.reserved_until>now()) then return false;end if;
 insert into public.kst_intro_redemptions(user_id,code,state,reserved_until,checkout_session_id,redeemed_at)
 values(p_user,p_code,'RESERVED',now()+interval '40 minutes',null,null)
 on conflict (user_id) do update set code=excluded.code,state='RESERVED',
 reserved_until=excluded.reserved_until,checkout_session_id=null,redeemed_at=null;
 return true;
end $$;

create or replace function public.kst_release_intro(p_user uuid,p_code text)
returns boolean language plpgsql security definer set search_path=public as $$
begin
 -- Used only after an unsuccessful Stripe checkout session creation.
 delete from public.kst_intro_redemptions
 where user_id=p_user and code=p_code and state='RESERVED' and checkout_session_id is null;
 return found;
end $$;

create or replace function public.kst_redeem_intro(p_user uuid,p_code text,p_session text)
returns boolean language plpgsql security definer set search_path=public as $$
declare current_session public.kst_billing_sessions%rowtype;
begin
 if p_user is null or p_code not in ('ENZO','MAYVI') or p_session is null then return false;end if;
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,84622));
 select * into current_session from public.kst_billing_sessions where id=p_session and user_id=p_user and intro_code=p_code;
 if not found then return false;end if;
 update public.kst_intro_redemptions set state='REDEEMED',checkout_session_id=p_session,
 redeemed_at=now(),reserved_until=now()
 where user_id=p_user and code=p_code and state='RESERVED';
 return found;
end $$;

revoke all on function public.kst_reserve_intro(uuid,text), public.kst_release_intro(uuid,text), public.kst_redeem_intro(uuid,text,text) from public,anon,authenticated;
grant execute on function public.kst_reserve_intro(uuid,text), public.kst_release_intro(uuid,text), public.kst_redeem_intro(uuid,text,text) to service_role;
