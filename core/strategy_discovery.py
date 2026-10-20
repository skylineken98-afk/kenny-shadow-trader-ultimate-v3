"""Deterministic multi-strategy RESEARCH LAB. No broker side effects.

OHLCV input: properly timestamped, completed historical bars. All outputs are
research hypotheses, not approved trading signals. Every fill is simulated at
NEXT bar's open, after a decision based only on prior completed bars.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from itertools import product
import hashlib, json, math
import numpy as np
import pandas as pd

FAMILIES = ('ema_trend','donchian_breakout','bollinger_reversion',
            'momentum','rsi_reversal','volatility_breakout')
THEMES = {
 'trend':['EMA continuation','EMA ribbon','ADX trend confirmation','Donchian trend','Moving average crossover','Trend-day pullback','Weekly base breakout','Sector strength rotation','Relative strength momentum'],
 'momentum':['Volume surge','Opening range breakout','Gap and go','Momentum acceleration','Previous-day high breakout','Opening drive','Afternoon continuation','Relative volume expansion'],
 'pullback':['EMA retracement','VWAP reclaim','Anchored VWAP pullback','Fibonacci pullback','Breakout retest','Support bounce','Trend first pullback'],
 'reversal':['Double top or bottom','Liquidity sweep','Failed breakout','RSI divergence','Exhaustion','Market structure CHoCH','BOS retest','Supply demand bounce'],
 'mean_reversion':['Bollinger reversion','VWAP deviation','Price z-score','Oversold bounce','Range fade','Pairs reversion'],
 'volatility':['ATR breakout','Volatility expansion','IV vs RV spread','Earnings IV crush','Gamma exposure shift','Options skew divergence'],
 'flow':['Unusual options volume','Dark-pool prints','Open interest changes','Dealer positioning','Institutional filings'],
 'events':['Post earnings drift','News catalyst','Analyst revision','Sympathy trading','Sector news rotation'],
 'quant':['Cointegration','Cross sectional momentum','Factor rotation','Statistical arbitrage','Calendar effect'],
 'crypto_forex':['Crypto funding divergence','Crypto liquidation sweep','Crypto basis','FX session breakout','FX carry']
}
CATALOG=tuple({'name':n,'category':category,'implementation':'research_spec_only'} for category, names in THEMES.items() for n in names)

@dataclass(frozen=True)
class Candidate:
    family:str
    fast:int=10
    slow:int=30
    threshold:float=0.01
    holding_bars:int=5
    def __post_init__(self):
        if self.family not in FAMILIES or not 2 <= self.fast < self.slow <= 250 or not 0 < self.threshold < .3 or not 1 <= self.holding_bars <= 50:
            raise ValueError('Invalid research candidate')
    @property
    def name(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()[:16]

def candidates(max_candidates=60):
    """Generate distinct, bounded testable hypotheses; not self-modifying code."""
    if not 1 <= int(max_candidates) <= 1000: raise ValueError('invalid research cap')
    combos=(Candidate(family,fast,slow,thr,hold) for family,fast,slow,thr,hold in
        product(FAMILIES,(8,12,20),(30,55),(.008,.018),(3,7)))
    return list(__import__('itertools').islice(combos,int(max_candidates)))

def _bars(bars):
    if not isinstance(bars,pd.DataFrame) or len(bars)<80: raise ValueError('At least 80 timestamped OHLCV bars required')
    if not all(c in bars for c in ('Open','High','Low','Close','Volume')): raise ValueError('OHLCV columns required')
    if not isinstance(bars.index,pd.DatetimeIndex) or bars.index.tz is None or bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValueError('Unique, ordered timezone-aware bar timestamps required')
    frame=bars[['Open','High','Low','Close','Volume']].astype(float).copy()
    if not np.isfinite(frame.to_numpy()).all() or (frame[['Open','High','Low','Close']]<=0).any().any() or (frame['Volume']<0).any() or (frame['Low']>frame['High']).any():
        raise ValueError('invalid bar prices')
    return frame

def decisions(bars,candidate):
    b=_bars(bars);c=b.Close
    fast=c.ewm(span=candidate.fast,adjust=False).mean()
    slow=c.ewm(span=candidate.slow,adjust=False).mean()
    rolling_high=b.High.shift(1).rolling(candidate.slow).max()
    rolling_low=b.Low.shift(1).rolling(candidate.slow).min()
    momentum=c.pct_change(candidate.fast)
    ma=c.rolling(candidate.slow).mean();std=c.rolling(candidate.slow).std().replace(0,np.nan)
    z=(c-ma)/std
    delta=c.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean().replace(0,np.nan)
    rsi=100-100/(1+gain/loss)
    atr=pd.concat([(b.High-b.Low),(b.High-c.shift()).abs(),(b.Low-c.shift()).abs()],axis=1).max(axis=1).rolling(14).mean()
    f=candidate.family
    if f=='ema_trend':raw=np.where(fast>slow,1,-1)
    elif f=='donchian_breakout':raw=np.where(c>rolling_high,1,np.where(c<rolling_low,-1,0))
    elif f=='bollinger_reversion':raw=np.where(z< -1.7,1,np.where(z>1.7,-1,0))
    elif f=='momentum':raw=np.where(momentum>candidate.threshold,1,np.where(momentum< -candidate.threshold,-1,0))
    elif f=='rsi_reversal':raw=np.where(rsi<30,1,np.where(rsi>70,-1,0))
    else:raw=np.where((c-c.shift(candidate.fast))>atr*1.5,1,np.where((c-c.shift(candidate.fast))< -atr*1.5,-1,0))
    series=pd.Series(raw,index=b.index,dtype=int)
    series.iloc[:candidate.slow+1]=0
    return series

def research_backtest(bars,candidate,fee_bps=5,slippage_bps=5):
    """One-position non-overlapping next-open fills, fixed holding period.

    Simple unit-return model with short results included for comparison only.
    No option-premium, borrow, margin, market-hours, or broker-fill realism.
    """
    b=_bars(bars);d=decisions(b,candidate)
    costs=(float(fee_bps)+float(slippage_bps))*2/10000
    if not 0<=costs<=.1:raise ValueError('invalid costs')
    returns=[];records=[];i=candidate.slow+2
    while i+candidate.holding_bars<len(b):
        direction=int(d.iloc[i-1]);
        if not direction:i+=1;continue
        entry=float(b.Open.iloc[i]);exit_price=float(b.Open.iloc[i+candidate.holding_bars]);gross=direction*(exit_price/entry-1)
        net=gross-costs
        records.append({'decision_at':str(b.index[i-1]),'entry_at':str(b.index[i]),'exit_at':str(b.index[i+candidate.holding_bars]),'direction':direction,'net_return':round(net,8)})
        returns.append(net);i+=candidate.holding_bars+1
    return {'strategy':candidate.name,'family':candidate.family,'trades':len(returns),'mean_return':float(np.mean(returns)) if returns else None,'win_rate':float(np.mean(np.array(returns)>0)) if returns else None,'records':records,'research_only':True}

def walk_forward(bars,candidate,min_train=100,min_test=40):
    b=_bars(bars)
    if len(b)<min_train+min_test:return {'status':'INSUFFICIENT_DATA','research_only':True}
    cut=int(len(b)*.7);cut=max(min_train,min(cut,len(b)-min_test))
    # Provide preceding warmup for signal indicators; only count trades entered in holdout.
    train=research_backtest(b.iloc[:cut],candidate)
    test=research_backtest(b.iloc[max(0,cut-candidate.slow-10):],candidate)
    test['records']=[x for x in test['records'] if pd.Timestamp(x['entry_at'])>=b.index[cut]]
    rr=[x['net_return'] for x in test['records']]
    test['trades']=len(rr);test['mean_return']=sum(rr)/len(rr) if rr else None
    test['win_rate']=sum(x>0 for x in rr)/len(rr) if rr else None
    return {'status':'EVALUATED','cutoff':str(b.index[cut]),'training':train,'holdout':test,'auto_promote':False,'research_only':True}
