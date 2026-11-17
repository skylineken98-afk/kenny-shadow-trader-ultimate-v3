"""Source-grounded market research retrieval for KST Chat.

Read-only; uses existing private KST server-side database access. Does not
connect to broker accounts or generate orders. Scanner scores are not odds.
"""
from datetime import datetime, timedelta, timezone
import re
import json

# User-authored hypothesis; never a verified signal or automatic score adjustment.
WEEKLY_TREND_HYPOTHESIS = json.loads("{\"id\":\"weekly_trend_support_friday_recovery_monday_followthrough_v1\",\"recorded_on\":\"2026-11-08\",\"symbol\":\"SPY\",\"status\":\"UNVALIDATED_USER_HYPOTHESIS\",\"source\":\"Kenny chart discussion; IMG_6130.jpeg; screenshot is not a verified market feed\",\"timeframe\":\"weekly structural trend with daily confirmation\",\"separate_from\":\"1H trend / 15M zone / 1M trigger day-trading framework\",\"premise\":\"A pullback to a long-standing rising trendline may form a higher low when support is respected.\",\"user_observation\":\"Friday was sideways with a recovery upward; not independently verified.\",\"confirmation_hypothesis\":\"A bullish Monday holding support provides early continuation evidence; weekly follow-through provides stronger evidence, not certainty.\",\"pending_session\":\"2026-11-09\",\"verification_status\":\"Friday OHLCV, trendline anchors and all prices require provider verification; Monday is pending.\",\"required_collection\":[\"verified daily and completed weekly OHLCV with source and as-of times\",\"trendline anchor dates/prices, detection time and method; freeze anchors at decision time\",\"support distance and touch history; weekly higher-high/higher-low structure\",\"Friday range, close location and recovery from low\",\"Monday open/high/low/close, support hold/break and volume versus prior sessions\",\"weekly close and subsequent 1/5/20-session returns; maximum favorable/adverse excursion\",\"failed bounces, support breaks and comparable setups without Monday confirmation\"],\"proposed_test_definition\":\"Before evaluating, version thresholds for trendline tolerance, Friday sideways/recovery and bullish Monday. Suggested starting Monday condition: completed close above open and prior Friday close while holding the frozen support band. These are test definitions, not measured facts.\",\"invalidation\":\"Record support failures and lower-low/lower-high development; never discard failed examples.\",\"learning_policy\":\"Use as labeled context only. Do not boost scores, claim win probabilities, mark confirmed, or train on fabricated outcomes. Compare chronological held-out results including failures and costs before manual promotion.\",\"live_collection_status\":\"NOT_WIRED_BY_THIS_CHANGE\"}")

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
        "best put","best call","buy","short","bullish","bearish","momentum","volume","uptrend",
        "stocks","recommend","sector","rotation","money flowing","opportunities","scanner",
        "trend","trendline","support","friday","monday","weekly","higher low"))

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
    if not symbols or "SPY" in symbols or "spx" in message.lower():
        result["weekly_trend_research_hypothesis"] = dict(WEEKLY_TREND_HYPOTHESIS)
    try:
        params={"underlying":"in.("+",".join(symbols)+")"} if symbols else {}
        opts=store.rows("kst_option_signals",select=(
            "created_at,underlying,contract,option_type,strike,expiration,category,"
            "score,quality_label,context_label,entry_ask,entry_bid,quote_at,feed,state,risk_snapshot"
        ),category="eq.Swings" if "swing" in message.lower() else "in.(Swings,0DTE,LEAPS)",
            order="created_at.desc",limit=500,**params)
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
            evidence=(row.get("risk_snapshot") or {}).get("ranking_evidence") or {}
            measures=evidence.get("activity") or {}
            sector=evidence.get("sector_relative_strength") or {}
            item["measured_option_volume"]=measures.get("contract_volume")
            item["open_interest"]=measures.get("open_interest")
            item["relative_contract_volume"]=measures.get("relative_contract_volume")
            item["volume_to_oi_ratio"]=measures.get("volume_oi_ratio")
            item["unusual_volume_proxy"]=measures.get("unusual_volume_proxy")
            item["sector_etf"]=sector.get("sector_etf")
            item["sector_relative_strength_pct_points"]=sector.get("relative_strength_pct_points")
            item["evidence_items_measured"]=evidence.get("measured_evidence_items",0)
            item["ranking_method"]=evidence.get("score_method","structural only")
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
        # For broad discovery, do not allow one ETF to monopolize the answer.
        # Named-symbol questions can still surface several contracts on that symbol.
        if not symbols:
            diverse=[];used=set();other=[]
            for item in ranking:
                ticker=item.get("underlying")
                if ticker and ticker not in used:
                    diverse.append(item);used.add(ticker)
                else:other.append(item)
            ranking=diverse+other
        result["contract_candidates"]=ranking[:8]
        result["coverage"]={"unique_option_underlyings":len(set(x.get("underlying") for x in unique.values())),
                            "sampled_contract_rows":len(opts),
                            "quotes_are_volume_verified":False,
                            "note":"Contract rank uses quality/alignment, not confirmed option volume; sampled DB records are not the entire stock market."}
        for i,row in enumerate(result["contract_candidates"],1):
            row["reference"]="KOPT"+str(i)
            refs.append({"id":row["reference"],"label":row["contract"],
                         "time":row.get("quote_at"),"url":None})
    except Exception:
        result["contract_candidates"]={"status":"UNAVAILABLE","reason":"KST contract feed/query failed"}
    try:
        setup_params={"symbol":"in.("+",".join(symbols)+")"} if symbols else {}
        setups=store.rows("ultimate_signals",select="created_at,symbol,status,side,entry,stop,target,details",
                          order="created_at.desc",limit=300,**setup_params)
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
    # Structural history is kept distinct from fresh entry quotes.
    if not symbols or 'SPY' in symbols or 'spx' in message.lower() or any(w in message.lower() for w in ('trendline','weekly','historical trend')):
        try:
            hist_symbols=['^GSPC' if x=='SPX' else x for x in symbols] or ['^GSPC','SPY']
            if 'spx' in message.lower() and '^GSPC' not in hist_symbols:hist_symbols.insert(0,'^GSPC')
            events=store.rows('kst_trendline_events',symbol='in.('+','.join(hist_symbols)+')',order='bar_at.desc',limit=12)
            result['historical_trendline_events']={'events':events,'source':'Source-reported historical OHLCV; rule-based linear trendlines. Historical replay, not verified predictive accuracy or an entry signal.'}
        except Exception:
            result['historical_trendline_events']={'status':'UNAVAILABLE','reason':'Historical collection/query unavailable; no trendline evidence invented'}
        try:
            result['collection_health']=store.rows('kst_collection_status',select='id,status,last_attempt_at,last_finished_at,last_success_at,data_as_of,rows_saved,message',limit=40)
        except Exception:
            result['collection_health']={'status':'UNAVAILABLE'}
    return result,refs

