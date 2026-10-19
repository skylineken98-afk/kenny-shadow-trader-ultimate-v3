import os

def get(name, default=""):
    value=os.getenv(name)
    if value: return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default))
    except Exception: return default

def symbols():
    return [s.strip().upper() for s in get('SCAN_SYMBOLS','SPY,QQQ,IWM,AAPL,MSFT,NVDA,TSLA,BTC-USD,ETH-USD').split(',') if s.strip()]
