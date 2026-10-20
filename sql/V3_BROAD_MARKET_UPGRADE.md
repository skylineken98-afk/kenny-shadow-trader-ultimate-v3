# V3 broad-market and affordable options upgrade

- Exchange-listed stock discovery no longer defaults to the first 3,000 symbols.
- Each scan rotates over the universe in bounded chunks (120–1,000 listed symbols per pass) to avoid pretending a free feed can simultaneously refresh every US option contract.
- Prescreen accepts stocks at or above $0.50 and five-day average traded notional at or above $250,000/day (the former minimums were $2 and $2 million). This may include smaller tickers, but it does not mean every penny stock has listed options.
- Selects up to 40 underlyings per pass for 4H/1H/5M confluence and option-chain discovery rather than 18.
- User budget is $5–$3,000 per standard 100-share option contract at indicative ask, with existing spread, volume, open interest and last-trade recency safeguards. Bid/ask timestamps are unverified and indicative.
- No options buy signal is fabricated; only vendor-reported contracts with confirmed trend alignment are displayed. Some passes/categories may show zero results.
- To inspect further names, advance the rotation offset by the sample size and run again. Current dashboard results are for a single pass, not globally proven Top 3 across all listed stocks.
- This is research-only: no real broker orders or auto-trading activated.
