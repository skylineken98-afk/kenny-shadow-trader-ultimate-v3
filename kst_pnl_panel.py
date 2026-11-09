"""Read-only agent option P/L cards; quote freshness is always explicit."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
OCC = re.compile(r"^([A-Z.]{1,8})(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")

def decimal(value):
    try:
        d = Decimal(str(value))
        return d if d.is_finite() else None
    except (TypeError, ValueError, InvalidOperation):
        return None

def contract_label(symbol):
    m=OCC.fullmatch(str(symbol or ""))
    if not m:
        return "Unknown option contract"
    root, yy, mm, dd, side, strike=m.groups()
    return f"{root} ${Decimal(int(strike))/1000:g} {'Call' if side=='C' else 'Put'} · 20{yy}-{mm}-{dd}"

def view(row, now=None):
    now=now or datetime.now(timezone.utc)
    result={"label":contract_label(row.get("contract")),"agent":str(row.get("agent","unknown")),
            "state":row.get("state"),"quote_at":row.get("quote_at")}
    price=decimal(row.get("entry_ask")); bid=decimal(row.get("last_bid"));qty=row.get("quantity")
    if price is None or price<=0 or type(qty)!=int or qty<1:
        return {**result,"status":"UNAVAILABLE"}
    cost=price*qty*100
    result.update(entry=price,bid=bid,quantity=qty)
    if row.get("state")!="OPEN":
        pnl=decimal(row.get("realized_pl"))
        return {**result,"status":"CLOSED" if pnl is not None else "UNAVAILABLE",
                "pnl":pnl,"pct":(pnl/cost*100 if pnl is not None else None)}
    try:
        stamp=datetime.fromisoformat(str(row.get("quote_at")).replace("Z","+00:00"))
        if stamp.tzinfo is None: raise ValueError("timezone missing")
        age=(now-stamp.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return {**result,"status":"UNAVAILABLE"}
    if bid is None or bid<0 or age<0: return {**result,"status":"UNAVAILABLE"}
    pnl=(bid-price)*qty*100
    return {**result,"status":"FRESH" if age<=60 else "STALE",
            "pnl":pnl,"pct":pnl/cost*100,"age":int(age)}

def render(st,fetch):
    st.subheader("AI Paper P/L · By contract")
    st.caption("Simulated ask entries and observed option-bid marks only. Not broker fills; fees and slippage excluded.")
    if st.button("Refresh contract P/L",key="kst_contract_refresh"):st.rerun()
    rows=fetch("kst_agent_positions",100)
    if not rows:
        st.info("No simulated option positions recorded.")
        return
    for row in rows:
        x=view(row)
        with st.container(border=True):
            st.markdown("**"+x["label"]+"**")
            st.caption(f'Agent: {x["agent"]} · {x["state"]} · Quote: {x["quote_at"] or "missing"}')
            if x["status"]=="UNAVAILABLE":
                st.warning("Contract quote or P/L unavailable")
                continue
            a,b,c=st.columns(3)
            a.metric("Entry ask",f'${x["entry"]:.2f}')
            b.metric("Last bid",f'${x["bid"]:.2f}' if x["bid"] is not None else "—")
            c.metric("P/L" if x["state"]=="OPEN" else "Realized P/L",
                     f'${x["pnl"]:+,.2f}',f'{x["pct"]:+.1f}%')
            if x["status"]=="STALE":st.warning(f'Stale option quote · {x["age"]} seconds old')
            elif x["status"]=="FRESH":st.caption(f'Fresh observed bid · {x["age"]} seconds old')

def render_live(st,fetch):
    if hasattr(st,"fragment"):
        @st.fragment(run_every="15s")
        def panel():render(st,fetch)
        panel()
    else:
        render(st,fetch)
        st.caption("Manual refresh required on this Streamlit version.")
