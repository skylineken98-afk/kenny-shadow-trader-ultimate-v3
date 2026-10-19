# Feature delivery matrix — audited upgrade

**This is a functioning research foundation and additive upgrade, NOT a completed live trading SaaS.**
The ZIP contains original source preserved and newly added separated research/paper candidate code.

| Capability | Status | Caveats / requirements |
|---|---|---|
| Railway background scanner | Existing working installation (preserved) | Your confirmed production logs show successful Supabase 201 inserts; cannot test live credentials in this ZIP |
| Supabase `ultimate_signals` | Existing working installation; dashboard now reads correct table | Requires server-only Supabase credentials; service role not public |
| 4H/1H/5M confluence, levels, RVOL | Rule-based implemented | Yahoo bars; 4H resampling approximate; no validated trading edge |
| Options chains | Research utility included | Yahoo option-chain snapshots, prices not guaranteed fresh; no broker option execution |
| News classification | Implementation present, unverified | OpenAI key and paid usage, news source access, API schema verification |
| Read-only research profiles (5) | Implemented | Rule-based not independent self-learning AI |
| Automatic multi-agent paper candidate recording | Added, **opt-in only** | Separate worker and SQL migration; CANDIDATE_ONLY not executed fills |
| Intrabar conservative target-vs-stop evaluation | Added helper | No market replay scheduling or accurate event reconstruction |
| Paper position order fills/P&L | Not automated | SQL stores positions; requires market data, spread/fees, position scheduler and reconciliation |
| Win/loss summary functions | Added helpers | Only calculate over trustworthy *closed* simulation rows; not live performance |
| Eight market research tabs + more | Existing dashboard, preserved | Not all tab features fully implemented |
| Futures / forex simulated contracts | Not implemented | Instrument specs, FX pips, session hours, margin, reliable licensed feed |
| Crypto simulated fills | Basic manual ledger, no autonomous execution | 24/7 worker research data, exchange liquidity, mark-to-market needed |
| Challenge ledger & reset handling | Research profile placeholder only | Account ledger, liquidation, independent bot state, goal tracking missing |
| Historical learning / champion/challenger | Not implemented | Dataset, walk-forward split, leakage checks, promotion gates |
| Dark pool/Unusual Whales/institutional flows | Not integrated | Paid/licensed feed, terms and keys required |
| FRED macro | Key may exist outside ZIP, no verified live wiring | FRED key and macro ingestion worker required |
| Robinhood watchlist add + notifications | Intent placeholder only | Authorized supported API/permissions and messaging provider needed |
| Automated real-money orders | NOT implemented; disabled | Supported broker, explicit authorization, independent compliance/risk checks, kill switch, reconciliation and substantial testing |
| Public multi-user accounts and payments | NOT implemented | Supabase Auth, RLS policies, Stripe, legal/privacy review |
| Conversational AI assistant | Not implemented | Model/API, tool permissions, prompt/data isolation and testing |
| Performance claims | None supported | Do not imply 98% win rate or 10% guaranteed daily gains |

Never interpret a SETUP, signal, or CANDIDATE_ONLY row as a fill or realized return.
