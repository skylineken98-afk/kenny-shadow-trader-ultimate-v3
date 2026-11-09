# SPX Opening Momentum Paper Scalper — development proposal

**Mode:** research and paper-only. Not connected to a production scheduler or broker; no fills are claimed.
All times US/Eastern (DST aware), weekdays only; exchange holiday/early-close calendar MUST be enforced by the host scheduler before enabling.

* 9:30–9:31 ET: analyze the opening range and review confirmed 1H direction / 15M zone.
* First eligible entry at **9:32 ET**, never before; evaluate every completed 1-minute candle through 9:59 ET.
* Calls only in bullish 1H + 15M alignment, EMA9 above EMA21, close above VWAP and prior completed minute's high; reversed criteria for puts. Skip rather than forcing a daily trade.
* Require independent completed-candle 1H/15M feeds, reward/risk >= 1.5, and fresh timestamped executable option bid/ask (the decision module consumes a 'fresh_quote' flag, it does NOT validate that flag).
* Simulated position size: max 10% of $1,000 initial paper equity per trade (or lower current-equity budget), max 3 simultaneous positions, daily-loss guard 10%. Enforce allocation in the future execution adapter, **not in this decision module**.
* Initial stop is 25% of entry option premium. Momentum exit: EMA9/EMA21 cross, SPX close crosses VWAP against the position, or a 1m close moves against position relative to prior 1m close. These are deliberately sensitive research exit rules.
* Exit by **10:00 ET at latest**, including a mandatory retry/alert if a valid quote is temporarily unavailable. Do not mark a position closed or invent a price if no real bid is available. The exit module yields EXIT_REQUIRED, not a fill.
* Future adapter should trail stops after +30, +40, +50, +75 and +100% verified option-bid profit thresholds; record progressive exits and avoid claiming the top was caught. These stops are **not yet implemented** by this branch.
* Record entry ask, exit bid, spread, quote timestamps, costs, realized simulated P/L, the exact entry/exit reason, and rejects in a persistent paper ledger. **Integration pending.**
* No live broker execution, no changes to worker environment flags, secrets, production or kill switches.

## Scope of this branch

Pure SPX opening entry/exit decision logic and deterministic offline tests. Does **not** install a daily schedule, fetch real options data, maintain persistent positions, or activate paper trading. Those integrations must be separately verified before claiming daily operation.
