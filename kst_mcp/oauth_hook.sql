-- REVIEWED TEMPLATE ONLY: do not apply over an existing token hook without composing it.
-- Register real ChatGPT client ID/resource below only after production URLs are known.
-- No existing grants, user rows, policies, memberships or auth settings are changed.
create schema if not exists kst_connector_private;
revoke all on schema kst_connector_private from public, anon, authenticated;
create table if not exists kst_connector_private.clients (
 client_id text primary key,
 resource text not null check(resource like 'https://%/mcp'),
 enabled boolean not null default false
);
alter table kst_connector_private.clients enable row level security;
revoke all on kst_connector_private.clients from public, anon, authenticated;
grant usage on schema kst_connector_private to supabase_auth_admin;
grant select on kst_connector_private.clients to supabase_auth_admin;
create policy auth_admin_read_clients on kst_connector_private.clients
 for select to supabase_auth_admin using (true);

create or replace function kst_connector_private.access_token_hook(event jsonb)
returns jsonb language plpgsql stable security invoker set search_path = '' as $$
declare claims jsonb := event->'claims'; client text; audience text;
begin
 client := coalesce(event->>'client_id', claims->>'client_id');
 -- Remove this connector's privilege unless the trusted client registry grants it.
 claims := claims - 'kst_mcp_access';
 if client is not null then
  select resource into audience from kst_connector_private.clients
   where client_id=client and enabled=true;
  if audience is not null then
   claims := jsonb_set(claims, '{aud}', to_jsonb(audience));
   claims := jsonb_set(claims, '{kst_mcp_access}', '"read"'::jsonb);
   claims := jsonb_set(claims, '{client_id}', to_jsonb(client));
   claims := jsonb_set(claims, '{exp}', to_jsonb(least((claims->>'exp')::bigint, extract(epoch from now())::bigint+300)));
  end if;
 end if;
 return jsonb_set(event, '{claims}', claims);
end;
$$;
revoke all on function kst_connector_private.access_token_hook(jsonb) from public, anon, authenticated;
grant execute on function kst_connector_private.access_token_hook(jsonb) to supabase_auth_admin;
