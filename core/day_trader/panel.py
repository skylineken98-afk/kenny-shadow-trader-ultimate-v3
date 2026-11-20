"""On-demand research entry points for the KST dashboard."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from core.day_trader.disclosures import PtrError, load_index, select
from core.day_trader.quarterly import FactsError, analyse
from core.day_trader.replay import opening_replay
from core.market import history
from core.sec_intelligence import company_facts, recent_filings


def render():
    with st.expander("Opening momentum replay"):
        st.caption("Historical SPY or QQQ underlying research. Option returns require contract quotes.")
        symbol = st.selectbox("Underlying", ["SPY", "QQQ"], key="opening_replay_symbol")
        minutes = st.selectbox("Candle minutes", [1, 5], key="opening_replay_minutes")
        cost = st.number_input("Round-trip cost assumption (basis points)", 0, 100, 4)
        if st.button("Run opening replay"):
            try:
                candles = history(symbol, "7d" if minutes == 1 else "60d", f"{minutes}m")
                if not candles.empty:
                    today = datetime.now(ZoneInfo("America/New_York")).date()
                    candles = candles[candles.index.tz_convert("America/New_York").date < today]
                result = opening_replay(candles, symbol, minutes=minutes, cost_bps=cost)
            except (ValueError, KeyError, TypeError, requests.RequestException):
                st.info("The price feed did not return usable replay data.")
            else:
                trades = pd.DataFrame(result["trades"])
                st.write(f"{result['sessions']} complete opening windows, {len(trades)} modeled trades.")
                if not trades.empty:
                    st.dataframe(trades, use_container_width=True)
                if result["simulation"]:
                    st.caption("Separate five-minute price-path simulation, conditional on surviving the entry candle. Percentages are modeled.")
                    st.write(result["simulation"])

    with st.expander("SEC quarterly earnings and filings"):
        ticker = st.text_input("Company ticker", "NVDA", key="quarterly_facts_ticker").strip().upper()
        if st.button("Compare SEC quarters"):
            try:
                facts = company_facts(ticker)
                if facts["status"] != "ok":
                    st.info("Ticker not found in the SEC index.")
                else:
                    report = analyse(facts["data"])
                    st.dataframe(pd.DataFrame(report["rows"]), use_container_width=True)
                    filings = recent_filings(ticker, forms=("10-K", "10-Q", "8-K"))
                    st.dataframe(pd.DataFrame(filings.get("filings", [])[:10]), use_container_width=True)
            except (FactsError, ValueError, requests.RequestException) as exc:
                st.info(str(exc))

    with st.expander("House transaction disclosures"):
        st.caption("Public filings can lag the transactions. Open the original report to see transaction details.")
        member = st.text_input("House member (blank for all)", key="house_disclosure_member").strip()
        current_year = datetime.now(ZoneInfo("America/New_York")).year
        year = st.number_input("Filing year", 2012, current_year, current_year)
        if st.button("Find House disclosures"):
            try:
                rows = select(load_index(year), members=[member] if member else None)
            except (PtrError, OSError, ValueError, KeyError):
                st.info("The House Clerk filing index is unavailable for that year.")
            else:
                if rows:
                    st.dataframe(pd.DataFrame(rows[:30])[["name", "district", "filed", "url"]],
                                 column_config={"url": st.column_config.LinkColumn("Original report")},
                                 use_container_width=True)
                else:
                    st.info("No matching transaction reports found.")
