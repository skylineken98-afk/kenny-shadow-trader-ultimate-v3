# Video strategy research

All candidates are research hypotheses inspired by user-uploaded clips, not exact replicas or verified profitable systems. Alpha Insider's strategy creator is a workflow reference, not a trading strategy.

| Candidate | Current state |
| --- | --- |
| Swing liquidity sweep and reclaim | Implemented OHLCV approximation: sweep prior 20 completed bars, reclaim on a directional candle, next-open entry, fixed five-bar hold |
| Asia/London/New York session sweep | Registered; needs explicit session calendars, timezones/DST, completed-session levels and entry rules |
| Sharp-drop reversal | Registered; needs measurable drop threshold and entry confirmation |
| Heavy absorption plus volume profile | Registered; needs aggressor-side trades/bid-ask data and exact thresholds; never infer verified absorption from OHLCV |

`core.video_strategy_lab` provides candidates, causal sweep decisions, a cost-aware simulation and append-only JSONL run storage. It is not connected to the production scanner or a scheduler. Historical, holdout and paper runs are labeled separately. No market backtests or paper results were fabricated or run as part of adding this module.

Before enabling ongoing testing:
1. Freeze each version's rules and dataset snapshot. Add swing-sweep stop/target variants separately; current simulation is a fixed-hold baseline and does not implement KST's 1H/15M/1M strategy or option stops.
2. Supply licensed historical data. For SPX session/flow studies specify ES/SPY proxies explicitly; do not attribute their traded volume to the index.
3. Test chronological holdouts with warmup and entries restricted to the holdout. Account for parameter selection and overlapping samples.
4. Add fills, spread, fees, slippage, stop-gap handling and intrabar ambiguity. Options require historical contract quotes; underlying returns are not option returns.
5. Wire a persistent worker to evaluate completed bars, deduplicate observations, record actual quote-based paper entries/exits and append outcomes. Paper phase labeling alone does not implement a paper engine.
6. Compare expectancy, drawdown, trade count, profit factor, costs and performance by session/regime to the existing baseline. Require review before promotion; keep losers and failed versions.

Run unit checks: `python -m pytest tests/test_video_strategy_lab.py -q`. These use synthetic bars solely for correctness; they provide no evidence of profitability.
