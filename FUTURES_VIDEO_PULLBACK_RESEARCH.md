# NQ/MNQ video-inspired trend-pullback strategy v1

**State:** isolated research module on a development branch. Not wired to the public KST scanner, a scheduled worker, Telegram alerts, paper broker, or live execution. It does not replicate an unverified video's exact rules.

**Mechanical hypothesis:** On contiguous completed 5-minute NQ/MNQ OHLCV, evaluate EMA(20) versus EMA(50). For longs, EMA20 above EMA50, the previous candle touches or crosses EMA20 but closes above EMA50, and the current completed bullish candle closes above the previous high. Reverse conditions for shorts. Observe only after candle close, simulate entry at following open. Warm up 55 bars, prohibit overlapping positions, exit at a fixed 3 bars by default. This is a baseline, **not** a claimed profitable strategy.

**Futures costs:** NQ $20/point, MNQ $2/point; model per-side fees plus tick slippage, with tick size 0.25. P&L is dollars per number of contracts, *not* underlying percentage return. Configure actual broker commissions separately.

**Known limitations:** No exchange/session calendar, contract roll/corporate mapping, historical data provider, stops or targets, gap/slippage distribution, bid/ask spreads, margin, prop-firm drawdown rules, fill certification, or out-of-sample performance yet. Input must be contiguous 5-minute candles; split by session. No actual historical testing has been performed on licensed futures data.

**Next validation:** Acquire licensed timestamped NQ/MNQ historical bars, split sessions and instrument contracts correctly, freeze parameters, execute historical and walk-forward holdouts with rollover and realistic fills, compare against buy/hold and existing KST futures hypotheses; then add signal-only paper monitoring behind a disabled-by-default feature flag. No customer or brokerage routing without explicit later approval.

**Offline correctness tests:** `python -m pytest tests/test_futures_video_pullback.py -q`.
