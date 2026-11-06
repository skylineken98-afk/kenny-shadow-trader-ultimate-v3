# Signal outcome audit — November 6, 2026

## Winner definition

A signal wins if its sampled bid-based return is positive at the same day's
regular 4 p.m. New York close, OR a +50% return is first observed before a
−30% stop. Those reasons are reported separately. A stop-first signal that
recovers to a positive close is a positive-close winner under this definition;
that does not mean a trader following the stop would have won.

`daily_signal_outcomes.sql` is read-only and reproducible. It uses the earliest
record for each contract/New York date, excluding repeated budget records.
Closing references must be observed in the last five minutes before 4 p.m.;
missing closing evidence stays unresolved. This is a closing reference,
not necessarily the official closing auction or last tradable option price.

Initial snapshot: 202 winners (152 positive-close, 50 target-first), 569 losses,
6 flat, 393 missing closing references, 10 entry-time flags. Among the 777
classified records including flat outcomes, winners account for about 26.0%.
This differs from the former deadline-based counts and must not be combined
with them. The dataset contains only November 5–6 and indicative feed quotes.

## Findings and changes

- Prior alignment labels accepted setup creation times up to 90 minutes old.
  New alignment requires creation within five minutes and an actual completed
  five-minute underlying bar closing within ten minutes. Missing bar timestamps
  produce STRUCTURAL_ONLY, not a confirmed alignment.
- Trend EMA/ATR inputs previously included forming candles. New frames exclude
  forming bars and persist actual bar-close timestamps.
- New candidate entries require option quotes within 60 seconds, checked again
  after enrichment. Greeks and IV still lack independently verified timestamps.
- Live tracking records the first sampled +50%/−30% crossing separately inside
  risk_snapshot.observed_barrier. Horizon outcomes and historical records remain
  unchanged. Existing legacy crossing flags are marked PRIOR_ORDER_UNKNOWN.
- `signal_outcomes.sql` compares original horizon results with observed barrier
  ordering; its gap diagnostic includes overnight/market-closure gaps.

## Ranking and learning limits

No countertrend bonus or new learned model is justified by these two days.
Baseline quality ranking remains explicitly heuristic. Stale/unknown context
cannot receive an alignment preference. Indicative observations remain excluded
from model promotion and probability calibration. Extreme returns are audit
candidates, not verified fills; current evidence cannot validate historic quotes
against an independent entitled market-data feed.

All barrier results are sampled observations. A missing observation may hide an
earlier stop or target, and a gap-through price is not a guaranteed fill at the
threshold. Repeated contracts across days and common market moves are correlated.
A proper strategy comparison needs longer forward data, chronological holdout,
spread/fee/slippage checks, average returns, and coverage reported with win rate.

## Profit-lock update

Kenny subsequently set target one to +30%, followed by +40%, +50%, +75%,
+100%, and additional 25-percentage-point steps. The daily audit now uses
+30% for its target-first criterion; the initial snapshot above used +50%
and is retained as historical context, not the current win rate.

New monitoring records use risk_snapshot.profit_lock with a monotonic stop
reference at the highest crossed milestone. A later sampled bid at or below
the prior stop records an observed research exit, including the actual sampled
return if it gaps below the stop. It does not submit or modify broker orders.
The ladder uses gross premium returns, excluding fees, and starts when the
tracker initializes. Prior data is not retroactively assigned a stop exit.
The fixed +50%/-30% observed_barrier remains a separate legacy comparison.

## Website scoreboard and paper research

Apply `kst_options/scoreboard.sql` and `kst_options/paper_profit_lock.sql` after
`schema.sql`. Both were applied and verified on November 6. The scoreboard
is service-role-only and the public Worker exposes its fixed research projection.
It includes winners, losers, missing evidence, and major winners ranked by
observed peak (not realized profit). The initial-stop/target count is distinct
from the subsequent profit-lock ladder exit and daily close reference.

From this release, new option signal records carry exit_policy=profit-lock-v1
and track until their sampled ladder exit or expiration, rather than ending
all swing observations after 24 hours. Historical horizons are preserved.

Paper agents can evaluate both OPRA and indicative feeds with matching source
labels; indicative outcomes are stored as paper_indicative and remain ineligible
for model promotion. Virtual accounts, one-position limits, risk fractions,
cooldowns, and daily loss limits are unchanged. No stale or out-of-session
entry is forced. Their SQL marker uses the same 30/40/50/75/100/25-point ladder.

Each paper agent starts with $1,000 virtual cash. There is no one-entry daily cap; additional qualified entries are allowed after exits, subject to the existing cooldowns, one-open-position rule, cash, risk, and daily loss limits. No daily trade count is guaranteed.

Daily paper-entry mandate: from 15:45 ET, an agent without an entry that day
can use a clearly labeled DAILY_REQUIRED_RESEARCH exploration from the best
fresh, qualified affordable contract, even without directional alignment.
Premium is capped at $100, estimated stop risk at 3% of cash, and existing
loss limits remain. Missing valid quotes/cash can still block entry and must
produce a visible reason; no fabricated fills. Exploration outcomes are tagged
paper_daily_exploration and excluded from strategy-learning promotion.

Aggressive mode prioritizes 0DTE then nearest expiry, holds at most 15 minutes,
and may re-enter sequentially with a two-minute loss cooldown/five-minute
same-contract cooldown. Regular checks are worker-cycle based, not tick-level
execution. Source/latency and qualifying setup constraints remain visible.

### Final scalper settings

The later scalper instructions supersede the earlier 15-minute horizon and
2/5-minute cooldown plan: initial stop −25%; locks at 30/40/50/75/100 then
50-percentage-point steps. After +30%, protect 85% of the observed gain;
the tighter stop applies. No profit ceiling. Research positions end at the
observed stop or session close, with no fabricated closing fill.

Scale-ins require a new 30%-higher bid, fresh completed-bar trend confirmation,
affordable cash, and added stop risk <=2% of cash; at most three contracts.
Average cost and quantity-based P/L are reconciled and the absolute stop cannot
fall on an add. Strong-trend re-entry can bypass the ordinary cooldown, but
requires a current independent setup; each re-entry gets its own immutable
signal baseline when needed. Weak/stale trend signals retain ordinary guards.

Database stop/quantity accounting was exercised in a rolled-back transaction;
no synthetic position or event was retained. $1,000 per agent was verified.
