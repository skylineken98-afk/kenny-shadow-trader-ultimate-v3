# V3 consolidated opportunity-intelligence upgrade

This ZIP includes the earlier broad-universe screening, options-chain discovery, candle-based flow estimates, and SEC/FINRA read-only connectors, plus `core/opportunity_intelligence.py`.

`rank_opportunities(contracts, evidence_by_ticker, limit=3)` accepts **real, already-discovered** options candidates and returns distinct top bullish calls and bearish puts. Evidence is explicitly labeled: OHLCV pressure is only a proxy; FINRA short-interest context has **zero directional score**; SEC company filings do **not** themselves provide intrinsic valuation. A defensible separately computed and dated fair-value model must be supplied before the valuation feature contributes.

The module is pure, read-only, and offline-testable. It **is not yet integrated with a continuously operating Railway worker, data ingestion scheduler, chart dashboard, or Supabase publishing pipeline**. No trade orders, paid feed subscriptions, live institutional money flows, or self-learning models were activated. Previous configured Alpaca/FRED credentials are untouched.

The research-only scores are heuristics rather than probabilities of success. Stale quotes and illiquid options can invalidate practical execution. Risk and public distribution licensing must be checked separately.

To validate after extraction: `python -m unittest discover -s tests -v`. Ignore the archived V2 integration directory during V3 test discovery.
