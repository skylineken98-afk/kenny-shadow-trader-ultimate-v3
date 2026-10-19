import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.settings import symbols,get
from core.market import history,confluence,levels
from core.db import fetch,client
from core.paper import open_paper_trade
from core.chart_ui import make_chart
from core.market_wide import listed_symbols,shortlist
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
def show_chart(symbol,mode,plan=None):
    fig,z=make_chart(symbol,mode,plan)
    if fig is None:
        st.info('No usable candles from the current data provider for this ticker/timeframe.')
        return
    st.plotly_chart(
    fig,
    use_container_width=True,
    key=f"chart_{symbol}_{mode}_{id(fig)}"
)
    if z:
        c1,c2,c3=st.columns(3)
        c1.metric('Underlying last',f"${z['price']:,.2f}")
        c2.metric('Support',f"${z['support']:,.2f}")
        c3.metric('Resistance',f"${z['resistance']:,.2f}")
    st.caption('Candles and levels are for the underlying asset, not the option premium. Data may be delayed; verify at your broker.')

def show_setup(symbol,mode,analysis=None):
    analysis=analysis or confluence(symbol)
    c1,c2,c3=st.columns(3)
    c1.metric('Setup status',analysis.get('status','UNKNOWN'))
    c2.metric('Direction',analysis.get('side','WAIT'))
    c3.metric('Source','Rule-based')
    if analysis.get('status')=='SETUP':
        st.caption('Entry / stop / target below are hypothetical UNDERLYING price levels only.')
        st.write('Underlying entry:',round(analysis['entry'],2),'· Stop:',round(analysis['stop'],2),'· Target:',round(analysis['target'],2))
    show_chart(symbol,mode,analysis if analysis.get('status')=='SETUP' else None)

with tabs[0]:
    st.subheader('Live-style market dashboard · chart-first')
    st.caption('Refresh pulls the latest provider data; this free-data build is not tick-by-tick streaming.')
    symbols_for_dashboard=symbols()
    choice=st.selectbox('View market',symbols_for_dashboard or ['SPY'],key='dash_symbol')
    show_chart(choice,'Swings')
    with st.expander('Latest saved signals'):
        rows=fetch('ultimate_signals',100)
        if rows:
            fields=[f for f in ['created_at','symbol','status','side','entry','stop','target'] if f in rows[0]]
            st.dataframe(pd.DataFrame(rows)[fields],use_container_width=True)
        else:st.info('No stored signals yet.')

def explore(kind,preset):
    st.caption(f'{kind} · Candles, levels, and trend visualization (underlying market).')
    sym=st.text_input('Ticker to inspect',preset,key='ticker_'+kind).upper().strip()
    if sym:
        show_chart(sym,kind)
        with st.expander('Technical scenario (not an options premium recommendation)'):
            if st.button('Evaluate multi-timeframe setup',key='analyze_'+kind):
                a=confluence(sym)
                st.write('Status:',a.get('status'),'· Bias:',a.get('side','WAIT'))
                if a.get('status')=='SETUP':
                    st.write('Underlying entry:',a.get('entry'),'Stop:',a.get('stop'),'Target:',a.get('target'))
for idx,kind,default in [(1,'0DTE','SPY'),(2,'Swings','IWM'),(3,'LEAPS','QQQ'),(4,'Stocks','AAPL'),(5,'Crypto','BTC-USD'),(6,'Forex','EURUSD=X'),(7,'Futures','NQ=F')]:
    with tabs[idx]: explore(kind,default)
