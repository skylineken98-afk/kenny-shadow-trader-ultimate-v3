-- Additive least-privilege OAuth role. No inherited authenticated/anon privileges.
-- No OAuth clients are registered/enabled by this script.
do $$ begin
 if not exists(select 1 from pg_roles where rolname='kst_mcp_reader') then
  create role kst_mcp_reader nologin noinherit nosuperuser nocreatedb nocreaterole noreplication nobypassrls;
 end if;
end $$;
grant kst_mcp_reader to authenticator;
grant usage on schema public to kst_mcp_reader;

create schema if not exists kst_connector_private;
revoke all on schema kst_connector_private from public, anon, authenticated;
grant usage on schema kst_connector_private to kst_mcp_reader, supabase_auth_admin;
create table if not exists kst_connector_private.clients (
 client_id text primary key,
 resource text not null check(resource like 'https://%/mcp'),
 enabled boolean not null default false
);
alter table kst_connector_private.clients enable row level security;
revoke all on kst_connector_private.clients from public, anon, authenticated;
grant select on kst_connector_private.clients to kst_mcp_reader, supabase_auth_admin;
drop policy if exists auth_admin_read_clients on kst_connector_private.clients;
create policy auth_admin_read_clients on kst_connector_private.clients for select to supabase_auth_admin using(true);
drop policy if exists connector_read_clients on kst_connector_private.clients;
create policy connector_read_clients on kst_connector_private.clients for select to kst_mcp_reader using(enabled);

create or replace function kst_connector_private.allowed()
returns boolean language sql stable security invoker set search_path='' as $$
 select exists (
  select 1 from kst_connector_private.clients c
  where c.enabled and c.client_id=(nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'client_id')
   and c.resource=(nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'aud')
   and (nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'kst_mcp_access')='read'
   and (nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role')='kst_mcp_reader'
 );
$$;
revoke all on function kst_connector_private.allowed() from public, anon, authenticated;
grant execute on function kst_connector_private.allowed() to kst_mcp_reader;

grant select(id,contract,underlying,expiration,option_type,strike,category,created_at,entry_ask,entry_bid,quote_at,feed,score,quality_label,context_label,state,last_bid,last_quote_at,closed_at,outcome_return) on public.kst_option_signals to kst_mcp_reader;
grant select(symbol,report_date,timing,source,fetched_at,active) on public.kst_earnings to kst_mcp_reader;
grant select(title,url,source,published_at,fetched_at) on public.kst_news to kst_mcp_reader;
grant select(id,user_id,symbol,quantity,entry,stop,target,state,last_bid,quote_at,created_at) on public.kst_personal_positions to kst_mcp_reader;

do $$ declare t text; begin
 foreach t in array array['kst_option_signals','kst_earnings','kst_news','kst_personal_positions'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('drop policy if exists kst_connector_select on public.%I',t);
  if t='kst_personal_positions' then
   execute format('create policy kst_connector_select on public.%I for select to kst_mcp_reader using ((select kst_connector_private.allowed()) and user_id=(nullif(current_setting(''request.jwt.claims'',true),'''')::jsonb->>''sub'')::uuid)',t);
  else
   execute format('create policy kst_connector_select on public.%I for select to kst_mcp_reader using ((select kst_connector_private.allowed()))',t);
  end if;
 end loop;
 -- Existing projects without market pulse remain unavailable; do not invent a table or rows.
 if to_regclass('public.kst_market_pulse') is not null then
  grant select(id,observed_at,payload) on public.kst_market_pulse to kst_mcp_reader;
  alter table public.kst_market_pulse enable row level security;
  drop policy if exists kst_connector_select on public.kst_market_pulse;
  create policy kst_connector_select on public.kst_market_pulse for select to kst_mcp_reader using((select kst_connector_private.allowed()));
 end if;
 -- Refuse activation if PUBLIC exposes privileged RPC functions to this new role.
 if exists(select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
           where n.nspname='public' and p.prosecdef and has_function_privilege('kst_mcp_reader',p.oid,'EXECUTE')) then
  raise exception 'Public SECURITY DEFINER RPC privileges require review before adding the connector role';
 end if;
end $$;
