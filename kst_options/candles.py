"""Small deterministic pattern review over completed OHLC candles, not forecasts."""
from .engine import num,parse

def review_candles(rows,now,minutes):
 """Rows use candle OPEN timestamps. Excludes still-forming/invalid candles.
 Follow-through uses up to three subsequent closes, with pattern extremes as
 reference levels. It is descriptive, not a probability or causal test.
 """
 from datetime import timedelta
 bars=[]
 for row in rows:
  try:
   t=parse(row['time']);o,h,l,c=(num(row[k]) for k in ('open','high','low','close'))
   if t.tzinfo is None or t+timedelta(minutes=minutes)>now:continue
   if None in (o,h,l,c) or l>min(o,c) or h<max(o,c) or h<=l:continue
  except (KeyError,ValueError,TypeError):continue
  if bars and t<=bars[-1]['time']:raise ValueError('Candle times must be strictly chronological')
  bars.append(dict(time=t,open=o,high=h,low=l,close=c))
 patterns=[]
 for i,b in enumerate(bars):
  span=b['high']-b['low'];body=abs(b['close']-b['open']);upper=b['high']-max(b['open'],b['close']);lower=min(b['open'],b['close'])-b['low'];found=[]
  if body<=span*.1:found.append(('DOJI','NEUTRAL'))
  if span*.1<body<=span*.35 and lower>=body*2 and upper<=body*.5:found.append(('LOWER_WICK_REJECTION','BULLISH'))
  if span*.1<body<=span*.35 and upper>=body*2 and lower<=body*.5:found.append(('UPPER_WICK_REJECTION','BEARISH'))
  if i:
   p=bars[i-1]
   if b['close']>b['open'] and p['close']<p['open'] and b['open']<=p['close'] and b['close']>=p['open']:found.append(('BULLISH_ENGULFING','BULLISH'))
   if b['close']<b['open'] and p['close']>p['open'] and b['open']>=p['close'] and b['close']<=p['open']:found.append(('BEARISH_ENGULFING','BEARISH'))
   if b['high']<p['high'] and b['low']>p['low']:found.append(('INSIDE_BAR','NEUTRAL'))
  for name,direction in found:
   later=bars[i+1:i+4];above=any(x['close']>b['high'] for x in later);below=any(x['close']<b['low'] for x in later)
   state='PENDING' if not later else 'MIXED' if above and below else 'UPSIDE_CLOSE_BREAK' if above else 'DOWNSIDE_CLOSE_BREAK' if below else 'NO_CLOSE_BREAK'
   reaction='PENDING' if not later else 'MIXED' if above and below else 'CONFIRMED' if (direction=='BULLISH' and above) or (direction=='BEARISH' and below) else 'INVALIDATED' if (direction=='BULLISH' and below) or (direction=='BEARISH' and above) else 'UNCONFIRMED'
   patterns.append({'pattern':name,'direction_hypothesis':direction,'time':b['time'].isoformat(),'high':b['high'],'low':b['low'],'subsequent_closed_bars':len(later),'visible_reaction':state,'directional_follow_through':reaction})
 return {'as_of':now.isoformat(),'completed_bars':len(bars),'patterns':patterns[-10:],'method':'OHLC shape heuristics. Rejection shapes require trend context before calling them hammer/shooting star. Reaction uses up to three subsequent closes beyond pattern extremes, not wicks. No backtested success rate, prediction or causal claim.'}