with tabs[8]:
    from core.request_signals import discover_contracts,CATEGORIES
    st.subheader('🎯 Request a Signal · 3 best contracts per strategy')
    st.caption('Market-wide DISCOVERY ➜ daily liquidity prescreen ➜ 4H/1H/5M alignment ➜ actual option chain ➜ ranked Top 3. No single required ticker.')
    c1,c2,c3=st.columns(3)
    with c1:budget=st.number_input('Maximum 1-contract cost ($)',30,3000,300,10,key='universe_budget')
    with c2:sample=st.selectbox('Daily prescreen breadth',[60,120,200,400],index=1,key='scan_breadth')
    with c3:rotation=st.number_input('Universe rotation offset',min_value=0,value=0,step=120,key='scan_offset')
    st.caption('An exchange-listing-based rotating sample is screened; NOT a complete, live scan of every stock. This may take several minutes and free feeds can throttle requests.')
    if st.button('🔎 Scan market for Top 3 0DTE + Swings + LEAPS',type='primary',key='request_options'):
        with st.spinner('Discovering listings and ranking liquid underlyings...'):
            all_tickers,listing_notes=listed_symbols()
            screened,screen_notes=shortlist(all_tickers,sample_size=sample,shortlist_size=18,offset=rotation)
        with st.spinner(f'Checking options on {len(screened)} liquid candidates...'):
            found,chain_notes=discover_contracts(screened,budget)
        st.session_state['requested_options']=(found,listing_notes+screen_notes+chain_notes,screened,len(all_tickers))
    if 'requested_options' in st.session_state:
        found,notes,screened,listed_count=st.session_state['requested_options']
        st.caption(f'Listing universe: {listed_count:,} symbols · daily candidates evaluated: {sample} maximum · deep multi-timeframe/options checks: {len(screened)}. Rank score measures liquidity/fit, not profit probability.')
        for group in CATEGORIES:
            st.markdown(f'### {group} — {len(found[group])} / 3 qualifying contracts')
            if not found[group]:st.warning('No verifiable contracts met every rule. Increase scan breadth or rotate the universe; no fabricated substitutes.')
            for i,rec in enumerate(found[group]):
                with st.container(border=True):
                    sym=rec['ticker']
                    st.markdown(f"**#{i+1} · {rec['contract']}**  ·  {rec['right']} · {rec['expiration']} · Strike ${rec['strike']:g}")
                    q1,q2,q3,q4=st.columns(4)
                    q1.metric('Option last',f"${rec['last']:.2f}" if rec['last'] is not None else 'N/A',f"{rec['percent_change']:+.1f}%" if rec['percent_change'] is not None else None)
                    q2.metric('Bid / Ask',f"${rec['bid']:.2f} / ${rec['ask']:.2f}")
                    q3.metric('Ask × 100',f"${rec['cost']:,.0f}")
                    q4.metric('Rank (not odds)',f"{rec['rank_score']:.1f}/100")
                    st.caption(f"Volume: {rec['volume']:,} · OI: {rec['open_interest']:,} · Spread: {rec['spread_pct']:.1f}% · Last option trade: {rec['last_trade_at']}")
                    with st.expander(f'📈 {sym} {"5-minute" if group=="0DTE" else "daily" if group=="Swings" else "weekly"} chart with key levels',expanded=True):
                        show_chart(sym,group)
                    st.caption('Option premium OHLC and valid premium stops/targets are unavailable from this feed. The chart shows UNDERLYING movement, not the contract price. Confirm quotes before decisions.')
        with st.expander(f'Market-data and screening notices ({len(notes)})'):
            for note in notes[:100]:st.caption(note)
        st.warning('Free data may be delayed, incomplete or rate-limited. 0DTE only when same-day contracts exist. No real orders or automated investment advice.')
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
    if submitted:st.write(open_paper_trade(sym,asset,side,entry,stop,target,equity,equity,equity))
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
        st.write(evaluate(confluence(symbol),pick))
        show_chart(symbol,'Swings')
with st.expander('Opt-in autonomous paper simulation monitoring',expanded=False):
    st.caption('This dashboard does not launch background jobs. A separate Railway paper service requires SQL setup and PAPER_AUTO_ENABLED=true.')
    st.dataframe(pd.DataFrame(fetch('paper_agent_events',100)),use_container_width=True)
    st.dataframe(pd.DataFrame(fetch('paper_agent_positions',100)),use_container_width=True)
with st.expander('Signal history and research attribution',expanded=False):
    from core.research_analytics import summarize_signals
    st.write(summarize_signals(fetch('ultimate_signals',500)))
