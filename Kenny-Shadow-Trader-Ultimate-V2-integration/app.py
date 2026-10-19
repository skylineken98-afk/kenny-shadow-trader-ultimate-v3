import os
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from config import DEFAULT_TICKERS,CRYPTO,FOREX
from market_engine import analyze,candles
from scanners import scan
from storage import record_signal,recent_signals,paper_open,paper_close,paper_list
from risk import permit_order

st.set_page_config(page_title='Kenny Shadow Trader V2',layout='wide',page_icon='📈')
st.markdown("""<style>.stApp{background:#090d19;color:#e5e9f4}h1,h2,h3{color:#91b7ff}div[data-testid='stMetric']{background:#121b2e;padding:14px;border-radius:12px}</style>""",unsafe_allow_html=True)
st.title('KENNY SHADOW TRADER V2')
st.caption('Research dashboard and PAPER-only experiment. Not a live broker, options-chain scanner, or verified profit tracker.')
nav=st.sidebar.radio('Markets', ['0DTE','Swings','LEAPS','Stocks','Crypto','Forex','Request a Signal','Market Sentiment','Daily Top 5','Hourly Top 10','Paper Trading','Signal History','News Intelligence'])
st.sidebar.warning('LIVE execution is deliberately disabled. Price feeds may be delayed. Historical returns are not guaranteed.')
if nav in ['0DTE','Swings','LEAPS','Stocks','Crypto','Forex','Request a Signal']:
    if nav in ['0DTE','Swings','LEAPS']:st.info('Underlying trend research only. Actual options chain, premiums, Greeks, spreads, strikes, expiries and fills require an options data integration.')
    universe=CRYPTO if nav=='Crypto' else FOREX if nav=='Forex' else DEFAULT_TICKERS
    ticker=st.text_input('Search ticker',value=universe[0]).strip().upper()
    budget=st.number_input('Research budget ($), no order will be placed',min_value=30,max_value=3000,value=100,step=10)
    if st.button('Analyze ticker',type='primary') and ticker:
        try:
            signal=analyze(ticker)
            record_signal(signal)
            a,b,c=st.columns(3);a.metric('4H trend',signal['4H']);b.metric('1H trend',signal['1H']);c.metric('5M trend',signal['5M'])
            st.subheader('Signal: '+signal['direction']);st.json(signal)
            bars=candles(ticker,'5d','5m').tail(160)
            fig=go.Figure(go.Candlestick(x=bars.index,open=bars.Open,high=bars.High,low=bars.Low,close=bars.Close))
            for key in ['support','resistance']:
                if signal[key] is not None:fig.add_hline(y=signal[key],annotation_text=key)
            fig.update_layout(height=450,template='plotly_dark',xaxis_rangeslider_visible=False)
            st.plotly_chart(fig,use_container_width=True)
        except Exception as ex:st.error(f'Cannot analyze live data: {ex}')
elif nav in ['Hourly Top 10','Daily Top 5']:
    st.subheader(nav+' — limited-universe underlying candidates')
    st.caption('Not whole-market coverage or actual option contracts. On-demand calculation only here.')
    if st.button('Run scan now',type='primary'):
        with st.spinner('Requesting market data...'):results,errors=scan()
        for s in results:record_signal(s)
        st.dataframe(pd.DataFrame(results[:10 if nav=='Hourly Top 10' else 5]),use_container_width=True)
        if errors:st.warning(f'{len(errors)} symbols unavailable');st.json(errors)
elif nav=='Signal History':
    st.subheader('Saved research candidates')
    st.caption('PROPOSED does not mean triggered or filled. Database is local unless configured with durable storage.')
    st.dataframe(pd.DataFrame(recent_signals()),use_container_width=True)
elif nav=='Paper Trading':
    st.subheader('Manual PAPER trade journal')
    st.caption('Entries and exits must be entered manually; these are not broker-simulated fills. No autonomous orders.')
    with st.form('paper'):
        ticker=st.text_input('Ticker',value='SPY');side=st.selectbox('Side',['BUY','SELL']);qty=st.number_input('Quantity',min_value=.001,value=1.0);price=st.number_input('Entry',min_value=.01,value=100.0);equity=st.number_input('Paper equity',min_value=1.,value=10000.);loss=st.number_input('Today paper P/L',value=0.);submit=st.form_submit_button('Log manual paper entry')
        if submit:
            ok,why=permit_order(equity,loss,len([t for t in paper_list() if t['exit'] is None]),sum(t['entry']*t['quantity'] for t in paper_list() if t['exit'] is None),qty*price)
            if ok:paper_open(ticker.upper(),side,qty,price,datetime.now(timezone.utc).isoformat(),'MANUAL PAPER ENTRY');st.success('Paper entry saved')
            else:st.error(why)
    trades=paper_list();st.dataframe(pd.DataFrame(trades),use_container_width=True)
    open_trades=[t for t in trades if t['exit'] is None]
    if open_trades:
        with st.form('close'):
            tid=st.selectbox('Close paper trade ID',[t['id'] for t in open_trades]);exit_price=st.number_input('Exit price',min_value=.01,value=100.);fee=st.number_input('Fees',min_value=0.,value=0.);go=st.form_submit_button('Save paper exit')
            if go:paper_close(tid,exit_price,datetime.now(timezone.utc).isoformat(),fee);st.success('Saved; refresh to see change')
elif nav=='Market Sentiment':
    st.subheader('Market Sentiment')
    st.info('Live market breadth, options positioning, social sentiment and real-time news verification are NOT connected yet. No fabricated bullish/bearish score is displayed.')

elif nav=='News Intelligence':
    from news_intelligence import fetch_news
    from intelligence_storage import upsert_news,recent_news
    st.subheader('Shadow News Intelligence')
    st.caption('Original source headlines and brief excerpts. Keyword-ranked research, NOT verified live market impact or financial advice. Sources retain their own copyright.')
    if st.button('Fetch newest articles',type='primary'):
        with st.spinner('Checking configured sources...'):
            articles,issues=fetch_news()
            st.info(f'{len(articles)} source articles retrieved, {upsert_news(articles)} newly stored.')
            if issues:st.warning('Some feeds are unavailable.');st.json(issues)
    records=recent_news()
    if not records:st.info('No news stored yet. Fetch articles to populate this view. Network/provider availability varies.')
    for story in records[:60]:
        with st.container(border=True):
            st.markdown('### '+story['headline'])
            st.caption(f"{story['source']} • Published: {story['published_at'] or 'Not provided'} • Impact keyword score {story['impact_score']}/100")
            st.write(story['summary'] or 'Open the source for the full story.')
            if story['assets']:st.write('Potentially related markets (NOT price direction): '+', '.join(story['assets']))
            st.link_button('Read original reporting',story['article_url'])
