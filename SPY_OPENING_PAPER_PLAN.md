# KST SPY 9:32 Opening Momentum Paper Bot

This supersedes SPX for the opening scalper. **Status: research decision module only; NOT deployed, NOT wired to live quote ingestion, and NOT a daily active bot.**

- Underlying: SPY; choose a same-day SPY CALL when bullish price momentum scores higher, or same-day SPY PUT when bearish momentum scores higher. No trade if signal is ambiguous.
- First eligible entry 09:32 America/New_York (using the most recent **completed** one-minute candle, e.g. the 09:31 bar at 09:32); latest opening entry 09:59, hard exit requested 10:00 ET. Do not force a trade.
- Compare EMA9/EMA21, VWAP, prior bar breakout and close direction. 1H and 15m context recorded without veto.
- $1,000 simulated starting equity; one contract only if ask*100 + fees <= 10% of current equity, 10% daily loss guard, at most 3 positions; fail closed for absent fresh bid/ask or candle close timestamps.
- Initial stop 25% of option-premium entry, exit on momentum weakening, 10:00 cutoff. Future integration must include progressive profit-stop ladder at observed +30%, +40%, +50%, +75%, +100%.
- Candidate and exit decisions are **not fills**. To activate: (1) validate live 1m SPY bar feed + exchange calendar, (2) verify Alpaca OPRA options entitlement and valid same-day OCC contracts, spreads, option ask/bid timestamps, (3) integrate paper ledger idempotency and persistent state for restart, (4) verify closing marks and 10:00 retry+alert on missing quotes, (5) enforce allocation and loss caps in execution adapter, (6) run offline tests, backtest, and shadow-mode monitoring, (7) deploy dedicated paper worker after verifying. All real-money trading remains OFF.

This branch does NOT yet provide data fetch, paper ledger integration, scheduler, real-time reconciliation or orders. Existing KST scanning and other services are unchanged.
