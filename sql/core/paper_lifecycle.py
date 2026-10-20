"""Deterministic, offline simulated LONG stock/call/put trade lifecycle.

No broker calls. A paper 'fill' is an assumption, never a broker fill.
Prices for options MUST be option contract premiums, not underlying prices.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from core.agents import PROFILES

class PaperRiskError(ValueError): pass

def dec(value):
    try:
        v = Decimal(str(value))
        if not v.is_finite() or v <= 0: raise PaperRiskError('nonpositive or nonfinite price')
        return v
    except (InvalidOperation, TypeError): raise PaperRiskError('invalid number')

@dataclass(frozen=True)
class PaperAccount:
    agent: str
    equity: Decimal
    day_start_equity: Decimal
    open_cost: Decimal = Decimal('0')
    killed: bool = False

    def __post_init__(self):
        if self.agent not in PROFILES: raise PaperRiskError('unknown agent')
        if self.equity <= 0 or self.day_start_equity <= 0 or self.open_cost < 0: raise PaperRiskError('bad account')


def enter(account, *, signal_id, symbol, asset, direction, entry, stop, target, ask, quantity=1,
          max_day_loss=Decimal('.05'), max_exposure=Decimal('.25'), fee_per_unit=Decimal('0')):
    """Conservative simulated immediate ask fill, long-only shares or standard call/put.
    Require signal direction and instrument type to match; no naked short trades.
    """
    if account.killed: raise PaperRiskError('kill switch active')
    if account.equity <= account.day_start_equity * (1 - max_day_loss): raise PaperRiskError('daily loss limit')
    if not signal_id or not symbol: raise PaperRiskError('source signal and symbol required')
    if asset not in ('stock','call','put'): raise PaperRiskError('unsupported asset')
    if direction not in ('BULLISH','BEARISH'): raise PaperRiskError('unsupported direction')
    if (direction=='BEARISH' and asset!='put') or (asset=='put' and direction!='BEARISH'):
        raise PaperRiskError('direction/long-instrument mismatch')
    if isinstance(quantity,bool) or not isinstance(quantity,int) or not 1<=quantity<=100: raise PaperRiskError('bad quantity')
    entry, stop, target, ask = map(dec, (entry,stop,target,ask))
    if not stop < entry < target: raise PaperRiskError('invalid LONG instrument levels')
    if ask < entry: raise PaperRiskError('ask below assumed entry; re-quote before simulation')
    multiplier = 100 if asset in ('call','put') else 1
    fee = Decimal(str(fee_per_unit)) * quantity
    cost = ask*quantity*multiplier + fee
    if cost > account.equity - account.open_cost: raise PaperRiskError('insufficient simulated cash')
    if cost+account.open_cost > account.equity*max_exposure: raise PaperRiskError('exposure cap')
    risk = max(Decimal('0'),ask-stop)*quantity*multiplier+fee
    if risk > account.equity * Decimal(str(PROFILES[account.agent].max_risk_fraction)):
        raise PaperRiskError('agent risk cap')
    return dict(signal_id=str(signal_id), agent=account.agent, symbol=symbol, asset=asset,
                direction=direction, quantity=quantity, fill_price=str(ask), stop=str(stop),
                target=str(target), cost=str(cost), fee=str(fee), multiplier=multiplier,
                state='SIMULATED_OPEN', simulation_only=True)


def close_trade(trade, *, bid=None, bar=None, fee_per_unit=Decimal('0')):
    """Use bid for exit; if OHLC has both barriers touched, assume stop first.
    OHLC simulation is inherently approximate and ignores intrabar event order.
    """
    if trade.get('state')!='SIMULATED_OPEN' or trade.get('simulation_only') is not True:
        raise PaperRiskError('invalid paper position')
    stop=dec(trade['stop']); target=dec(trade['target'])
    if bar is not None:
        lo=dec(bar['low']);hi=dec(bar['high'])
        if lo>hi:raise PaperRiskError('bad bar')
        if lo<=stop: price=stop;reason='STOP'
        elif hi>=target:price=target;reason='TARGET'
        else: return None
    elif bid is not None:
        price=dec(bid);reason='MARKET_EXIT'
    else: raise PaperRiskError('requires bid or bar')
    qty=int(trade['quantity']); mult=int(trade['multiplier'])
    fees=Decimal(trade['fee'])+Decimal(str(fee_per_unit))*qty
    pnl=(price-Decimal(trade['fill_price']))*qty*mult-fees
    return {**trade, 'state':'CLOSED', 'exit_reason':reason,'exit_price':str(price),
            'realized_pnl':str(pnl), 'simulated_only':True}
