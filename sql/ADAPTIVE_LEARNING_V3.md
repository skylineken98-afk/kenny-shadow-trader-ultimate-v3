# V3 Adaptive Learning — Research Development

Added `core/adaptive_learning.py` and tests to the latest nine-area V3 ZIP.

Implemented: local SQLite model registry; timestamped persistent observations; verified-fill scorecards;
point-in-time checks; multi-profile records; descriptive trend/volatility regime detection;
chronological champion/challenger held-out comparisons; saved audit reviews.

Nothing here places an order, changes live risk limits, retrains a neural network, or
self-promotes a strategy. Real-money automated strategy changes remain disabled.

## Basic example
```python
from core.adaptive_learning import ResearchJournal,market_regime
j=ResearchJournal('v3_research_dev.sqlite')
j.register('baseline-v1','balanced',{'indicator':'trend_alignment'})
# Record only historical decision-time features and verified paper outcomes via j.record(...).
print(j.scorecard('baseline-v1'))
j.close()
```

## Activation still missing
- Connect to an authenticated database with per-user access and retention policy; local SQLite
  is not suitable for multiple Railway replicas or ephemeral disk.
- Ingest unique paper fill IDs, timestamped market features, financing/fees/spreads/slippage.
- Build retraining jobs, label pipelines, walk-forward/purged validation, drift monitoring,
  statistical uncertainty and controlled experiments; keep human-controlled promotion.
- Wire dashboards, notifications, non-trading schedules and Supabase with proper service auth.
- No licensed Unusual Whales redistribution without commercial permission.

Test: `python -m pytest -q tests/test_adaptive_learning.py`
