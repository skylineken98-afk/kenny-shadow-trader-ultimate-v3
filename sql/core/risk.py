from dataclasses import dataclass
@dataclass(frozen=True)
class Limits:
    max_trade_fraction:float=.01
    max_daily_loss_fraction:float=.05
    max_gross_fraction:float=.25
    max_symbol_fraction:float=.10

def sizing(cash,equity,entry,stop,limits=Limits()):
    if min(cash,equity,entry)<=0 or stop is None or entry==stop:return 0
    risk_per_unit=abs(entry-stop)
    by_risk=int(equity*limits.max_trade_fraction/risk_per_unit)
    by_cash=int(min(cash,equity*limits.max_symbol_fraction)/entry)
    return max(0,min(by_risk,by_cash))

def permitted(equity,day_start_equity,gross_exposure,proposal_value,limits=Limits(),killed=False):
    if killed or equity<=0 or day_start_equity<=0:return False,'kill switch or invalid equity'
    if (day_start_equity-equity)/day_start_equity>=limits.max_daily_loss_fraction:return False,'daily loss limit'
    if proposal_value<=0:return False,'invalid order value'
    if proposal_value>equity*limits.max_symbol_fraction:return False,'per-symbol exposure limit'
    if gross_exposure+proposal_value>equity*limits.max_gross_fraction:return False,'portfolio exposure limit'
    return True,'ok'
