# KST Evidence-Driven Option Rankings

This branch extends option ranking beyond bid/ask spread, delta, and premium cost.

## Actual fields
- **Contract volume**: 1Day Alpaca option aggregate (`v`); only same-day bar is used as current session volume. Last trade size and bid/ask sizes are NOT substituted.
- **Open interest**: Alpaca Trading API contract details (`open_interest` and `open_interest_date`), checked for a reasonably recent date. If unavailable, report unknown.
- **Relative/unusual volume**: current 1Day option-contract volume divided by mean volume over 3–5 previous observed daily bars. `>=2x` is a **research proxy**, not a vetted anomaly, institution detection, or delta-adjusted buy pressure. Sparse history is unknown.
- **Volume/OI ratio**: descriptive only; does not identify buyer versus seller.
- **Sector-relative strength**: latest completed daily closes versus a sector ETF over five completed sessions. For puts, weakness relative to sector is favorable; for calls, strength is favorable. This is not live sector cash flow.
- **Structural signals**: original spread/delta/affordability features retained.

## Ranking arithmetic
Original structural score remains an ingredient. New evidence score is a bounded heuristic:
- 70% structural baseline
- 7 points from observed contract volume (normalized at 500)
- 7 points from open interest (normalized at 1000)
- 8 points from contract relative volume (normalized at 2x)
- 3 points from volume/OI (normalized at 1x)
- 5 points from direction-aligned sector-relative strength (normalized at 3 percentage points)

If a metric is missing, its component remains neutral at baseline/100, not zero and not maximum. `risk_snapshot.ranking_evidence` saves actual measurements, provenance, missing count, original score and methodology for audit. **Not a success probability.** The new ranking is exploratory and must be backtested before promotion into automatic strategy performance claims.

## Data feed constraints
- Alpaca snapshot feed contains bid/ask, last trade and Greeks but not daily volume or OI, so the implementation reads *different* endpoints: options historical daily bars and Trading API contract details.
- In `indicative` feed, derived quotes/trades are delayed or modified; do not label executable real-time order prices.
- Enrich up to **two leading qualified contracts per scanned ticker per cycle** to limit requests, not all market options. Candidate data completeness is explicitly exposed to chat; other options still receive structural-only scores.
- The multi-sector universe rotates bounded batches; data-provider entitlements, access limits and pagination can reduce coverage.
- The code is read-only; no brokerage execution, credentials, order permissions or subscriptions are modified.

## Release checks
1. Confirm GitHub CI and unittest checks, including missing/invalid source data.
2. Stage against real Alpaca account entitlements and record historical-bar + paper contract metadata errors, quotas, call duration.
3. Verify score output and evidence in `kst_option_signals.risk_snapshot.ranking_evidence`, alongside feed, timestamp and schema validation.
4. Validate no stale metadata claimed fresh; compare live OPRA vs indicative and do not silently substitute feeds.
5. Review score impact across symbols, budgets and expirations; backtest outside the training sample.
6. Merge scanner and Chat PRs once verified; deploy without enabling real trading.
