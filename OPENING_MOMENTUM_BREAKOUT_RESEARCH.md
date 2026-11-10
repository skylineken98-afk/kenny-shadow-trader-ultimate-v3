# Opening Momentum Reclaim & Breakout — paper-only research

**State:** isolated research branch. Not connected to the production scanner, scheduler,
Telegram, broker, or any automatically armed paper executor. No deployments or live trades.

## Rule definition (v1)
- Use completed and chronologically ordered underlying OHLCV candles, one consistent
  1–5-minute interval, anchored at the regular-session 09:30 ET opening bar.
- Require a directional opening body of at least 0.2%.
- Require 2–6 pullback candles that do not violate the opening impulse by more than
  60% of its range and that have not already closed beyond the opening extreme.
- Bullish: final candle closes **above** the opening high with strong bullish body.
  Bearish: final candle closes **below** the opening low with strong bearish body.
- Closing strength must be >=65% of candle range toward the breakout end.
- Breakout bar volume must be >=1.3x the mean volume of pullback bars.
  This is **candle-derived relative volume**, not verified order flow or
  exchange-normalized same-time-of-day RVOL.
- Underlying stop is the pullback low/high; the initial underlying research
  target uses 1.5x the underlying distance to the stop. These levels are **not**
  option premium levels. Historical results do not imply option profitability.
- No 4H, 1H or 5M trend consensus required. A consistent OHLCV sampling interval
  is still necessary to evaluate volume and opening structure.

## Option candidate planner and safeguards
`paper_option_plan` provides an advisory candidate only, never an order or a fill.
It validates last completed candle freshness (<=120 sec), real-time timestamped
contract-specific bid/ask (<=60 sec), OCC symbol, call/put direction, expiration,
bid/ask spread, regular market session, maximum 10% allocation, maximum 10% daily
drawdown, maximum three positions and chosen dollar budget. Uses illustrative
option ask premium stop at -25% and first actionable target at +40% (1.6 RR
before fees), **not** the underlying stop. This does not use an actual execution
system; stops are not guaranteed.

## Backtest and evidence
`backtest` records a decision on the completed breakout, assumes an underlying
entry at the **next** bar's open and an exit at a subsequent bar's close after a
chosen hold window. Includes round-trip basis-point transaction-cost assumptions.
At most one opening pattern per session, no lookahead, no auto-promotion. Output
reports **underlying returns**, not options fills, slippage-adjusted option
returns, or broker-verified P&L. It does not download data.

`append_performance` writes JSONL run snapshots with immutable dataset ID,
phase (historical/holdout/paper), parameters, individual records and timestamps.
Paper option fills require a separately validated durable ledger and real quotes.

## Tests
Run `python -m pytest -q tests/test_opening_momentum_breakout.py`.
The test suite uses synthetic OHLCV only and checks both directions,
unconfirmed bars, breakout and volume failures, chronology, quote/budget/risk
guards, next-bar entry, cost validation and JSONL persistence.

## Remaining approval gate
Obtain licensed point-in-time intraday equities and options data and run
train/holdout and multi-day market-regime tests; verify skip reasons,
option spreads, fill assumptions, opportunity counts and paper outcomes.
Integrate with the persistent runner ONLY after an explicit separate approval,
and keep broker execution physically disabled. Do not deploy this PR.
