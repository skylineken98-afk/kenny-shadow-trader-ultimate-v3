"""Private futures cloud risk guard — research/simulation only.

Does not connect to NinjaTrader, Tradovate, Apex or any broker.
No live-order code. Fail closed when quotes/account status are stale.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math

@dataclass(frozen=True)
class Policy:
    max_contracts: int = 1
    max_positions: int = 1
    max_daily_loss_usd: float = 10.0
    max_risk_per_trade_usd: float = 5.0
    max_quote_age_seconds: float = 3.0
    max_account_age_seconds: float = 15.0
    min_rr: float = 1.5
    allowed_symbols: tuple = ("NNQ",)  # Subject to broker listing and contract verification.

@dataclass(frozen=True)
class Candidate:
    symbol: str
    direction: str
    entry: float
    stop: float
    target: float
    qty: int
    usd_per_point: float
    market_data_at: datetime

@dataclass(frozen=True)
class AccountSnapshot:
    timestamp: datetime
    realized_today_usd: float
    unrealized_usd: float
    open_positions: int
    margin_available_usd: float
    connection_ok: bool
    protective_order_system_ok: bool
    simulation_account: bool

def check(candidate: Candidate, account: AccountSnapshot, *, now=None, policy=Policy()):
    """Return (approved, reason). Approval is ONLY for paper-order simulation."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        return False, "INVALID_CLOCK"
    now = now.astimezone(timezone.utc)
    if not account.simulation_account:
        return False, "LIVE_ACCOUNT_FORBIDDEN"
    if not account.connection_ok or not account.protective_order_system_ok:
        return False, "CONNECTION_OR_PROTECTION_UNAVAILABLE"
    for t, max_age, code in (
        (candidate.market_data_at, policy.max_quote_age_seconds, "STALE_QUOTE"),
        (account.timestamp, policy.max_account_age_seconds, "STALE_ACCOUNT"),
    ):
        if t.tzinfo is None or not (0 <= (now-t.astimezone(timezone.utc)).total_seconds() <= max_age):
            return False, code
    if candidate.symbol not in policy.allowed_symbols:
        return False, "SYMBOL_NOT_APPROVED"
    if candidate.direction not in ("LONG", "SHORT"):
        return False, "INVALID_DIRECTION"
    vals = (candidate.entry, candidate.stop, candidate.target, candidate.usd_per_point,
            account.realized_today_usd, account.unrealized_usd, account.margin_available_usd)
    if not all(isinstance(v, (int,float)) and math.isfinite(v) for v in vals):
        return False, "INVALID_NUMERIC_VALUE"
    if min(candidate.entry,candidate.stop,candidate.target,candidate.usd_per_point) <= 0:
        return False, "INVALID_PRICE_OR_MULTIPLIER"
    if not isinstance(candidate.qty,int) or candidate.qty < 1 or candidate.qty > policy.max_contracts:
        return False, "POSITION_SIZE_REJECTED"
    if account.open_positions < 0 or account.open_positions >= policy.max_positions:
        return False, "POSITION_LIMIT"
    side = 1 if candidate.direction == "LONG" else -1
    risk_points = side*(candidate.entry-candidate.stop)
    reward_points = side*(candidate.target-candidate.entry)
    if risk_points <= 0 or reward_points <= 0 or reward_points/risk_points < policy.min_rr:
        return False, "INVALID_REWARD_RISK"
    risk_usd = risk_points*candidate.usd_per_point*candidate.qty
    if risk_usd > policy.max_risk_per_trade_usd:
        return False, "PER_TRADE_RISK_LIMIT"
    # A prospective full stop cannot exceed daily budget (fees/slippage require extra buffer).
    if account.realized_today_usd + account.unrealized_usd - risk_usd <= -policy.max_daily_loss_usd:
        return False, "DAILY_LOSS_GUARD"
    if account.margin_available_usd <= 0:
        return False, "INSUFFICIENT_MARGIN"
    # Requires real broker initial/day margin checks in execution adapter; not sufficient for live.
    return True, "SIMULATION_ONLY"
