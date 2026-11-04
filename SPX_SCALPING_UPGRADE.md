# Shadow Trader V3 — additive SPX scalping upgrade

## Included

- `tradingview/Shadow_Trader_SPX_Aggressive_v6.pine` — stand-alone Pine Script v6 indicator to paste into TradingView **Pine Editor** and add to an SPX **1-minute** chart. Built with 1H trend, 15m recent-candle zone approximation, 1m confirmed structure break, optional liquidity sweep and volume filter, session VWAP, early proximity alerts and risk/reward boxes (minimum 1.5R). Setup includes green/red theoretical *index price* reward/risk boxes, not option premiums.
- `core/spx_scalping.py` — **candle-derived** rolling volume-by-price histogram and pressure. This is neither tick-weighted volume profile nor actual bid/ask footprint/delta or options flow.
- Streamlit dashboard: an optional SPX scalping lab expander with SPY (ETF), ^GSPC (index), and QQQ OHLCV choices. It discards the newest possibly incomplete 1m bar and does not place orders.
- `tests/test_spx_scalping.py` — additional offline tests for the research helpers.

## TradingView install and validation

1. Open TradingView and select the **SPX** symbol and **1m** timeframe. Open Pine Editor, paste all of `tradingview/Shadow_Trader_SPX_Aggressive_v6.pine`, save, and click **Add to chart**.
2. Create separate alerts for **Early bullish/bearish zone proximity** and **Confirmed bullish/bearish 1m entry**. Choose *once per bar close* for confirmed alerts. Proximity alerts may change during the currently forming 1m candle.
3. Watch 1H / 15m completed candles and subsequent 1m triggers in Replay. A confirmed signal is marked only on a completed 1m candle; no future bars are used. The 15m zone is a **previous completed candle low/high**, not a validated institutional order block.
4. Keep volume filter OFF on SPX cash index unless the data source has useful volume. The background tint is a candle-based pressure proxy, **not** real bid/ask delta. VWAP is a reference and may not be meaningful on volume-less index data.
5. Backtest separately with historical slippage, latency, spreads, commissions, event volatility, multiple market regimes and out-of-sample days. An `indicator` does not provide a strategy tester P&L, and this package has no demonstrated trading edge.

## Not implemented / dependencies

- No paid options sweep, OPRA, footprint, dark-pool, or true level-2 order-flow source; any label suggesting real options flow would be misleading.
- No real 3D heatmap or weighted 3-day **tick volume profile**; the Streamlit version approximates a volume histogram using each candle's typical price.
- No broker-bound live option scalping, order submission, stops or portfolio execution. Risk controls in prior files must not be represented as a production-grade live trading risk engine.
- Pine code has not been compiled on TradingView from this offline environment. Verify installation and any TradingView runtime warnings before use.

## Verify and deploy

```bash
python -m pytest -q tests/
python -m compileall -q app.py core workers
streamlit run app.py
```

Preserved existing V3 code, settings and prior V2 integration. Existing Railway worker activation settings were not changed; no live mode enabled. Do not put secrets into repositories or client-side Streamlit code.
