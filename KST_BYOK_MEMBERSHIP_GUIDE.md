# KST paid market research + customer-funded AI

## Revenue and cost boundaries

KST membership is for the user's authorized access to the proprietary scanner, option research, sector rotation, alerts and analysis. The AI provider bill is separate and belongs to the user. ChatGPT, Claude and Gemini consumer subscriptions do NOT automatically pay developer API bills. There is no integration with personal ChatGPT conversation history or saved memories.

**No authenticated user's AI request may ever use KST's OPENAI_API_KEY or any operator-owned model credential as a fallback.** The server now rejects a message before any model request unless a valid provider key was supplied for that request. Never place user keys in the database, source code, browser localStorage, URLs, logs, error responses, or chat history.

### How the web/mobile chat front end must connect

1. User signs in to KST (Supabase Auth). The backend validates their token and conversation ownership.
2. User selects OpenAI, Anthropic (Claude) or Google (Gemini) in *Connect my AI*.
3. User pastes an API key into a password-type connection field on the authenticated **HTTPS** site. Display plain-language separate provider billing disclosures. Do **not** ask users to paste API keys into the chatbot message.
4. Keep the key only in ephemeral, in-memory page state; do not save it in localStorage, cookies, analytics, error reports or the KST database. It must be reentered after reload.
5. For each POST /api/chat/message or /api/chat/stream send the selected provider in JSON `ai_provider`; send the key in the private `X-KST-User-AI-Key` header. The existing proxy must forward this header unmodified, over TLS, without storing or logging it. The backend accepts only signed-in users, preserves X-KST-Proxy validation, and rate limits by owner-verified user UUID.
6. Do not proxy credentials to unapproved hosts or model endpoints. No key = no response and no provider charge. The server never uses its own owner key.
7. For consumer plans without API credits, provide instructions to create and fund a developer API project, without promising account subscriptions will work.
8. The full chat includes KST's recent source-tagged research snapshot. The request is sent to the selected third-party AI company under that user's provider account. Inform the user that their questions and relevant KST research excerpts will be sent to their chosen provider.

**Browser/Cloudflare frontend must be updated before this interface can be used.** The backend alone is insufficient. A production release should include a tested connection field and proxy header forwarding; no screenshots or claims of completed user connection before this.

## Paid KST access control

The user-provided API key does **not** grant KST access on its own. The existing authenticated membership check on POST /api/chat/message runs before the research snapshot or external AI call. Turn on `MEMBERSHIP_ENFORCED=true` when paid memberships launch, with verified Stripe webhook and plan access. Keep authenticated conversation privacy, owner-scoped memories and research routes. Do not expose service-role Supabase credentials, internal tables or proprietary scanner research as a public endpoint.

The current beta may keep `MEMBERSHIP_ENFORCED=false` intentionally. Charging users requires separately testing plan eligibility, revoked passes and missing entitlements across all research endpoints. A paywall cannot be guaranteed solely by updating Chat.

## Cost containment

Provider key and usage quota belong to the user's API project. KST must not advertise that ChatGPT Plus or Claude Pro pays usage. KST still pays for its own infrastructure, news/data licensing, Supabase usage, scanning and hosting; enforce fair use and per-user request quotas on those resources too. The app caps response output tokens and limits requests. This system is not a calibrated trading strategy and never places brokerage orders.

## Verification and safe rollout

- CI tests verify provider identity, key isolation, no site-owner fallback, user-scoped history, membership enforcement when enabled, and read-only trading.
- Before merging or deploying, confirm that the frontend has implemented the ephemeral user key field and checked how Cloudflare forwards sensitive request headers.
- Remove or blank `OPENAI_API_KEY` from the KST chat Railway service after verifying the frontend path; ensure unrelated services using their own keys are not altered.
- Perform a live test with a user-controlled, restricted API key and validate that the user's provider dashboard—not the site owner's—records usage. Never print or log real keys.
