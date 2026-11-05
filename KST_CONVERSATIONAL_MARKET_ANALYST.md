# KST Conversational Market Analyst — research enhancement

KST Chat remains a natural-language, user-facing assistant. It can discuss SPX,
AAPL, sector trends, bearish and bullish swing setups, option candidates, and
market regime using existing time-stamped KST database evidence. It is NOT a
complete real-time market intelligence feed, nor a guarantee of trading edge.

## Added in this branch
- Data-focused candidate retrieval for swing/options and trend questions.
- Scope queries to explicitly named tickers at the database query layer.
- De-duplicate contract candidates to avoid counting repeated budget-scans as independent evidence.
- Label bid/ask age and indicative quotes; no quote is marked executable or broker-verified.
- Prioritize current *direction-aligned* candidates over stale/countertrend
  candidates; scores are research heuristics, not success probabilities.
- Add 4h/1h/5m technical context, RVOL, underlying entry/stop/target.
- Provide citations via KOPT and KSET IDs, and rules to separate underlying risk
  from option Greeks, gaps, liquidity and expiration.
- Continue existing conversation history, user authentication, memory retrieval,
  private account isolation and chat quota enforcement. No broker actions.

## Scope limits and next production steps
1. Run all GitHub CI tests and review source/authorization paths.
2. Merge only after review, and deploy the KST Chat service with working API
   credentials; inspect production logs to confirm snapshot retrieval succeeds.
3. Connect licensed quote sources including options volume, open interest,
   bid/ask and Greeks; KST's indicative quotes are **not** an execution feed.
4. Add verified earnings/news/macroeconomic event coverage, with dates,
   sources, freshness limits and license review.
5. Verify assistant answers on representative prompts with known correct
   benchmarks, including stale data and missing quotes.
6. Keep advice distinct from automated trading, and maintain read-only
   controls. User data is never shared to public prompts or a different user.

This PR provides a **foundation**, not comprehensive global market coverage.
