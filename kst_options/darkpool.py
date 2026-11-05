"""Delayed FINRA ATS transparency adapter. Not a live dark-pool tape.

The caller supplies externally verified, dated FINRA ATS weekly observations.
Never manufactures or infers institutional buying/selling direction.
"""
from datetime import date,datetime
from .evidence_ranking import nonnegative_int

def delayed_ats_report(rows,*,published_at=None,source_url=None):
    if not isinstance(source_url,str) or not source_url.startswith("https://www.finra.org/"):
        return {"status":"UNAVAILABLE","reason":"Official FINRA source and publication date required","rows":[]}
    try:
        published=date.fromisoformat(str(published_at)[:10])
    except (ValueError,TypeError):return {"status":"UNAVAILABLE","reason":"Valid publication date required","rows":[]}
    if published>datetime.now().date():return {"status":"UNAVAILABLE","reason":"Publication date is in future","rows":[]}
    output=[]
    for row in rows or []:
        if not isinstance(row,dict):continue
        symbol=str(row.get("symbol") or "").strip().upper()
        shares=nonnegative_int(row.get("shares"))
        trades=nonnegative_int(row.get("trades"))
        week=row.get("week_ending")
        try:week=date.fromisoformat(str(week))
        except (ValueError,TypeError):continue
        if not symbol or not symbol.replace(".","").isalnum() or shares is None or trades is None or week>published:continue
        output.append({"symbol":symbol,"week_ending":week.isoformat(),"shares":shares,"trades":trades})
    return {"status":"HISTORICAL_DELAYED" if output else "UNAVAILABLE",
            "source":"FINRA ATS Transparency","source_url":source_url,
            "published_at":published.isoformat(),"rows":output,
            "notes":"Historical ATS-reported volume. Not real-time dark-pool transactions; no buy/sell aggressor, institutional accumulation or immediate price impact inferred."}
