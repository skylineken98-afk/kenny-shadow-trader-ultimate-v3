import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.settings import symbols,get
from core.market import history,confluence,levels
from core.db import fetch,client
from core.paper import open_paper_trade
st.set_page_config(page_title='Kenny Shadow Trader Ultimate V3',page_icon='📈',layout='wide')
st.markdown("""<style>.stApp{background:#090e1a;color:#e6ecff}div[data-testid="stMetric"]{background:#151c31;border:1px solid #283454;padding:12px;border-radius:12px}</style>""",unsafe_allow_html=True)
password=get('APP_PASSWORD')
if password:
    entered=st.text_input('Access password',type='password')
    if entered!=password:st.stop()
st.title('⚡ Kenny Shadow Trader Ultimate V3')
st.caption('BETA • Rules-based market scan • Paper simulations only • Live orders permanently disabled in this build')
if not password:st.warning('APP_PASSWORD is not configured. Set it before exposing the dashboard publicly; service-role credentials must remain server-side.')
if client() is None:st.warning('Supabase is not configured. Live market exploration works; persistence, news history and paper ledger require Supabase + SQL setup.')
tabs=st.tabs(['Dashboard','0DTE','Swings','LEAPS','Stocks','Crypto','Forex','Futures','Request a Signal','Market Sentiment','AI News','Paper Trading','Risk & System'])
with tabs[0]:
    st.subheader('Latest tracked signals')
    rows=fetch('ultimate_signals',100)
    if rows:st.dataframe(pd.DataFrame(rows)[['created_at','symbol','status','side','entry','stop','target']],use_container_width=True)
    else:st.info('No saved ultimate_signals yet. Check scanner logs and Supabase permissions.')
    st.subheader('Watchlist');st.write(', '.join(symbols()))
def chart(symbol):
    df=history(symbol,'60d','1h')
    if df.empty:st.warning('No price history available');return
    df=df.tail(200);fig=go.Figure(data=[go.Candlestick(x=df.index,open=df.Open,high=df.High,low=df.Low,close=df.Close,name=symbol)])
    z=levels(df)
    if z:
        fig.add_hline(y=z['support'],line_dash='dash',annotation_text='Support')
        fig.add_hline(y=z['resistance'],line_dash='dash',annotation_text='Resistance')
    fig.update_layout(template='plotly_dark',height=480,xaxis_rangeslider_visible=False)
    st.plotly_chart(fig,use_container_width=True)
def explore(kind,preset):
    st.caption(kind+' • Price action information is not a verified options contract quote or executable signal.')
    symbol=st.text_input('Ticker',preset,key='ticker_'+kind)
    if st.button('Analyze '+kind,key='analyze_'+kind):
        with st.spinner('Loading market bars...'):
            s=confluence(symbol.upper().strip())
        st.json(s)
        if s['status']!='INSUFFICIENT_DATA':chart(symbol)
for idx,kind,default in [(1,'0DTE','SPY'),(2,'Swings','IWM'),(3,'LEAPS','QQQ'),(4,'Stocks','AAPL'),(5,'Crypto','BTC-USD'),(6,'Forex','EURUSD=X'),(7,'Futures','NQ=F')]:
    with tabs[idx]: explore(kind,default)
with tabs[8]:
    from core.request_signals import discover_contracts, CATEGORIES
    st.subheader('🎯 Request a Signal — Top 3 per category')
    st.caption('Real vendor option-chain contracts · Ranked research candidates · Not trade recommendations or live executable quotes')
    c1,c2=st.columns([3,1])
    with c1:
        universe=st.text_input('Underlyings to search (comma-separated)', 'SPY,QQQ,IWM,TSLA,NVDA,AAPL,MSFT', key='request_symbols')
    with c2:
        budget=st.number_input('Max cost per 1 contract ($)',min_value=30,max_value=3000,value=300,step=10,key='request_budget')
    st.caption('Requires aligned bullish or bearish 4H → 1H → 5M research setup, nonzero bid, sufficient liquidity and available expirations. Results can be fewer than three.')
    if st.button('🔎 Request Top 3 for 0DTE, Swings & LEAPS', type='primary',key='request_options'):
        with st.spinner('Checking option chains and multi-timeframe trend alignment…'):
            st.session_state['requested_options']=discover_contracts(universe.split(','),budget)
    if 'requested_options' in st.session_state:
        found,notes=st.session_state['requested_options']
        for group in CATEGORIES:
            st.markdown(f'### {group} · {len(found[group])}/3 verified candidates')
            if not found[group]:st.info('No contracts met the expiration, data freshness, liquidity, budget, and trend requirements. No placeholders generated.')
            columns=st.columns(3)
            for index,record in enumerate(found[group]):
                with columns[index]:
                    right=record['right'];direction='🟢 CALL' if right=='CALL' else '🔴 PUT'
                    quote=record['last'];cost=record['cost']
                    st.markdown(f"**{index+1}. {record['contract']}**")
                    st.caption(f"{record['ticker']} · {record['expiration']} · {record['strike']:g} · {direction}")
                    st.metric('Last trade premium',f'${quote:.2f}' if quote is not None else 'Unavailable',
                        f"{record['percent_change']:+.2f}%" if record['percent_change'] is not None else None)
                    st.markdown(f"**Bid:** ${record['bid']:.2f} &nbsp;&nbsp; **Ask:** ${record['ask']:.2f}")
                    st.caption(f"Indicative 1-contract ask cost: ${cost:,.2f} · Spread {record['spread_pct']:.1f}%")
                    st.caption(f"Volume {record['volume']:,} · Open interest {record['open_interest']:,} · Rank {record['rank_score']:.1f}/100 (liquidity/fit, NOT win probability)")
                    with st.expander('Quote & research details'):
                        st.write('Last option trade:',record['last_trade_at'])
                        st.write('Quote caveat:',record['quote_warning'])
                        st.write('No verified option-premium entry, stop, or target. Do not substitute underlying price levels.')
                        st.write('This contract was identified by its vendor-reported symbol and chain; verify live quotes with your broker.')
        with st.expander(f'Provider and screening notices ({len(notes)})'):
            for notice in notes:st.caption(notice)
        st.warning('Quote fields may be delayed. Last-trade timestamps do not establish bid/ask freshness. 0DTE can be unavailable outside market hours or when no qualifying expiry exists. No orders are submitted.')
