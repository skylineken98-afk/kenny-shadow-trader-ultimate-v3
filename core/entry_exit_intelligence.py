"""Research-only direction, entry and potential-exhaustion signals from completed OHLCV bars.

No future knowledge, trade order submission, or claims to identify exact tops.
Stock/underlying values must never be treated as option contract premium quotes.
"""
import math
import pandas as pd

REQUIRED=('Open','High','Low','Close','Volume')

def analyze_completed_bars(bars):
    """Returns an interpretable signal on the supplied *completed* bars only.

    Caller must omit active/incomplete bar and supply timestamped, chronological bars.
    This is a diagnostic research feature, not a validated live trading model.
    """
    if not isinstance(bars,pd.DataFrame) or len(bars)<60 or any(c not in bars for c in REQUIRED):
        return {'status':'INSUFFICIENT_DATA','action':'WAIT','simulation_only':True}
    df=bars.loc[:,list(REQUIRED)].copy()
    for c in REQUIRED: df[c]=pd.to_numeric(df[c], errors='coerce')
    if df.isna().any().any() or not all(math.isfinite(float(x)) for x in df.to_numpy().ravel()):
        return {'status':'INVALID_DATA','action':'WAIT','simulation_only':True}
    if (df['Close']<=0).any() or (df['High']<df['Low']).any() or (df['Volume']<0).any():
        return {'status':'INVALID_DATA','action':'WAIT','simulation_only':True}
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        return {'status':'INVALID_DATA','action':'WAIT','simulation_only':True}
    close=df['Close']; high=df['High']; low=df['Low']; volume=df['Volume']
    fast=close.ewm(span=20,adjust=False).mean()
    slow=close.ewm(span=50,adjust=False).mean()
    ret=close.diff()
    gain=ret.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-ret.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rs=gain.iloc[-1]/loss.iloc[-1] if loss.iloc[-1]>0 else float('inf')
    rsi=100-(100/(1+rs))
    tr=pd.concat([(high-low),(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.rolling(14).mean().iloc[-1]); price=float(close.iloc[-1])
    volbase=float(volume.iloc[-21:-1].mean())
    rvol=float(volume.iloc[-1])/volbase if volbase>0 else 0.0
    high_prev=float(high.iloc[-21:-1].max()); low_prev=float(low.iloc[-21:-1].min())
    direction='UP' if fast.iloc[-1]>slow.iloc[-1] and price>fast.iloc[-1] else ('DOWN' if fast.iloc[-1]<slow.iloc[-1] and price<fast.iloc[-1] else 'MIXED')
    breakout_up=price>high_prev and rvol>=1.2
    breakout_down=price<low_prev and rvol>=1.2
    weakening_up=direction=='UP' and (price<close.iloc[-2] or rsi<55)
    weakening_down=direction=='DOWN' and (price>close.iloc[-2] or rsi>45)
    exhaustion_up=direction=='UP' and rsi>=70 and price<float(high.iloc[-1])
    exhaustion_down=direction=='DOWN' and rsi<=30 and price>float(low.iloc[-1])
    entry='BULLISH_BREAKOUT_CANDIDATE' if breakout_up else ('BEARISH_BREAKOUT_CANDIDATE' if breakout_down else 'WAIT')
    return {'status':'RESEARCH','action':entry,'direction':direction,'price':price,'rsi':round(float(rsi),2),
            'atr':atr,'rvol':round(rvol,2),'prior_resistance':high_prev,'prior_support':low_prev,
            'possible_peak_exhaustion':bool(exhaustion_up),'possible_trough_exhaustion':bool(exhaustion_down),
            'momentum_weakening':bool(weakening_up or weakening_down),
            'risk_note':'Signals are candidate rules, not forecasts; tops/bottoms cannot be known in advance.',
            'simulation_only':True,'live_order_authorized':False}

def exit_research(signal, *, entry_price, current_bid, highest_bid=None, style='adaptive', trailing_fraction=0.10):
    """Evaluate long-instrument exit research from executable-instrument BID values.

    Never substitute underlying stock price for option premium. No order creation.
    """
    if style not in ('quick_profit','trend_runner','adaptive'):
        raise ValueError('Unknown exit style')
    prices=[entry_price,current_bid]
    if highest_bid is not None: prices.append(highest_bid)
    if not all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in prices):
        raise ValueError('Positive finite instrument prices required')
    if not 0 < trailing_fraction < 1: raise ValueError('Invalid trailing fraction')
    high=max(entry_price,current_bid, highest_bid or current_bid)
    ret=(current_bid/entry_price)-1
    trail_breached=current_bid<=high*(1-trailing_fraction) and high>entry_price
    take_profit=(style=='quick_profit' and ret>=.15)
    deterioration=(style=='adaptive' and signal.get('momentum_weakening',False) and ret>0)
    exit_candidate=trail_breached or take_profit or deterioration
    return {'style':style,'exit_candidate':bool(exit_candidate),'reason':('TRAIL' if trail_breached else 'QUICK_PROFIT' if take_profit else 'MOMENTUM' if deterioration else 'HOLD'),
            'estimated_return_pct':round(ret*100,2),'simulation_only':True,'live_order_authorized':False}
