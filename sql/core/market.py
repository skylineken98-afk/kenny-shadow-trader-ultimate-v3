import pandas as pd

def history(symbol,period='60d',interval='1h'):
    import yfinance as yf
    df=yf.Ticker(symbol).history(period=period,interval=interval,auto_adjust=True)
    if df is None or df.empty: return pd.DataFrame()
    return df.dropna(subset=['Close']).copy()

def levels(df):
    if df.empty or len(df)<30: return None
    close=df['Close'].astype(float)
    ema20=close.ewm(span=20,adjust=False).mean()
    ema50=close.ewm(span=50,adjust=False).mean()
    ema200=close.ewm(span=200,adjust=False).mean()
    rng=(df['High'].astype(float)-df['Low'].astype(float))
    true_range=pd.concat([rng,(df['High']-close.shift()).abs(),(df['Low']-close.shift()).abs()],axis=1).max(axis=1)
    atr=float(true_range.rolling(14,min_periods=5).mean().iloc[-1]); price=float(close.iloc[-1])
    vol=df['Volume'].astype(float)
    vavg=float(vol.tail(21).iloc[:-1].mean()) if len(vol)>1 else 0.0
    rvol=(float(vol.iloc[-1])/vavg if vavg>0 else 0.0)
    high=float(df['High'].tail(40).max());low=float(df['Low'].tail(40).min())
    bull=price>float(ema20.iloc[-1])>float(ema50.iloc[-1]);bear=price<float(ema20.iloc[-1])<float(ema50.iloc[-1])
    trend='BULLISH' if bull else 'BEARISH' if bear else 'NEUTRAL'
    return {'price':price,'ema20':float(ema20.iloc[-1]),'ema50':float(ema50.iloc[-1]),'ema200':float(ema200.iloc[-1]),'atr':atr,'rvol':rvol,'support':low,'resistance':high,'trend':trend,'volume':float(vol.iloc[-1])}

def confluence(symbol):
    frames={}
    for key,period,interval in [('4h','180d','1h'),('1h','60d','1h'),('5m','5d','5m')]:
        try:
            df=history(symbol,period,interval)
            if key=='4h' and not df.empty:
                df=df.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
            frames[key]=levels(df)
        except Exception: frames[key]=None
    if any(v is None for v in frames.values()):return {'symbol':symbol,'status':'INSUFFICIENT_DATA','frames':frames}
    directions=[frames[k]['trend'] for k in ('4h','1h','5m')]
    aligned=all(x=='BULLISH' for x in directions) or all(x=='BEARISH' for x in directions)
    f=frames['5m'];side=directions[0] if aligned else 'WAIT'
    stop=f['price']-1.5*f['atr'] if side=='BULLISH' else f['price']+1.5*f['atr'] if side=='BEARISH' else None
    target=f['price']+3*f['atr'] if side=='BULLISH' else f['price']-3*f['atr'] if side=='BEARISH' else None
    return {'symbol':symbol,'status':'SETUP' if aligned else 'WAIT','side':side,'frames':frames,'entry':f['price'] if aligned else None,'stop':stop,'target':target,'confidence_label':'RULE_BASED_ONLY'}
