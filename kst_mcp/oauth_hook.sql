-- Apply reader_role.sql first. Compose with any existing hook; never overwrite it blindly.
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
   claims := jsonb_set(claims, '{role}', '"kst_mcp_reader"'::jsonb);
   claims := jsonb_set(claims, '{client_id}', to_jsonb(client));
   claims := jsonb_set(claims, '{exp}', to_jsonb(least((claims->>'exp')::bigint, extract(epoch from now())::bigint+300)));
  end if;
 end if;
 return jsonb_set(event, '{claims}', claims);
end;
$$;
revoke all on function kst_connector_private.access_token_hook(jsonb) from public, anon, authenticated;
grant execute on function kst_connector_private.access_token_hook(jsonb) to supabase_auth_admin;
