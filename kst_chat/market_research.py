"""Source-grounded market research retrieval for KST Chat.

Read-only; uses existing private KST server-side database access. Does not
connect to broker accounts or generate orders. Scanner scores are not odds.
"""
from datetime import datetime, timedelta, timezone
import re

def _utc(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None

def _age_minutes(timestamp, now):
    t = _utc(timestamp)
    if not t:
        return None
    age = (now - t).total_seconds() / 60
    return round(age, 1) if age >= 0 else None

def _symbols(message):
    """Ticker identification is conservative; invalid identifiers are ignored."""
    stop = {"BEST","WHAT","WHICH","TRADE","SWING","CALL","PUT","SPX","KST",
            "LEAPS","AI","PRICE","NOW","ETF","BUY","SELL","NEXT","DTE",
            "LIVE","RISK","HIGH","LOW","OPEN","CLOSE","TECH","FLOW","RVOL"}
    named = {"apple":"AAPL","nvidia":"NVDA","tesla":"TSLA",
             "microsoft":"MSFT","amazon":"AMZN","google":"GOOGL",
             "alphabet":"GOOGL","meta":"META","small caps":"IWM",
             "russell":"IWM","nasdaq":"QQQ"}
    result=[]
    for token in re.findall(r"\b[A-Z]{2,6}\b",message):
        if token not in stop and token not in result:result.append(token)
    for name,symbol in named.items():
        if re.search(r"\b"+re.escape(name)+r"\b",message.lower()) and symbol not in result:
            result.append(symbol)
    return result[:4]

def _wants_trade_research(message):
    q=message.lower()
    return any(word in q for word in ("swing","trade idea","trades","setups","option",
        "best put","best call","buy","short","bullish","bearish","momentum","volume","uptrend"))

def market_research(store, message, now=None):
    """Answer-supporting, non-user-private market snapshots plus provenance.

    Query timestamp, signal timestamp, and market quote timestamp are different.
    Fetch failure is reported explicitly, never treated as no signals.
    """
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("now must be timezone aware")
    if not _wants_trade_research(message):
        return {},[]
    refs=[]
    result={"observed_at":now.isoformat(),
        "disclaimer":"Rankings describe KST research hypotheses, NOT win probability or executable prices."}
    symbols=_symbols(message)
    try:
        params={"underlying":"in.("+",".join(symbols)+")"} if symbols else {}
        opts=store.rows("kst_option_signals",select=(
            "created_at,underlying,contract,option_type,strike,expiration,category,"
            "score,quality_label,context_label,entry_ask,entry_bid,quote_at,feed,state"
        ),category="eq.Swings" if "swing" in message.lower() else "in.(Swings,0DTE,LEAPS)",
            order="created_at.desc",limit=80,**params)
        if symbols: opts=[x for x in opts if x.get("underlying") in symbols]
        unique={}
        for row in opts:
            key=row.get("contract")
            if not isinstance(key,str) or key in unique:continue
            age=_age_minutes(row.get("quote_at"),now)
            if age is None:quote_status="UNKNOWN"
            elif age<=15:quote_status="RECENT_INDICATIVE" if row.get("feed")=="indicative" else "RECENT_UNVERIFIED"
            else:quote_status="STALE"
            item={k:row.get(k) for k in (
                "underlying","contract","option_type","strike","expiration",
                "category","score","quality_label","context_label",
                "entry_ask","entry_bid","quote_at","feed","state","created_at")}
            item.update(quote_age_minutes=age,quote_status=quote_status,
                        broker_executable_quote_verified=False,
                        score_is_win_probability=False)
            unique[key]=item
        ranking=list(unique.values())
        def rank(x):
            aligned=str(x.get("context_label") or "").endswith("_SETUP_ALIGNED")
            age=x.get("quote_age_minutes")
            fresh=age is not None and age<=15
            return (not fresh, not aligned, -(float(x.get("score") or 0)))
        ranking.sort(key=rank)
        result["contract_candidates"]=ranking[:8]
        for i,row in enumerate(result["contract_candidates"],1):
            row["reference"]="KOPT"+str(i)
            refs.append({"id":row["reference"],"label":row["contract"],
                         "time":row.get("quote_at"),"url":None})
    except Exception:
        result["contract_candidates"]={"status":"UNAVAILABLE","reason":"KST contract feed/query failed"}
    try:
        setup_params={"symbol":"in.("+",".join(symbols)+")"} if symbols else {}
        setups=store.rows("ultimate_signals",select="created_at,symbol,status,side,entry,stop,target,details",
                          order="created_at.desc",limit=75,**setup_params)
        if symbols:setups=[r for r in setups if r.get("symbol") in symbols]
        unique={}
        for row in setups:
            sym=row.get("symbol")
            if sym in unique or not sym:continue
            frames=((row.get("details") or {}).get("frames") or {})
            trend={tf: (frames.get(tf) or {}).get("trend") for tf in ("4h","1h","5m")}
            vol={tf: (frames.get(tf) or {}).get("rvol") for tf in ("4h","1h","5m")}
            unique[sym]={"symbol":sym,"status":row.get("status"),
                "side":row.get("side"),"entry":row.get("entry"),
                "stop":row.get("stop"),"target":row.get("target"),
                "created_at":row.get("created_at"),"age_minutes":_age_minutes(row.get("created_at"),now),
                "timeframe_trends":trend,"relative_volume":vol,
                "entry_stop_target_are_underlying_levels":True}
        result["technical_setups"]=list(unique.values())[:12]
        for i,row in enumerate(result["technical_setups"],1):
            row["reference"]="KSET"+str(i)
            refs.append({"id":row["reference"],"label":row["symbol"]+" setup",
                         "time":row.get("created_at"),"url":None})
    except Exception:
        result["technical_setups"]={"status":"UNAVAILABLE","reason":"KST technical signals unavailable"}
    return result,refs
