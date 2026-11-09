"""SPX/SPXW daily paper-candidate checks. No broker orders or simulated fills."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import re

OCC=re.compile(r"^(SPX|SPXW)(\d{6})([CP])(\d{8})$")
NY=ZoneInfo("America/New_York")
@dataclass(frozen=True)
class Policy:
    min_rr: Decimal=Decimal("1.5")
    stop_fraction: Decimal=Decimal("0.25")
    allocation: Decimal=Decimal("0.10")
    max_open: int=3
    quote_max_age: int=60

def dec(x):
    try:
        d=Decimal(str(x))
        return d if d.is_finite() else None
    except (ValueError,TypeError,InvalidOperation):
        return None

def evaluate(row,now=None,policy=Policy()):
    now=now or datetime.now(timezone.utc)
    def wait(reason):return {"action":"WAIT","reason":reason,"simulation_only":True,"broker_order":False}
    symbol=str(row.get("contract",""))
    m=OCC.fullmatch(symbol)
    if not m:return wait("Complete SPX/SPXW OCC contract required")
    exp=datetime.strptime(m.group(2),"%y%m%d").date()
    local=now.astimezone(NY)
    if exp<local.date() or local.weekday()>4 or not 570<=local.hour*60+local.minute<960:
        return wait("Option expired or market closed")
    side=row.get("direction")
    if side not in ("BULLISH","BEARISH"):return wait("Missing bullish or bearish direction")
    if any(row.get(k)!=side for k in ("trend_1h","zone_15m","trigger_1m")) or row.get("trigger_bar_complete") is not True:
        return wait("1H trend, 15M zone, and completed 1M trigger required")
    try:
        stamp=datetime.fromisoformat(str(row.get("quote_at")).replace("Z","+00:00"))
        if stamp.tzinfo is None or not 0<=(now-stamp.astimezone(timezone.utc)).total_seconds()<=policy.quote_max_age: raise ValueError("stale")
    except (ValueError,TypeError,OverflowError):
        return wait("Missing, invalid, or stale contract quote")
    bid,ask,stop,target,equity=map(dec,(row.get("bid"),row.get("ask"),row.get("stop_premium"),row.get("target_premium"),row.get("equity")))
    if any(x is None for x in (bid,ask,stop,target,equity)) or not (0<=bid<=ask and 0<stop<ask<target and equity>0):
        return wait("Invalid option premium or account data")
    if (m.group(3)=="C")!=(side=="BULLISH"):return wait("Option direction mismatch")
    if row.get("kill_switch") is not False:return wait("Emergency stop enabled or unknown")
    count=row.get("open_positions")
    if type(count)!=int or not 0<=count<policy.max_open:return wait("Open position limit or unknown count")
    if ask*100>equity*policy.allocation:return wait("One contract exceeds 10% account allocation")
    if stop!=ask*(1-policy.stop_fraction):return wait("Stop must be exactly 25% of premium below entry")
    rr=(target-ask)/(ask-stop)
    if rr<policy.min_rr:return wait("Risk/reward below 1.5")
    return {"action":"PAPER_CANDIDATE","contract":symbol,"entry_ask":str(ask),
            "stop_premium":str(stop),"target_premium":str(target),"rr":str(rr),
            "quote_at":stamp.isoformat(),"simulation_only":True,"broker_order":False,
            "daily_trade_guaranteed":False}
