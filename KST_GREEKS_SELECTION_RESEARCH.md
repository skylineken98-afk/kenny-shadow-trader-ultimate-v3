# KST Greeks-Aware Contract Selection — research branch

## Existing capability versus this addition
KST already ingested delta, gamma, theta, vega, and rho into a contract's
`risk_snapshot`. Delta was used as a structural qualification gate.
This update adds interpretation, risk scenarios, timestamp provenance and a
small bounded adjustment used by `requested_choices` **after** affordability
and liquidity screening. The existing delta, spreads, quote freshness,
expiration/category and context rules are unchanged.

## Greeks research
`kst_options/greeks_selection.py` computes:
- Delta exposure, gamma-to-absolute-delta acceleration proxy and daily
  theta as a fraction of ask premium.
- Six static Delta–Gamma–Theta–Vega scenarios for +/-1% underlying moves,
  +/-2 implied volatility percentage points, and a configurable hold.
  No scenario is labeled a prediction or executable option fill.
- Rho is included as metadata and is not used as a short-term scalp trigger.
- A bounded [-5,+5] structural-score adjustment *only when a separately
  supplied, valid Greeks timestamp is present*. A quote timestamp does **not**
  qualify as a timestamp for the Greeks. Greeks missing or stale leave
  the original structural ranking unchanged.

Scenarios assume a standardized contract multiplier of 100 and provider
conventions of theta per day, vega/rho per one percentage point. These
conventions must be verified against each feed before production use.
Greeks can change rapidly, particularly on 0DTE contracts. Scenario P&L
excludes spread, commissions, IV surface dynamics and fills.

## Integration
`kst_options.engine.candidate` stores `greeks_analysis` next to original
provider Greeks. `kst_options.engine.requested_choices` sorts qualified,
affordable candidates using the bounded adjusted score without eliminating
cheap options merely for lacking Greek timestamps. Original
`structural_score` is preserved in ranked output. No autonomous orders,
paper fills, agent arming, database migrations or deployment changes.

## Verification and next gate
Run:
`python -m pytest -q tests_options/test_greeks_selection.py tests_options/test_r3.py`

Historical performance is unknown; synthetic tests establish logic only.
Verify the actual Greeks source, as-of timestamp and units before enabling
ranking bonuses. Then compare contract outcomes by budget tier ($50, $100,
$200, $500), DTE, Greeks availability, spread and slippage using held-out
real data. Review before merging or deploying.
