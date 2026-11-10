import pandas as pd

def history(symbol,period='60d',interval='1h'):
    import yfinance as yf
    df=yf.Ticker(symbol).history(period=period,interval=interval,auto_adjust=True)
    if df is None or df.empty: return pd.DataFrame()
    return df.dropna(subset=['Close']).copy()

def levels(df,interval_minutes=None):
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
    candle_evidence=None
    if interval_minutes:
        from datetime import datetime,timezone
        from kst_options.candles import review_candles
        try:
            rows=[dict(time=t.isoformat(),open=r.Open,high=r.High,low=r.Low,close=r.Close) for t,r in df.tail(50).iterrows()]
            candle_evidence=review_candles(rows,datetime.now(timezone.utc),interval_minutes)
        except (ValueError,TypeError,AttributeError):pass
    from core.trend_quality import trend_quality
    quality=trend_quality(df,trend)
    return {'trend_quality':quality,'candle_evidence':candle_evidence,'price':price,'ema20':float(ema20.iloc[-1]),'ema50':float(ema50.iloc[-1]),'ema200':float(ema200.iloc[-1]),'atr':atr,'rvol':rvol,'support':low,'resistance':high,'trend':trend,'volume':float(vol.iloc[-1])}

def confluence(symbol):
    """Public options/stocks/crypto KST default: volume-confirmed price momentum.

    No 4H / 1H / 5M alignment, FVG or trend-structure prerequisite.
    One-minute bars are observations, NOT a multi-timeframe entry rule.
    """
    from core.momentum_volume import qualify
    from datetime import datetime, timezone
    try:
        candles = history(symbol, period='5d', interval='1m')
        return qualify(candles, symbol=symbol, now=datetime.now(timezone.utc),
                       bar_minutes=1, max_stale_minutes=15)
    except Exception as exc:
        return {'symbol':symbol,'status':'INSUFFICIENT_DATA','side':'WAIT',
                'strategy':'MOMENTUM_VOLUME','reason':type(exc).__name__}
