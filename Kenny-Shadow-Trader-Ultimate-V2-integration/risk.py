from dataclasses import dataclass
@dataclass
class RiskLimits:
    max_position_fraction:float=.05
    max_daily_loss_fraction:float=.05
    max_open_positions:int=5
    max_total_exposure_fraction:float=.20

def permit_order(equity, day_pnl, open_positions, current_exposure, proposed_notional, limits=None, kill_switch=False):
    r=limits or RiskLimits()
    if kill_switch:return False,'Kill switch active'
    if equity<=0 or proposed_notional<=0:return False,'Invalid equity/notional'
    if day_pnl<=-equity*r.max_daily_loss_fraction:return False,'Daily loss limit reached'
    if open_positions>=r.max_open_positions:return False,'Open-position limit reached'
    if proposed_notional>equity*r.max_position_fraction:return False,'Position cap exceeded'
    if current_exposure+proposed_notional>equity*r.max_total_exposure_fraction:return False,'Portfolio exposure cap exceeded'
    return True,'Allowed for PAPER simulation only'
