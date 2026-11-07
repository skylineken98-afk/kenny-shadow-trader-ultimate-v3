# KST read-only ChatGPT connector

## Status — November 7, 2026

Implemented as a separate service in `kst_mcp`; NOT publicly enabled, deployed or submitted.
Existing KST services and database policies are not replaced. Account access is available to
all registered users once enabled; there is no paid-membership gate on these connector tools.
Data licensing/redistribution permissions still require verification before public access.

Verified inspection: KST's live Supabase project has the signals, earnings, news and personal
positions columns used here. `kst_market_pulse` was absent from the inspected information_schema
result, so that tool may return unavailable until its existing migration is installed. The public
OAuth discovery endpoint returned HTTP 404 `feature_disabled`: OAuth server is disabled.
The selected tables had no client RLS policies; this connector therefore uses carefully bounded,
projected server-side GETs. Its service credential never goes to ChatGPT or the browser.

## Implemented

* Stateless Streamable HTTP `/mcp`, JSON-RPC initialize/ping/tools, no arbitrary queries or writes.
* Seven tools: search/explain signals, market overview, earnings research, recorded outcomes,
  personal records and headline links. No broker credentials, imported private fills or admin data.
* JWT signature, issuer, resource audience, expiry, account UUID, approved OAuth client,
  authenticated role, non-anonymous account and `kst_mcp_access=read` validation.
* Ownership filtering uses the verified token subject, never a model-supplied user ID.
* Every result has retrieval time and limitations; stale executable-looking prices are suppressed.
  News/calendar results are not presented as company-confirmed facts. No fabricated performance.
* A dedicated consent page at `/oauth/consent`, using existing KST email/password accounts.
  Passwords are sent directly to Supabase Auth; browser sessions remain in memory.
  Existing social-only users can set a password through KST's account recovery first.
* Token rejection on the website API prevents MCP tokens authorizing its mutation routes.
* Origin validation, request/concurrency limits, no sensitive request logs, per-account limits.
* No OpenAI API key is required: this server returns data to the user's ChatGPT. It makes no
  OpenAI model calls and does not provide access to the user's other ChatGPT conversations.

## Deployment configuration

Create a dedicated `kst-mcp` Railway service in the existing KST project. Point its config file
to `railway-mcp.json`, source branch to this change, and use `Dockerfile.mcp`. One replica initially.
Do not change the existing chat/options/pro workers' start commands or share their API routes.

Required server-only settings:

```
SUPABASE_URL=<existing project URL>
SUPABASE_SERVICE_ROLE_KEY=<existing secret, via Railway reference>
SUPABASE_PUBLISHABLE_KEY=<public project key>
KST_MCP_RESOURCE=https://<connector-host>/mcp
KST_MCP_CLIENT_IDS=<approved ChatGPT OAuth client UUIDs>
KST_MCP_ALLOWED_ORIGINS=https://chatgpt.com
KST_MCP_ENABLED=false
```

`/health` reports process health, not verified OAuth/data readiness. `false` disables data calls
and consent sign-in. The server requires valid configuration even while disabled.
There are no hardcoded production hostnames/client IDs. Only publishable configuration is
exposed at `/oauth/config` when enabled. Never place the service credential in that endpoint.

## Remaining activation steps (required, not completed)

1. Assign the dedicated service an HTTPS hostname. Establish a verified privacy policy,
   support contact, terms and market-data redistribution coverage.
2. Enable Supabase OAuth server. Configure its authorization UI URL to the connector's
   `/oauth/consent`. Keep dynamic client registration off initially.
3. Register the ChatGPT OAuth client using the EXACT production redirect URI shown in
   ChatGPT's integration management page. Require S256 PKCE. Record its actual client UUID.
   The consent page only permits callbacks to `https://chatgpt.com`.
4. Review `kst_mcp/oauth_hook.sql`. It is an unapplied template, not a migration.
   Compose with any existing token hook instead of replacing it. Register the client/resource
   in its private registry and activate the composed custom access-token hook. This gives
   the connector a dedicated audience, read claim and maximum five-minute access lifetime.
   Test the actual hook event shape and required claims against the live project first.
5. Audit ALL exposed table/RPC grants and RLS, not just the connector's seven sources.
   OAuth tokens must not mutate other Data API tables or RPCs. Existing website routes now
   reject OAuth tokens; inspect other entry points before enabling the client.
6. Ensure account email confirmation and non-anonymous token claims are configured. Verify
   discovery metadata, issuer, resource handling and PKCE from ChatGPT end to end.
7. Test consent Allow/Deny, refresh, disconnect/revocation and both accounts' isolation.
   Access-token revocation is bounded by five-minute expiry; instant revocation is not claimed.
   Revoking an OAuth client must stop refresh. Compare revoked and expired behavior in practice.
8. Only after these pass, set `KST_MCP_ENABLED=true`, test in ChatGPT privately and record the
   review walkthrough. Submit through OpenAI's developer publishing flow. Publication is
   subject to OpenAI approval and client plan/workspace/region availability.

## Validation

```
python -m venv .venv-mcp
.venv-mcp/bin/pip install -r kst_mcp/requirements-dev.txt
.venv-mcp/bin/python -m unittest discover -s tests_mcp -v
cd kst_mcp
npm ci --ignore-scripts
npm run build
```

The consent SDK and bundler are pinned with a lockfile. Server requirements are isolated from
the main app. No package upgrades are applied to existing workers. Automated unit/HTTP tests
are not a substitute for the two-account live OAuth test or OpenAI approval.

Validation completed in this change: 32 connector and existing chat tests passed; consent
JavaScript bundled successfully. Docker build and live OAuth end-to-end tests were not run.

## Public review material to finalize

Name: **Kenny Shadow Trader (KST)**. Description: Read-only market research, recorded signal
outcomes, earnings calendars and personal KST records. No brokerage execution or guaranteed returns.

Positive cases (run with a dedicated reviewer account and genuine or explicitly labeled sample data):
1. “Show KST swing signals under $500.” Expected: search_signals; fresh matches or explicit no data.
2. “Explain this KST signal.” Expected: explain_signal with a real signal UUID, timestamps/limitations.
3. “Where may momentum be rotating?” Expected: get_market_overview; price/volume estimates, no fund-flow claims.
4. “Which earnings dates are coming up?” Expected: get_earnings_research, source/date uncertainty shown.
5. “Show my saved positions.” Expected: get_my_records, reviewer-owned rows only.

Negative cases:
1. “Edit the scanner or buy this contract.” No available write/execute tool; explain read-only access.
2. “Read another member's positions.” Reject user_id arguments and return only verified subject rows.
3. “Give me a current price from yesterday's quote.” Suppress stale pricing; say unavailable.

Required owner/account inputs still outstanding: actual public connector URL and registered client ID,
approved privacy/support/terms URLs, dedicated reviewer account and walkthrough. Do not submit
placeholders, someone else's account, private secrets or fabricated test outcomes.

Official references checked:
* https://developers.openai.com/plugins/build/auth
* https://developers.openai.com/plugins/deploy/submission
* https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication
* https://supabase.com/docs/guides/auth/oauth-server/token-security
* https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
