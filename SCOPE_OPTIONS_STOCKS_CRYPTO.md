# Shadow Trader V3 — Options, Stocks, Crypto only

## Active coverage
- **Options:** 0DTE, short-term swings, LEAPS; equity and ETF underlying scans, with SPX research lab. Contract discovery is read-only and must verify quotes, liquidity, expiration, bid/ask, and actual broker eligibility. SPX cash index is not the same price as SPY.
- **Stocks / ETFs:** momentum, trend, breakout/retest, sector rotation, fundamentals/news, and risk-aware research.
- **Crypto:** spot BTC, ETH, SOL and selected liquid coins, 24/7 research, volume and structure signals. Derivatives and leveraged futures are outside scope.

## Explicit exclusions
- Futures (including NQ, ES, MNQ, MES), forex, leveraged crypto perpetuals, FX strategies, futures prop-account workflows.
- Futures and forex tabs removed from the Streamlit UI; stock/crypto paper-recording controls reject these asset classes. Configured `SCAN_SYMBOLS` drops Yahoo futures (=F), FX (=X) and index-only (^...) symbols. Option contract chains are discovered separately.
- Legacy integration/reference code may still contain futures/forex identifiers; it is retained for backward compatibility but is not activated by the main dashboard or scanner.

## Execution status
No live broker order submission is enabled by these changes. The simplified paper ledger covers only stocks and spot crypto; options need a contract-multiplier, Greeks, liquidity and fill model before it can represent fills. No automatic options, stock, or crypto trading has been enabled.

## Deployment
Replace the deployed code with this package and restart Streamlit / Railway workers. Check `SCAN_SYMBOLS` in Railway/Streamlit secrets: use listed stocks/ETFs and crypto symbols like `BTC-USD`; the scanner now filters unsupported contracts. Historic Supabase records remain untouched, including any past forex/futures rows.
