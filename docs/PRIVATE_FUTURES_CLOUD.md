# KST Private Futures — Cloud Architecture (SIMULATION ONLY)

This experimental module is part of the existing KST GitHub project but is
separated from public alerts, public user credentials, and Apex/Tradovate.

## Architecture
- Shared KST market research engine produces candidate trades, no executions.
- Dedicated private futures execution gateway runs with NinjaTrader **Desktop
  on a licensed Windows VPS**, not on Linux Railway. NinjaScript integration
  is NOT implemented yet; brokerage compatibility/API and VPS providers need verification.
- On the VPS, first run a NinjaTrader **Sim101** strategy with account whitelisting.
- Local private risk guard checks candidate, fresh quotes, account freshness,
  direction, protective-order availability, 1.5:1 RR, size, daily-loss caps.
- Private Telegram updates and KST admin-only website view are future work;
  no public API can access private trading records or credentials.
- Public NQ/MNQ alerts remain independent: PR #21 (also draft).

## Existing branch scope
- private_futures/risk_guard.py: fail-closed PAPER-ONLY pretrade guard.
- tests/test_private_futures_risk_guard.py: synthetic guard tests.
- No NinjaScript order adapter, cloud VPS, broker data subscription, broker
  credentials, deployment, API key, live-trading permission, trade execution,
  or user-fund movement.
- No backtest profitability claims. Tests have not been run in this workspace.

## Suggested initial paper policy (tunable, not funded-account settings)
- one position; one contract; NNQ only **if brokerage confirms symbol/listing**
- $5 maximum modeled risk/trade and $10 daily modeled loss limit
- 1.5:1 minimum reward/risk
- quote max 3 seconds old, account status max 15 seconds old
- refuse non-Sim101 live account; no trading when order protection is unavailable
- conservative controls must also account for instrument point multiplier,
  exchange tick size, round-trip fees, opening gaps, slippage, broker margin,
  forced liquidation, data outages and overnight position policy.

## Before actual cloud simulation
1. Confirm Windows VPS compatible with NinjaTrader Desktop, Windows licensing,
   monthly hosting budget and unattended remote access. Railway Linux services
   cannot host NinjaTrader Desktop directly.
2. Confirm personal NinjaTrader brokerage account and Sim101 availability,
   NNQ instrument support, real-time market data access and license terms.
3. Build NinjaScript managed-order simulation adapter separately with
   a **hard-coded Sim101 allowlist and manual kill switch**.
4. Test connectivity, orders, rejected orders, disconnect/reconnect, duplicate
   signals, protective stop lifecycle, and position/order reconciliation.
5. Verify account currency, daily resets in ET, trading hours, contract rolls,
   broker/exchange fees and actual margin.
6. Add user-only authenticated dashboard, private Telegram trade reports,
   and order execution audit logs (do not expose to the public beta).
7. Run replay/paper tests and assess losses, drawdown and operational reliability.
8. Live orders require distinct code review, a separate explicitly authorized
   live release, broker approval, and a sufficient account balance; **the
   current module cannot place live orders**.

## No fees incurred
No cloud instance, license, subscription or deployment was created by this PR.

Run offline tests:
`python -m unittest discover -s tests -p test_private_futures_risk_guard.py -v`
