"""Public LONG stock research plans and observed rule alerts. No broker orders."""
import os,re,uuid
from datetime import timedelta
from .engine import num,quote,parse,stamp,NY,utcnow

def stock_candidate(symbol,snapshot,now,feed):
 q=quote(snapshot.get('latestQuote') or {},now,max_age=60)
 daily=snapshot.get('dailyBar') or {};previous=snapshot.get('prevDailyBar') or {}
 if not q or not re.fullmatch(r'[A-Z][A-Z.]{0,9}',symbol):return None
 bid,ask,t=q
 if bid<=0 or (ask-bid)/((ask+bid)/2)>.01 or (num((snapshot.get('latestQuote') or {}).get('as')) or 0)<1:return None
 close=num(previous.get('c'));volume=num(daily.get('v'));prevvol=num(previous.get('v'));high=num(daily.get('h'));low=num(daily.get('l'))
 try:
  day=parse(daily['t']).astimezone(NY).date();old=parse(previous['t']).astimezone(NY).date()
 except (KeyError,ValueError,TypeError):return None
 if day!=now.astimezone(NY).date() or not 0<(day-old).days<=7 or any(x is None or x<=0 for x in (close,volume,prevvol,high,low)) or high<low:return None
 change=(bid/close-1)*100;ratio=volume/prevvol
 if change<1 or ratio<.5:return None
 risk=round(max(.01*ask,min(high-low,.05*ask)),4)
 return dict(id=str(uuid.uuid4()),symbol=symbol,created_at=stamp(now),quote_at=stamp(t),feed=feed,state='OPEN',entry_ask=ask,last_bid=bid,peak_bid=bid,stop=round(ask-risk,4),target=round(ask+2*risk,4),risk_per_share=risk,due_at=stamp(now+timedelta(days=5)),score=round(min(100,change*5+min(ratio,3)*10),2),reason=f'Positive momentum {change:.2f}% vs previous daily close; volume {ratio:.2f}× previous full day (not time-adjusted RVOL). Rule score is not a probability. Research ask reference; no actual purchase.')

def refresh(store,now,http=None):
 import requests
 http=http or requests.get
 feed=os.getenv('STOCK_FEED','').strip() or 'iex'
 if feed not in ('sip','iex'):raise ValueError('STOCK_FEED must be sip or iex')
 local=now.astimezone(NY)
 if local.weekday()>4 or not 570<=local.hour*60+local.minute<960:return
 symbols=[s.strip().upper() for s in os.getenv('STOCK_SYMBOLS','AAPL,MSFT,NVDA,TSLA,AMD,AMZN,META,GOOGL,SOFI,HOOD').split(',') if re.fullmatch(r'[A-Z][A-Z.]{0,9}',s.strip().upper())][:40]
 opened=store.rows('kst_stock_plans',state='eq.OPEN',order='created_at.asc',limit=100)
 symbols=list(dict.fromkeys(symbols+[r['symbol'] for r in opened]))
 if not symbols:return
 response=http('https://data.alpaca.markets/v2/stocks/snapshots',params={'symbols':','.join(symbols),'feed':feed},headers={'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'],'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET']},timeout=20)
 if not response.ok:raise RuntimeError('Stock data unavailable; check feed entitlement')
 snapshots=response.json();now=utcnow()
 for p in opened:
  q=quote((snapshots.get(p['symbol']) or {}).get('latestQuote') or {},now,max_age=60)
  if q:store.call('POST','rpc/kst_mark_stock',data={'p_id':p['id'],'p_bid':q[0],'p_quote':stamp(q[2])})
 active_symbols={p['symbol'] for p in opened}
 for symbol in symbols:
  if symbol in active_symbols:continue
  # Avoid immediate re-entry after an observed exit; one plan per symbol/day.
  recent=store.rows('kst_stock_plans',symbol='eq.'+symbol,created_at='gte.'+stamp(now-timedelta(days=1)),limit=1)
  if recent:continue
  c=stock_candidate(symbol,snapshots.get(symbol) or {},now,feed)
  if c:store.insert('kst_stock_plans',c,ignore=True)
 store.call('POST','kst_options_health',data={'id':'stocks','updated_at':stamp(now),'status':'OK','message':f'Checked {len(symbols)} configured symbols; feed {feed}. Long momentum research only; no orders. Regular-session clock window; fresh quotes required.'},prefer='resolution=merge-duplicates,return=minimal')
