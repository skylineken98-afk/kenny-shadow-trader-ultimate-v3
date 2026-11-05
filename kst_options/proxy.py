"""After-hours SPX fair-value proxy, NOT an official index or opening forecast."""
import os
from datetime import timedelta
from .engine import parse,num,stamp,NY
_cached=None
_cached_at=None

def estimate(anchor,trade,now,feed):
 result={'kind':'SPY_BASED_SPX_ESTIMATE','anchor_at':anchor.get('at'),'spx_anchor':anchor.get('spx'),'spy_anchor':anchor.get('spy'),'anchor_source':'Matched regular-session minute closes / Yahoo Finance; may be delayed','spy_feed':feed,'spy_at':trade.get('t'),'estimated_spx':None,'status':'UNAVAILABLE','note':'Indicative relationship estimate, not an official SPX quote, tradable index level or next-open prediction. ETF dividends, basis, venue coverage and new overnight information can cause divergence.'}
 spy,spx,current=num(anchor.get('spy')),num(anchor.get('spx')),num(trade.get('p'))
 try:a,t=parse(anchor['at']),parse(trade['t'])
 except (KeyError,ValueError,TypeError):return result
 if a.tzinfo is None or t.tzinfo is None:return result
 if spy is None or spx is None or current is None or min(spy,spx,current)<=0:return result
 local=now.astimezone(NY)
 if local.weekday()<5 and 570<=local.hour*60+local.minute<960:
  result['status']='REGULAR_SESSION';result['note']='Regular-session clock window: use an official SPX quote. Holiday calendars are not supplied.';return result
 if not 0<=(now-t).total_seconds()<=300 or t<a or not 0<=(now-a).total_seconds()<=96*3600:
  result['status']='STALE_OR_MISMATCHED';return result
 result.update(status='ESTIMATE',spy_price=current,spy_move_pct=(current/spy-1)*100,estimated_spx=round(spx*current/spy,2),estimated_point_change=round(spx*(current/spy-1),2))
 return result

def anchor(now):
 global _cached,_cached_at
 if _cached and _cached_at and (now-_cached_at).total_seconds()<900:return _cached
 import yfinance as yf
 spy=yf.Ticker('SPY').history(period='5d',interval='1m',prepost=True,auto_adjust=False)
 spx=yf.Ticker('^GSPC').history(period='5d',interval='1m',prepost=False,auto_adjust=False)
 common=spy.index.intersection(spx.index)
 valid=[]
 for idx in common:
  t=idx.to_pydatetime();local=t.astimezone(NY)
  if local.weekday()<5 and 570<=local.hour*60+local.minute<960 and t+timedelta(minutes=1)<=now:valid.append(idx)
 if not valid:raise RuntimeError('No matched SPY/SPX regular minute anchor')
 idx=max(valid);_cached={'at':stamp(idx.to_pydatetime()+timedelta(minutes=1)),'spy':float(spy.loc[idx,'Close']),'spx':float(spx.loc[idx,'Close'])};_cached_at=now
 return _cached

def refresh(store,now):
 import requests
 feed=os.getenv('STOCK_FEED','sip')
 if feed not in ('sip','iex'):raise ValueError('STOCK_FEED must be sip or iex')
 r=requests.get('https://data.alpaca.markets/v2/stocks/SPY/trades/latest',params={'feed':feed},headers={'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'],'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET']},timeout=20)
 if not r.ok:raise RuntimeError('SPY data access unavailable')
 payload=estimate(anchor(now),r.json().get('trade',{}),now,feed)
 store.call('POST','kst_market_proxy',data={'id':'SPX','updated_at':stamp(now),'payload':payload},prefer='resolution=merge-duplicates,return=minimal')
