from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf

def candles(ticker, period='30d',interval='1h'):
    x=yf.download(ticker,period=period,interval=interval,progress=False,auto_adjust=True,threads=False)
    if x is None or x.empty: raise ValueError(f'No price data returned for {ticker} ({period}/{interval})')
    if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
    x=x.rename(columns=str.title).dropna(subset=['Open','High','Low','Close'])
    if x.empty: raise ValueError('No valid bars')
    return x

def bars_4h(x):
    return x.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna(subset=['Close'])

def assess(df):
    if len(df)<25: return {'trend':'UNKNOWN','reason':'Insufficient history','close':float(df.Close.iloc[-1]) if len(df) else None}
    c=df.Close.astype(float);fast=c.ewm(span=12,adjust=False).mean();slow=c.ewm(span=24,adjust=False).mean()
    trend='BULL' if c.iloc[-1]>fast.iloc[-1]>slow.iloc[-1] else 'BEAR' if c.iloc[-1]<fast.iloc[-1]<slow.iloc[-1] else 'MIXED'
    return {'trend':trend,'close':round(float(c.iloc[-1]),4),'support':round(float(df.Low.tail(20).min()),4),'resistance':round(float(df.High.tail(20).max()),4),'ema_fast':round(float(fast.iloc[-1]),4),'ema_slow':round(float(slow.iloc[-1]),4)}

def analyze(ticker):
    h=candles(ticker,'60d','60m'); five=candles(ticker,'5d','5m')
    a,b,c=assess(bars_4h(h)),assess(h),assess(five)
    approved=a['trend']==b['trend']==c['trend'] and a['trend'] in ('BULL','BEAR')
    direction=a['trend'] if approved else 'WAIT'
    price=c['close'];lo=c.get('support');hi=c.get('resistance')
    stop=lo if direction=='BULL' else hi if direction=='BEAR' else None
    target=hi if direction=='BULL' else lo if direction=='BEAR' else None
    if approved and (stop is None or target is None or (direction=='BULL' and not stop<price<target) or (direction=='BEAR' and not target<price<stop)):
        direction='WAIT';approved=False;stop=None;target=None
    return {'ticker':ticker,'asof':datetime.now(timezone.utc).isoformat(),'4H':a['trend'],'1H':b['trend'],'5M':c['trend'],'direction':direction,'entry':price,'stop':stop,'target':target,'support':lo,'resistance':hi,'source':'Yahoo Finance via yfinance; may be delayed/incomplete','valid':approved}
