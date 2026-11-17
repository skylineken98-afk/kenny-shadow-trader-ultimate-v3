"""Source-labeled daily/weekly trendline research, not trade signals.
Anchors use confirmed pivots; recovered history is labeled retrospective.
"""
import hashlib,math,os
from datetime import timedelta
import pandas as pd
from kst_options.engine import NY,stamp
METHOD='confirmed-pivots-v1-linear-calendar-days'

def trendlines(bars,symbol,frame,observed_at):
 if len(bars)<15:return [],[]
 pivots={kind:[] for kind in ('SUPPORT','RESISTANCE')}
 for i in range(3,len(bars)-3):
  window=bars[i-3:i+4]
  for kind,key,choose in [('SUPPORT','low',min),('RESISTANCE','high',max)]:
   value=bars[i][key]
   if value==choose(b[key] for b in window) and sum(b[key]==value for b in window)==1:pivots[kind].append(i)
 lines=[];events=[]
 for kind,indices in pivots.items():
  key='low' if kind=='SUPPORT' else 'high'
  recent=indices[-9:]
  for a,b in zip(recent,recent[1:]):
   if b<=a:continue
   delta=(pd.Timestamp(bars[b]['bar_at'])-pd.Timestamp(bars[a]['bar_at'])).total_seconds()/86400
   if delta<=0:continue
   slope=(bars[b][key]-bars[a][key])/delta
   if (kind=='SUPPORT' and slope<=0) or (kind=='RESISTANCE' and slope>=0):continue
   def project(row):return bars[a][key]+slope*(pd.Timestamp(row['bar_at'])-pd.Timestamp(bars[a]['bar_at'])).total_seconds()/86400
   known=b+3
   # Disallow a proposed line already invalid at identification.
   if any((row['close']<project(row)*.99 if kind=='SUPPORT' else row['close']>project(row)*1.01) for row in bars[a+1:known+1]):continue
   ident=hashlib.sha256(f'{symbol}:{frame}:{kind}:{bars[a]["bar_at"]}:{bars[b]["bar_at"]}:{METHOD}'.encode()).hexdigest()
   line={'id':ident,'symbol':symbol,'timeframe':frame,'kind':kind,'anchor_a_at':bars[a]['bar_at'],'anchor_a_price':bars[a][key],
         'anchor_b_at':bars[b]['bar_at'],'anchor_b_price':bars[b][key],'identified_bar_at':bars[known]['bar_at'],
         'first_observed_at':stamp(observed_at),'method':METHOD,'source':'Yahoo Finance via yfinance; source-reported unadjusted OHLCV',
         'details':{'pivot_confirmation_bars':3,'touch_tolerance_pct':.5,'break_close_tolerance_pct':1,'scale':'linear','retrospective_at_first_collection':True,'is_win_probability':False}}
   lines.append(line);broken=False
   for i in range(known+1,len(bars)):
    row=bars[i];level=project(row)
    if level<=0:continue
    outside=row['close']<level*.99 if kind=='SUPPORT' else row['close']>level*1.01
    touches=row['low']<=level*1.005 and row['high']>=level*.995
    event='BREAK' if outside and not broken else 'RETEST' if touches and broken else 'TOUCH' if touches else None
    if outside:broken=True
    if not event:continue
    prior=[x['volume'] for x in bars[max(0,i-20):i] if x['volume']>0]
    outcomes={str(n):(bars[i+n]['close']/row['close']-1)*100 if i+n<len(bars) else None for n in (1,5,20)}
    events.append({'id':ident+':'+row['bar_at'],'line_id':ident,'symbol':symbol,'timeframe':frame,'bar_at':row['bar_at'],
       'observed_at':stamp(observed_at),'event':event,'level':level,'close':row['close'],'volume':row['volume'],
       'details':{'historical_replay':True,'forward_returns_pct':outcomes,'volume_vs_prior20':row['volume']/(sum(prior)/len(prior)) if prior else None,
                  'outcome_units':'bars of the stated timeframe','no_fill_or_profit_claim':True}})
 return lines,events

def collect(store,now):
 import yfinance as yf
 all_symbols=[s.strip().upper() for s in os.getenv('HISTORICAL_TREND_SYMBOLS','^GSPC,SPY,QQQ,IWM').split(',') if s.strip()][:20]
 import re
 symbols=[s for s in all_symbols if re.fullmatch(r'\^?[A-Z][A-Z.\-]{0,9}',s)]
 if not symbols:raise ValueError('No valid historical trend symbols')
 saved=0;failures=[];latest=[]
 for symbol in symbols:
  try:
   existing=store.rows('kst_historical_bars',symbol='eq.'+symbol,timeframe='eq.1d',select='bar_at',order='bar_at.desc',limit=1)
   df=yf.Ticker(symbol).history(period='10y',interval='1d',auto_adjust=False,timeout=15)
   if df is None or df.empty:raise ValueError('No historical OHLCV')
   df=df.loc[[t.date()<now.astimezone(NY).date() for t in df.index]]
   if df.empty or (now.astimezone(NY).date()-df.index[-1].date()).days>5:raise ValueError('Historical source is stale')
   frames=[('1d',df),('1w',df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna())]
   for frame,data in frames:
    if frame=='1w':data=data.loc[[t.date()<now.astimezone(NY).date() for t in data.index]]
    bars=[]
    for t,r in data.iterrows():
     values=[float(r[k]) for k in ('Open','High','Low','Close','Volume')]
     if not all(math.isfinite(v) for v in values) or min(values[:4])<=0 or values[4]<0:continue
     at=pd.Timestamp(t.date()).tz_localize(NY).replace(hour=16).isoformat()
     bars.append(dict(id=f'{symbol}:{frame}:{t.date()}',symbol=symbol,timeframe=frame,bar_at=at,open=values[0],high=values[1],low=values[2],close=values[3],volume=values[4],source='Yahoo Finance / yfinance; unadjusted; not an executable quote',observed_at=stamp(now)))
    # Initial backfill, then only recent bars; restart safely from persisted history.
    updates=bars if not existing else bars[-20:]
    for i in range(0,len(updates),200):
     store.call('POST','kst_historical_bars',data=updates[i:i+200],prefer='resolution=merge-duplicates,return=minimal');saved+=len(updates[i:i+200])
    lines,events=trendlines(bars,symbol,frame,now)
    # Freeze the initial anchors and first-observed provenance.
    if lines:store.insert('kst_historical_trendlines',lines,ignore=True)
    for i in range(0,len(events),200):store.call('POST','kst_trendline_events',data=events[i:i+200],prefer='resolution=merge-duplicates,return=minimal')
    if bars:latest.append(bars[-1]['bar_at'])
  except Exception as exc:
   from .collection import safe_error
   failures.append(symbol+': '+safe_error(exc))
 if failures:return {'status':'DEGRADED' if saved else 'ERROR','rows_saved':saved,'message':'; '.join(failures)}
 return {'status':'OK','rows_saved':saved,'data_as_of':max(latest) if latest else None,
         'message':f'{len(symbols)} symbols daily/weekly OHLCV and trendline replay saved; source-reported history, not live quotes or learned probabilities'}