with tabs[9]:
    st.subheader('Rule-based market sentiment proxy')
    st.caption('This is not a licensed fear/greed, fund flow or options positioning feed.')
    data=[]
    if st.button('Calculate breadth proxy'):
        for sym in ['SPY','QQQ','IWM','XLF','XLK','TLT','GLD','BTC-USD']:
            x=confluence(sym);data.append({'symbol':sym,'4h_trend':(x.get('frames',{}).get('4h') or {}).get('trend','unknown'),'aligned_setup':x['status']=='SETUP'})
        st.dataframe(pd.DataFrame(data),use_container_width=True)
with tabs[10]:
    st.subheader('AI News Intelligence')
    st.dataframe(pd.DataFrame(fetch('news_articles',100)),use_container_width=True)
    st.subheader('Recent classifications');st.dataframe(pd.DataFrame(fetch('news_analysis',50)),use_container_width=True)
with tabs[11]:
    st.subheader('Simulated positions — NOT brokerage orders')
    st.dataframe(pd.DataFrame(fetch('paper_trades',100)),use_container_width=True)
    st.warning('Educational simulation: no fill model, slippage, funding, margin, contract multipliers or mark-to-market reconciliation. Do not treat as accurate performance.')
    with st.form('paper_form'):
        sym=st.text_input('Symbol','SPY');asset=st.selectbox('Asset class',['stock','crypto','forex','future']);side=st.selectbox('Side',['BUY','SELL'])
        entry=st.number_input('Hypothetical entry',min_value=0.01,value=100.0);stop=st.number_input('Stop',min_value=0.01,value=98.0);target=st.number_input('Target',min_value=0.01,value=104.0)
        equity=st.number_input('Simulation account equity',min_value=1.0,value=10000.0)
        consent=st.checkbox('I understand this records an illustrative paper position only, not an order.')
        submitted=st.form_submit_button('Record hypothetical paper position',disabled=not consent)
    if submitted:st.json(open_paper_trade(sym,asset,side,entry,stop,target,equity,equity,equity))
with tabs[12]:
    st.subheader('Hard safety gates')
    st.write('Live execution: **DISABLED**. No API method capable of submitting brokerage orders is present.')
    st.write('Paper risk defaults: 1% equity risk/trade, 5% daily drawdown guard, 10% per-symbol allocation, 25% gross exposure cap.')
    st.write('These are safety checks for illustrative paper entries, not a complete automated risk engine.')
    st.write('News and market workers run separately from the dashboard on Railway.')

# Independent upgrade dashboard panels. These never trigger broker orders.
with st.expander('Research agent evaluations (read-only)', expanded=False):
    from core.agents import PROFILES, evaluate
    pick=st.selectbox('Agent profile',list(PROFILES),key='research_profile')
    symbol=st.text_input('Research symbol','IWM',key='research_symbol')
    if st.button('Evaluate research rules',key='agent_rules'):
        st.json(evaluate(confluence(symbol),pick))
with st.expander('Opt-in autonomous paper simulation monitoring',expanded=False):
    st.caption('This dashboard does not launch background jobs. A separate Railway paper service requires SQL setup and PAPER_AUTO_ENABLED=true.')
    st.dataframe(pd.DataFrame(fetch('paper_agent_events',100)),use_container_width=True)
    st.dataframe(pd.DataFrame(fetch('paper_agent_positions',100)),use_container_width=True)
with st.expander('Signal history and research attribution',expanded=False):
    from core.research_analytics import summarize_signals
    st.json(summarize_signals(fetch('ultimate_signals',500)))
