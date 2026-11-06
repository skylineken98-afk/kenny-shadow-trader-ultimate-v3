"""Read-only option strike concentration from reported contract volume.

Only ranks the *sampled* contracts with actual aggregated trading volume.
Quote size, open interest, theoretical gamma exposure and trade prints are not
interchangeable with today's traded contract volume.
"""
import re
from .evidence_ranking import nonnegative_int

OCC=re.compile(r"^([A-Z.]{1,8})(\d{6})([CP])(\d{8})$")

def strike_activity(contracts, volumes, *, as_of=None, universe_label="sampled contracts"):
    grouped={}
    valid_contracts=0
    for contract in list(dict.fromkeys(contracts or [])):
        m=OCC.fullmatch(str(contract))
        if not m:continue
        observation=(volumes or {}).get(contract) or {}
        # An absent or previous-session aggregate cannot be called today's flow.
        if not observation.get("current_session"):continue
        volume=nonnegative_int(observation.get("volume"))
        if volume is None:continue
        valid_contracts+=1
        underlying,expiry,right,strike=m.groups()
        key=(underlying,expiry,int(strike)/1000)
        row=grouped.setdefault(key,{"underlying":underlying,"expiration_yymmdd":expiry,"strike":int(strike)/1000,
                                     "call_volume":0,"put_volume":0})
        row["call_volume" if right=="C" else "put_volume"]+=volume
    result=[]
    for row in grouped.values():
        row["combined_volume"]=row["call_volume"]+row["put_volume"]
        row["put_call_volume_ratio"]=(round(row["put_volume"]/row["call_volume"],3)
                                       if row["call_volume"] else None)
        row["net_buying_pressure"]="UNKNOWN"
        result.append(row)
    result.sort(key=lambda x:(-x["combined_volume"],x["underlying"],x["expiration_yymmdd"],x["strike"]))
    return {"as_of":as_of,"coverage":{"contracts_with_verified_session_volume":valid_contracts,
                                       "contracts_submitted":len(set(contracts or [])),
                                       "sample":universe_label},
            "highest_volume_strikes":result[:20],
            "note":"Observed contract volume in the sampled universe; not the full options market. Put/call ratio cannot identify net bullish or bearish positioning. Trade aggressor and dealer exposure are unverified."}
