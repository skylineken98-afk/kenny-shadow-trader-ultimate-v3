# V3 chart-first market discovery update — Oct 19, 2026

## What changed
- Dashboard and asset tabs present candlestick charts with labeled support/resistance, EMAs, volume, and VWAP on the 0DTE 5-minute chart. Raw JSON technical outputs are no longer the main UI.
- Request a Signal does NOT demand a manually specified ticker: it discovers US exchange-listed ticker symbols from Nasdaq Trader listing files, then **samples a configurable 60–400 symbols** from the listing universe, uses recent daily pricing/turnover to shortlist up to 18, and checks multi-timeframe trend and available real options chains. Each of 0DTE, Swings and LEAPS returns up to three eligible contract cards with an underlying chart (5-minute, daily, weekly respectively).
- Option cards show vendor-provided contract symbol and quote snapshots; each contract is independently verified against its chain. If the data fails the filters, there will be fewer than 3. There are no fabricated contracts. Option contract OHLC price charts are NOT included: the displayed candles are for the underlying stock/ETF.

## Important constraints
- **Not a simultaneous whole-market scan**, not real-time streaming, and not guaranteed subsecond quotes. Full coverage requires an appropriate licensed tick/history/options feed, a symbol-universe screening backend, scheduled scans, caching, storage and compute. Free vendor limits can prevent results.
- Do not confuse a quote's last-trade time with bid/ask update time. Premium stops/targets are **not** inferred from underlying prices.
- To rotate what is sampled, use the universe rotation offset. Screening a single subset cannot guarantee the globally best 3 contracts.
- This patch does not activate broker executions, notifications, self-learning, 24/7 feed ingestion, or option-level chart histories.

## Installation and safety
1. Back up the V3 GitHub repository. Copy extracted files into V3 repository root and replace matches. Do not touch V2.
2. Verify no credential values are included in `.env.example` or other committed files; store keys privately.
3. Commit and push V3. Its Streamlit instance should redeploy `app.py`.
4. Test the market discovery with 60 symbols first; 400 may take multiple minutes, and Yahoo free services may throttle it.
5. Read the displayed number of scanned symbols and provider notices before interpreting its Top 3 as a market-wide ranking.
6. Leave live orders disabled. Keep the existing V2 Railway scanner and Supabase project unchanged.

## Validation
Python compiled; 16 existing `tests/` tests passed with `PYTHONPATH=.`. Internet-executed market scanning, UI runtime, Yahoo rate-limits, streaming and data licensing were NOT independently verified in this offline environment.
