-- Draft for staging review. Do not run until broker OAuth provider approval.
-- Keep credentials out of these tables: only server-side secret-store references.
-- All broker account data is private; collective analytics is explicitly opt-in.

create table if not exists public.kst_broker_connections(
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 provider text not null check(provider in ('alpaca')),
 account_fingerprint text not null,
 credential_vault_ref text not null,
 read_enabled boolean not null default true,
 execution_enabled boolean not null default false check(execution_enabled=false),
 status text not null default 'PENDING' check(status in ('PENDING','CONNECTED','REVOKED','ERROR')),
 authorized_at timestamptz,
 revoked_at timestamptz,
 created_at timestamptz not null default now(),
 unique(user_id,provider,account_fingerprint)
);

create table if not exists public.kst_broker_learning_consent(
 user_id uuid primary key references auth.users(id) on delete cascade,
 learning_enabled boolean not null default false,
 consent_version text not null default 'v1-2026-11',
 consented_at timestamptz,
 revoked_at timestamptz,
 updated_at timestamptz not null default now(),
 check (not learning_enabled or (consented_at is not null and revoked_at is null))
);

create table if not exists public.kst_broker_fills(
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 connection_id uuid not null references public.kst_broker_connections(id) on delete cascade,
 broker_fill_id_hash text not null,
 symbol text not null,
 asset_type text not null,
 option_type text,
 order_side text not null,
 quantity numeric not null check(quantity>0),
 fill_price numeric not null check(fill_price>=0),
 filled_at timestamptz not null,
 created_at timestamptz not null default now(),
 unique(connection_id,broker_fill_id_hash)
);

create table if not exists public.kst_broker_signal_attribution(
 fill_id uuid primary key references public.kst_broker_fills(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 signal_id text,
 evidence_level text not null check(evidence_level in ('UNATTRIBUTED','POSSIBLE_MATCH','USER_SELECTED_SIGNAL')),
 evidence JSONB not null default '{}'::jsonb,
 detected_at timestamptz not null default now()
);

create table if not exists public.kst_broker_outcomes(
 fill_id uuid primary key references public.kst_broker_fills(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 closed_at timestamptz not null,
 realized_pnl numeric not null,
 verified_source text not null default 'broker_fill_and_close',
 analyzed_at timestamptz not null default now()
);

-- Service-only backend gateway; clients never receive broad access to
-- other users' broker fills or collective training observations.
do $$ declare name text; begin
 foreach name in array array[
  'kst_broker_connections','kst_broker_learning_consent','kst_broker_fills',
  'kst_broker_signal_attribution','kst_broker_outcomes'
 ] loop
  execute format('alter table public.%I enable row level security',name);
  execute format('revoke all on public.%I from public,anon,authenticated',name);
  execute format('grant select,insert,update,delete on public.%I to service_role',name);
 end loop;
end $$;

create index if not exists kst_broker_fills_by_user on public.kst_broker_fills(user_id,filled_at desc);
create index if not exists kst_broker_outcomes_by_user on public.kst_broker_outcomes(user_id,analyzed_at desc);

-- Before launch:
-- 1. Review foreign-key user ownership in service API; never accept user_id
--    from client request bodies.
-- 2. Put token encryption keys in a dedicated managed secret store;
--    a vault reference is not an access token.
-- 3. Add a consent revocation endpoint that disables learning and future
--    collection, removes retained training observations, and notes that
--    previously trained models cannot be guaranteed to unlearn immediately.
-- 4. Add account disconnect that revokes broker OAuth tokens on the provider.
-- 5. Verify deletion/export, rate limiting, credential rotation and audit logs.
-- 6. Keep execution disabled until approved, reviewed, and separately consented.
