"""Licensed provider inputs; headline links only. Never invent missing events."""
import hashlib,os,re
from datetime import date,timedelta,datetime,timezone
from urllib.parse import urlsplit
import requests
from kst_options.engine import num,quote,parse,stamp,NY

def ticker(value):
 value=str(value or '').strip().upper()
 if not re.fullmatch(r'[A-Z][A-Z.\-]{0,9}',value):raise ValueError('Enter a valid ticker symbol')
 return value

def safe_link(value):
 try:
  u=urlsplit(value)
  return u.scheme=='https' and bool(u.hostname) and not u.username and not u.password and u.port in (None,443)
 except (ValueError,TypeError):return False

def finnhub(path,params,env=os.environ,http=None):
 key=env.get('FINNHUB_API_KEY')
 if not key:raise ValueError('Configure FINNHUB_API_KEY for earnings and company news')
 r=(http or requests.get)('https://finnhub.io/api/v1/'+path,params=params,headers={'X-Finnhub-Token':key},timeout=20,allow_redirects=False)
 if not r.ok:raise RuntimeError('Market provider unavailable; check credentials, quota and entitlement')
 data=r.json()
 if isinstance(data,dict) and 'error' in data:raise RuntimeError('Market provider rejected the request')
 return data

def normalize_earnings(data,now):
 rows={};today=now.astimezone(NY).date()
 for event in data.get('earningsCalendar',[])[:3000]:
  try:symbol=ticker(event['symbol']);day=date.fromisoformat(event['date'])
  except (KeyError,ValueError,TypeError):continue
  if not today<=day<=today+timedelta(days=21):continue
  ident=symbol+':'+str(day)
  rows[ident]={'id':ident,'symbol':symbol,'report_date':str(day),'timing':{'bmo':'BEFORE_OPEN','amc':'AFTER_CLOSE','dmh':'DURING_SESSION'}.get(event.get('hour'),'UNCONFIRMED'),'eps_estimate':num(event.get('epsEstimate')),'revenue_estimate':num(event.get('revenueEstimate')),'source':'Finnhub provider calendar; confirm company investor-relations announcement','fetched_at':stamp(now),'active':True,'details':{'schedule_status':'PROVIDER_REPORTED','expected_move':None,'historical_reactions':None}}
 return list(rows.values())

def refresh_earnings(store,now):
 day=now.astimezone(NY).date();data=finnhub('calendar/earnings',{'from':str(day),'to':str(day+timedelta(days=21))})
 rows=normalize_earnings(data,now)
 store.call('POST','rpc/kst_replace_earnings',data={'p_rows':rows,'p_from':str(day),'p_to':str(day+timedelta(days=21))})
 return len(rows)

def refresh_company(store,symbol,now):
 symbol=ticker(symbol);day=now.astimezone(NY).date();items=finnhub('company-news',{'symbol':symbol,'from':str(day-timedelta(days=7)),'to':str(day)})
 rows={}
 for item in items[:150]:
  try:
   t=datetime.fromtimestamp(float(item['datetime']),timezone.utc);url=item['url'];title=str(item['headline']).strip()[:300]
  except (KeyError,ValueError,TypeError,OverflowError):continue
  if not title or not safe_link(url) or not 0<=(now-t).total_seconds()<=7*86400:continue
  ident=hashlib.sha256((symbol+url).encode()).hexdigest();text=title.lower()
  category='Earnings' if any(w in text for w in ('earnings','guidance','quarterly')) else 'Filings' if any(w in text for w in ('10-k','10-q','sec filing','8-k')) else 'Company'
  rows[ident]=dict(id=ident,symbol=symbol,title=title,url=url,source=str(item.get('source') or 'Finnhub')[:80],published_at=stamp(t),fetched_at=stamp(now),category=category)
 if rows:store.call('POST','kst_company_news',data=list(rows.values()),prefer='resolution=merge-duplicates,return=minimal')
 return len(rows)

