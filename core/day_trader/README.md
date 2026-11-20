# Day-trader skill comparison

Reviewed all 11 modules at upstream commit `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd`
against KST main at `34b6be6`. The upstream MIT notice covers the adapted helpers
in this directory.

| Upstream module | KST integration |
| --- | --- |
| Scanner | `core/market_wide.py`, `core/v1_primary_scanner.py` and momentum scans already cover universe discovery and setup discovery. The replay uses KST's momentum trigger. |
| News | `core/news.py` handles headlines. The earnings panel adds recent 8-K, 10-Q and 10-K filings from KST's SEC adapter. |
| Entry | `core/momentum_scalper.py` confirms completed-candle momentum. The replay evaluates each available prefix and models entry at the next open. |
| Exit | `core/entry_exit_intelligence.py` and the scalper already plan exits. The replay adds modeled stop, target and timed exits on the underlying. |
| Time Machine | Adds historical opening-momentum replay and a separate five-minute path simulation in Streamlit. |
| Budget | `core/risk.py` and the option planner already size positions against cash and risk limits. |
| Risk | `core/risk.py` and paper execution controls already enforce sizing, exposure and loss limits. |
| Broker | KST already has a paper execution path. The dashboard research panels require zero brokerage permissions. |
| Alerts | `core/alerts.py` and `kst_options/momentum_alert_worker.py` already provide alert delivery and momentum notification state. |
| Analyst | Adds quarterly SEC revenue, margins, diluted EPS and year-over-year comparisons via the existing EDGAR adapter. |
| Pelosi | Adds a searchable House PTR filing index and original report links. |

The replay covers the first 30 minutes of complete SPY or QQQ sessions at the
selected one- or five-minute cadence. It tests the first eligible momentum
trigger, uses the trigger candle's adverse extreme as the stop, a 1.5R
target and a configurable round-trip cost. An ambiguous candle resolves to
the stop first. A stop gap fills at the adverse open. These modeled results
are underlying returns. The separate simulation uses prior full sessions
and starts at the entry candle close, conditional on surviving that candle.
Use five-minute mode for simulated paths, and one-minute mode for finer
historical entry timing. SEC metrics may reflect subsequent restatements;
the earnings view is for current research.
