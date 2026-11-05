-- Private chat. Apply in the existing Supabase project after enabling Auth.
create table if not exists public.kst_chat_conversations (
 id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
 title text not null, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists kst_chat_owner on public.kst_chat_conversations(user_id,updated_at desc);
create table if not exists public.kst_chat_turns (
 id uuid primary key, conversation_id uuid not null references public.kst_chat_conversations(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 user_text text not null, assistant_text text, status text not null default 'PENDING',
 sources jsonb not null default '[]'::jsonb, created_at timestamptz not null default now(), completed_at timestamptz
);
create index if not exists kst_chat_turn_owner on public.kst_chat_turns(user_id,created_at desc);
create index if not exists kst_chat_turn_search on public.kst_chat_turns using gin(to_tsvector('simple',user_text||' '||coalesce(assistant_text,'')));
create table if not exists public.kst_chat_memories (
 id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
 content text not null, created_at timestamptz not null default now()
);
create table if not exists public.kst_chat_quota (id text primary key, used integer not null default 0);
alter table public.kst_chat_conversations enable row level security;
alter table public.kst_chat_turns enable row level security;
alter table public.kst_chat_memories enable row level security;
alter table public.kst_chat_quota enable row level security;
-- Authenticated direct access is read-only. Mutations go through the authenticated chat server.
drop policy if exists kst_chat_owner_read on public.kst_chat_conversations;
create policy kst_chat_owner_read on public.kst_chat_conversations for select to authenticated using(user_id=auth.uid());
drop policy if exists kst_chat_turn_read on public.kst_chat_turns;
create policy kst_chat_turn_read on public.kst_chat_turns for select to authenticated using(user_id=auth.uid());
drop policy if exists kst_chat_memory_read on public.kst_chat_memories;
create policy kst_chat_memory_read on public.kst_chat_memories for select to authenticated using(user_id=auth.uid());
revoke all on public.kst_chat_conversations,public.kst_chat_turns,public.kst_chat_memories,public.kst_chat_quota from anon,authenticated;
grant select on public.kst_chat_conversations,public.kst_chat_turns,public.kst_chat_memories to authenticated;
grant select,insert,update,delete on public.kst_chat_conversations,public.kst_chat_turns,public.kst_chat_memories to service_role;
grant select,insert,update on public.kst_chat_quota to service_role;

create or replace function public.kst_chat_reserve(p_user uuid,p_daily integer,p_minute integer,p_global integer)
returns boolean language plpgsql security definer set search_path=public as $$
declare day_key text:=to_char(now() at time zone 'UTC','YYYY-MM-DD'); minute_key text:=to_char(now() at time zone 'UTC','YYYY-MM-DD-HH24-MI'); g text; d text; m text;
begin
 perform pg_advisory_xact_lock(842903);
 g:='global:'||day_key;d:=p_user::text||':'||day_key;m:=p_user::text||':'||minute_key;
 insert into public.kst_chat_quota(id) values(g),(d),(m) on conflict do nothing;
 if (select used from public.kst_chat_quota where id=g)>=least(greatest(p_global,1),2000)
 or (select used from public.kst_chat_quota where id=d)>=least(greatest(p_daily,1),100)
 or (select used from public.kst_chat_quota where id=m)>=least(greatest(p_minute,1),10) then return false;end if;
 update public.kst_chat_quota set used=used+1 where id in (g,d,m);return true;
end $$;
revoke all on function public.kst_chat_reserve(uuid,integer,integer,integer) from public,anon,authenticated;
grant execute on function public.kst_chat_reserve(uuid,integer,integer,integer) to service_role;

create or replace function public.kst_chat_search(p_user uuid,p_query text,p_exclude uuid)
returns table(user_text text,assistant_text text,created_at timestamptz)
language sql stable security definer set search_path=public as $$
 select t.user_text,t.assistant_text,t.created_at from public.kst_chat_turns t
 where t.user_id=p_user and t.conversation_id<>p_exclude and t.status='COMPLETE'
 and to_tsvector('simple',t.user_text||' '||coalesce(t.assistant_text,''))@@websearch_to_tsquery('simple',left(p_query,250))
 order by t.created_at desc limit 4;
$$;
revoke all on function public.kst_chat_search(uuid,text,uuid) from public,anon,authenticated;
grant execute on function public.kst_chat_search(uuid,text,uuid) to service_role;

-- r4: metadata only; original images are never stored in chat history.
alter table public.kst_chat_turns add column if not exists attachments jsonb not null default '[]'::jsonb;

-- Personal Request 3 archive. Server verifies Auth ownership and copies DB results.
create table if not exists public.kst_personal_suggestions (
 id uuid primary key,user_id uuid not null references auth.users(id) on delete cascade,
 request_id text not null,category text not null,budget numeric not null,
 contracts jsonb not null default '[]'::jsonb,created_at timestamptz not null default now(),
 unique(user_id,request_id)
);
create index if not exists kst_personal_suggestions_owner on public.kst_personal_suggestions(user_id,created_at desc);
alter table public.kst_personal_suggestions enable row level security;
drop policy if exists kst_personal_suggestions_read on public.kst_personal_suggestions;
create policy kst_personal_suggestions_read on public.kst_personal_suggestions for select to authenticated using(user_id=auth.uid());
revoke all on public.kst_personal_suggestions from anon,authenticated;
grant select on public.kst_personal_suggestions to authenticated;
grant select,insert,update,delete on public.kst_personal_suggestions to service_role;

alter table public.kst_personal_suggestions add column if not exists request_status text not null default 'DONE';
-- Atomically queue shared research work and record the private ownership link.
create or replace function public.kst_queue_personal_request(p_user uuid,p_id uuid,p_request text,p_category text,p_budget integer)
returns boolean language plpgsql security definer set search_path=public as $$
begin
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,842911));
 if exists(select 1 from public.kst_personal_suggestions where user_id=p_user and request_id=p_request) then return true;end if;
 if (select count(*) from public.kst_personal_suggestions where user_id=p_user and created_at>=now()-interval '1 minute')>=3
 or (select count(*) from public.kst_personal_suggestions where user_id=p_user and created_at>=now()-interval '1 day')>=50 then return false;end if;
 insert into public.kst_signal_requests(id,category,budget,created_at,status) values(p_request,p_category,p_budget,now(),'PENDING') on conflict do nothing;
 insert into public.kst_personal_suggestions(id,user_id,request_id,category,budget,request_status)
 values(p_id,p_user,p_request,p_category,p_budget,'PENDING') on conflict do nothing;
 return true;
end $$;
revoke all on function public.kst_queue_personal_request(uuid,uuid,text,text,integer) from public,anon,authenticated;
grant execute on function public.kst_queue_personal_request(uuid,uuid,text,text,integer) to service_role;
