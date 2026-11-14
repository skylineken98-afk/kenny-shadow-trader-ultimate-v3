# KST research in each member's ChatGPT and Claude

Prepared November 14, 2026. Development change based on draft PR #13.
No production activation is implied by a deployed process or passing unit tests.

## User experience

Each member connects from their own ChatGPT or Claude, signs in with their own
KST account, and consents to read-only research access. Existing registered free
KST accounts remain eligible; there is no membership gate in this connector.
The assistant reads KST's stored signals, market pulse, earnings, headlines,
historical outcomes, or the requesting member's own entered records. It can
explain that evidence conversationally. It cannot access other chats, place
orders, edit KST, or run fresh scans in this release.

`get_learning_context` packages evidence for momentum, sector rotation,
options risk, or personal trade review. It returns teaching guidance plus source
records, not an LLM-generated recommendation. Each underlying source retains its
existing projection, ownership filter, time checks and limitations. Missing
sources are explicitly unavailable. Historical examples are not fresh signals.
The interface makes no OpenAI or Anthropic model API calls, so users converse in
their own assistant; KST hosting and data-provider costs still apply.

## Operator configuration

Keep the current Supabase project, read-only role and token hook from PR #13.
No new database table, role, RLS policy, token scope or mutation permission is
introduced by this change. Review the existing hook and grants before release.

1. Enable the Supabase OAuth server and set its consent UI to this service's
   `/oauth/consent`. Verify the existing token hook is installed and selected.
2. Register a separate OAuth client for each assistant and record the exact
   callback URI supplied by that assistant. Use PKCE S256. Do not insert guessed
   clients directly into auth tables or use a shared personal bearer token.
3. Approve the real clients in the existing private KST registry; configure
   `KST_MCP_CLIENT_IDS` with their actual IDs. Keep registration bounded to the
   reviewed clients, rather than allowing arbitrary client enrollment.
4. Set `KST_MCP_CLIENT_REDIRECTS` to a JSON object mapping each actual approved
   client ID to its exact registered HTTPS callback URI(s). No query, fragment,
   credentials or wildcard is accepted in registered callback configuration.
   ChatGPT's callback must come from its actual setup flow, not this document.
   Claude currently documents `https://claude.ai/api/mcp/auth_callback`.
5. `KST_MCP_ALLOWED_ORIGINS` can contain `https://chatgpt.com,https://claude.ai`;
   do not use `*`. Server-to-server requests with no Origin still authenticate.
6. After database role, hook and client configuration are verified, enable the
   connector for a controlled live test using two separate member accounts.
   Verify both assistants, allow/deny, renewal, expiry/revocation, and attempts
   to read another member's records or mutate any exposed table/RPC.
7. Confirm licensed data scope permits the specific research returned to
   external assistants. Obtain required provider/publication review for wider
   distribution; custom connector tests do not imply directory approval.

The callback map is configuration, never accepted from URL parameters. The
browser checks exact HTTPS origin/path and, once a client is identified, binds
redirects to that client. This prevents allowing an entire provider domain as
an open redirect. Missing callback setup makes consent configuration fail closed.
The old connector's database isolation and account/client-bound JWT validation
remain mandatory. Adding Claude's callback does not itself authorize a user.

## Connection instructions after activation

Server URL: `https://kst-mcp-production.up.railway.app/mcp`.

- ChatGPT: add KST through the account's supported custom app/plugin setup,
  select OAuth and use the registered client configuration. Availability depends
  on the account/workspace and distribution route. Follow the actual setup UI.
- Claude: Customize → Connectors → Add custom connector; enter the server URL,
  then use the registered OAuth client and sign in with a KST account. An
  organization administrator may need to add the connector first.

Example member questions:
- Explain what KST's sector rotation evidence means and how old it is.
- Teach me momentum using KST's latest stored market overview.
- Explain SPY option risk using fresh candidates and labeled historical examples.
- Review my own saved trade plan and identify what evidence is missing.

If data is unavailable, the assistant should explain the concept generally and
state it lacks a verified KST example. It must not fabricate a quote or win rate.

## Production audit observed November 14

- Railway kst-mcp runs commit a9e8eef from the PR #13 branch.
- `/health`: running, read_only=true, enabled=false.
- Supabase OAuth discovery: HTTP 404, feature_disabled, OAuth server disabled.
- Database counts: 0 OAuth clients, 0 OAuth consents, 0 approved KST clients.
- Dashboard redirects this browser to Supabase sign-in. Connected Supabase tools
  can inspect the database but expose no OAuth server settings/client-management
  operation, so dashboard authentication is needed to finish that setup.

These are observed blockers, not completed activation steps. Never set the
enable flag as a substitute for client registration and verified isolation.

## Local verification

```
python -m unittest discover -s tests_mcp -v
cd kst_mcp
node --test callbacks.test.js
npm ci --ignore-scripts
npm run build
```

Official references checked:
- https://developers.openai.com/plugins/build/auth
- https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication
