# Private assistant connector test candidate

Production remains unchanged. This branch combines PR #28 with main at 34b6be6 and hardens early callback redirects. Do not attach this branch to production or enable production OAuth as part of preparation.

## Local checks

```
python -m venv .venv-mcp
.venv-mcp/bin/pip install -r kst_mcp/requirements-dev.txt
.venv-mcp/bin/python -m unittest discover -s tests_mcp -v
cd kst_mcp
npm ci --ignore-scripts
node --test callbacks.test.js
npm run build
```

## Required before an isolated live test

Use a separate Supabase project and connector service with explicitly labeled sample data and accounts A and B. Do not share production credentials. Review reader_role.sql and compose oauth_hook.sql with existing hooks. Audit every exposed table/RPC, not just MCP sources. Keep dynamic registration off. The source contains no real registered client IDs or verified ChatGPT callback.

The operator must sign in to the Supabase dashboard, verify OAuth availability, select the reviewed hook, and register separate actual ChatGPT and Claude clients using S256 PKCE. Obtain exact callbacks from each assistant setup. Approve those IDs in the private registry. Match registry resource, KST_MCP_RESOURCE, KST_MCP_CLIENT_IDS and KST_MCP_CLIENT_REDIRECTS. Never insert guessed clients into auth tables. Keep KST_MCP_ENABLED=false until these checks pass. The same flag gates consent configuration and data access, so an end-to-end test requires enabling the isolated service only.

Required environment: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, KST_MCP_RESOURCE (exact HTTPS /mcp URL), KST_MCP_CLIENT_IDS, KST_MCP_CLIENT_REDIRECTS (JSON mapping IDs to exact HTTPS callback lists), KST_MCP_ALLOWED_ORIGINS (explicit origins), KST_MCP_ENABLED. No service-role or assistant model API key.

## Test matrix — run each row in both assistants

| Case | Expected evidence |
| --- | --- |
| Missing/invalid callback config | Consent unavailable, no navigation |
| Wrong-client callback / early redirect without client details | Rejected, including previously authorized flows |
| Deny before Allow | No usable grant; correct callback/state; no personal read |
| Allow as A, then B in a separate browser session | Correct client and member displayed; matching token subject |
| Token claims | Verified signature/issuer, exact resource audience, registered client, non-anonymous UUID, kst_mcp_reader, read claim, expiry no more than 300 seconds |
| Refresh | Same subject/client/audience/role; rotation/replay behavior recorded |
| Account isolation | A sees only A records; B only B; cross-user arguments rejected; repeat after refresh/account switch |
| Direct Data API and website routes | No foreign rows, writes, billing access or privileged RPCs |
| Stale or missing evidence | Explicitly unavailable; historical examples never fresh signals |
| Disconnect, consent revoke, client disable (separate tests) | Record whether refresh stops and remaining access lifetime; registry disable removes DB access |
| Expired/replayed/wrong-audience tokens | Rejected |

Record timestamp, candidate SHA, assistant, test account alias, outcome and sanitized error for each case. Never record authorization codes, passwords, bearer/refresh tokens or client secrets. Successful unit tests do not prove live isolation or provider publication approval.

## Cleanup and rollback

Disable the isolated connector, revoke test consents and refresh grants, disable/remove disposable clients and registry approvals, and remove sample accounts/data. Verify refresh fails and data calls are disabled. Preserve only sanitized results. Do not change production Site URL, hook, OAuth setting, deployment source or enable flag. Public rollout additionally requires reviewed privacy/support/terms and market-data redistribution rights.