def expected_move(chain,spot,event_day,timing,now):
 """Same-strike near-ATM straddle mid, not a probability or precise forecast."""
 from kst_options.engine import candidate
 if not num(spot) or spot<=0:return None
 earliest=event_day+timedelta(days=1 if timing=='AFTER_CLOSE' else 0);pairs={}
 for contract,snapshot in chain:
  c=candidate(contract,snapshot,now,'opra',relaxed=True)
  if not c:continue
  expiry=date.fromisoformat(c['expiration'])
  if not earliest<=expiry<=earliest+timedelta(days=14) or abs(c['strike']/spot-1)>.02:continue
  q=quote(snapshot.get('latestQuote') or {},now)
  if not q:continue
  if (q[1]-q[0])/((q[0]+q[1])/2)>.15:continue
  pairs.setdefault((expiry,c['strike']),{})[c['option_type']]=(q[0]+q[1])/2
 valid=[(key,p) for key,p in pairs.items() if 'CALL' in p and 'PUT' in p]
 if not valid:return None
 (expiry,strike),pair=min(valid,key=lambda r:(r[0][0],abs(r[0][1]-spot)))
 move=pair['CALL']+pair['PUT']
 return dict(dollars=round(move,4),percent=round(move/spot*100,2),expiration=str(expiry),strike=strike,as_of=stamp(now),method='Near-ATM same-expiry call+put midpoint. Premium-implied range, not a confidence interval. IV crush and spreads can dominate results.')

def historical_reactions(events,bars):
 """Daily before/after closes. Timing must be supplied; no intraday path claim."""
 ordered=sorted(bars,key=lambda b:b['date']);out=[]
 for event in events:
  if event.get('hour') not in ('bmo','amc'):continue
  try:day=date.fromisoformat(event['date'])
  except (KeyError,ValueError):continue
  following=[b for b in ordered if date.fromisoformat(b['date'])>=day] if event['hour']=='bmo' else [b for b in ordered if date.fromisoformat(b['date'])>day]
  if not following:continue
  after=following[0];before=[b for b in ordered if b['date']<after['date']]
  if not before or not num(before[-1]['close']) or not num(after['close']):continue
  if (date.fromisoformat(after['date'])-day).days>5:continue
  out.append({'report_date':str(day),'timing':event['hour'],'before_close_date':before[-1]['date'],'after_close_date':after['date'],'close_to_close_pct':round((after['close']/before[-1]['close']-1)*100,3)})
 return out[-8:]

def enrich_earnings(store,symbol,now):
 """On-demand extras. Missing entitlement leaves values unavailable."""
 symbol=ticker(symbol);upcoming=store.rows('kst_earnings',symbol='eq.'+symbol,active='eq.true',report_date='gte.'+str(now.astimezone(NY).date()),order='report_date.asc',limit=1)
 if not upcoming:return
 row=upcoming[0];details=dict(row.get('details') or {})
 try:
  import yfinance as yf
  data=yf.Ticker(symbol).history(period='1y',interval='1d',auto_adjust=False)
  bars=[{'date':str(t.date()),'close':float(r.Close)} for t,r in data.iterrows() if t.date()<now.astimezone(NY).date()]
  history=finnhub('calendar/earnings',{'symbol':symbol,'from':str(now.date()-timedelta(days=365)),'to':str(now.date()-timedelta(days=1))})
  details['historical_reactions']=historical_reactions(history.get('earningsCalendar',[]),bars)
  details['historical_source']='Finnhub schedule + Yahoo daily closes; may be delayed/unadjusted; corporate actions can distort reactions'
 except Exception:details['historical_status']='UNAVAILABLE'
 try:
  from kst_options.provider import Provider
  provider=Provider()
  if provider.feed=='opra':
   r=requests.get('https://data.alpaca.markets/v2/stocks/'+symbol+'/snapshot',params={'feed':os.getenv('STOCK_FEED','iex') or 'iex'},headers=provider.headers,timeout=20)
   r.raise_for_status();q=quote(r.json().get('latestQuote') or {},now)
   day=date.fromisoformat(row['report_date'])
   if q:details['expected_move']=expected_move(provider.chain(symbol,day,day+timedelta(days=15)),(q[0]+q[1])/2,day,row['timing'],now)
 except Exception:details['options_status']='UNAVAILABLE'
 store.patch('kst_earnings',row['id'],{'details':details})
