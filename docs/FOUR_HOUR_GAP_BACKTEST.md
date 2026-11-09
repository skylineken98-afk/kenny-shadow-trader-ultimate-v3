# 4H gap sweep/reclaim — experimental v1

A testable KST interpretation of the uploaded CS Trades recording, not an exact replication or validated edge. The objective consolidation-high/low break replaces discretionary trendlines.

## Rules

Use separate completed 4H context and 1-minute trigger bars. CSV header: `timestamp,open,high,low,close`; timestamps are timezone-aware bar OPEN times. Supply one symbol per dataset. Use provider-defined 4H boundaries consistently; do not blindly resample across market sessions. Gaps across missing 4H intervals are excluded.

A bearish three-candle 4H gap (third high below first low) is an overhead long target; reverse for shorts. Use the latest eligible gap available before the sweep, at most 48 hours old. Price must close below the overhead gap (above for shorts). Reject a gap whose far edge was already traversed in the supplied trigger history. Supply trigger history from before zone formation for meaningful mitigation checks.

Sweep the prior 20 trigger-bar low and close back above it; reject candles sweeping both ends. Freeze that range, gap and sweep low. Within ten subsequent bars, close above the frozen range high without revisiting the sweep low. Reverse for shorts. Enter at the next contiguous bar open only if reward/risk remains at least 1.5. Stop at the sweep extreme. Test midpoint and far-edge targets as separate hypotheses. Hold at most 60 bars. One position at a time. If a candle hits stop and target, assume stop first. Adverse opening gaps fill at the worse open; favorable target gaps receive only the target. Fees and slippage default to five basis points each per side, deducted from returns. These are configurable estimates, not broker quotes. Data gaps close at the last observed close; inspect these records separately.

## Run

From repository root, using only Python's standard library:

```sh
python -m core.fvg_gap_backtest --context data/SPY_4h.csv --triggers data/SPY_1m.csv --phase historical --target midpoint --output historical.json
python -m core.fvg_gap_backtest --context data/SPY_4h.csv --triggers data/SPY_1m.csv --phase holdout --entry-from 2026-10-01T00:00:00+00:00 --target midpoint --output holdout.json
python -m unittest discover -s tests -p test_fvg_gap_backtest.py -v
```

Choose the holdout boundary before examining results. Keep warmup data before it. Do not tune parameters using holdout outcomes. Reports contain source hashes, parameters, trade records, net unit returns, net R, win rate and expectancy; zero trades produce null rates. The `paper` phase label records provenance only: it does not install a worker or schedule runs. Store each phase under a distinct output filename. No historical market dataset or strategy performance is bundled. Unit fixtures are synthetic and are not trading results.

## Limits and next integration

This module is an explicit CSV research runner, separate from dashboard scanning and broker execution. No scheduler, automatic promotion, or production deployment is enabled. OHLC cannot establish intrabar ordering or actual fills. Short returns omit borrow/margin. Session calendars, position sizing, portfolio equity/drawdown, VWAP, 1H/15M filters and option contract simulation are not implemented here. Compare those as separately specified follow-up experiments.

To measure option-premium targets and the -25% stop, supply historical contract-level bid/ask quotes, expirations, strikes, liquidity and fees. Underlying returns must never be presented as option returns. Run historical and untouched holdout datasets, inspect data-gap exits, then forward paper-test with the same frozen rules before considering promotion.
