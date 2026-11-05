import os,requests
class ProviderError(RuntimeError):
 def __init__(self,status_code):
  self.status_code=int(status_code)
  super().__init__('Alpaca HTTP '+str(self.status_code)+'; check options entitlement, symbol support and keys')

class Provider:
 def __init__(self):
  self.headers={'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'].strip(),'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET'].strip()}
  self.feed=os.getenv('OPTIONS_FEED','opra')
  if self.feed not in ('opra','indicative'):raise ValueError('OPTIONS_FEED must be opra or indicative')
 def get(self,path,params):
  r=requests.get('https://data.alpaca.markets'+path,params={**params,**({'feed':self.feed} if '/snapshots/' in path or '/quotes/' in path else {})},headers=self.headers,timeout=30)
  if not r.ok:raise ProviderError(r.status_code)
  return r.json()
 def chain(self,symbol,lo,hi):
  params={'expiration_date_gte':str(lo),'expiration_date_lte':str(hi),'limit':1000}
  seen=set()
  while True:
   data=self.get('/v1beta1/options/snapshots/'+symbol,params)
   yield from data.get('snapshots',{}).items()
   token=data.get('next_page_token')
   if not token:return
   if token in seen:raise RuntimeError('Repeated options page token')
   seen.add(token);params['page_token']=token
 def quotes(self,contracts):
  result={}
  for i in range(0,len(contracts),100):
   result.update(self.get('/v1beta1/options/quotes/latest',{'symbols':','.join(contracts[i:i+100])}).get('quotes',{}))
  return result

 def daily_volumes(self, contracts, now):
  """Cumulative 1-hour option bars, same-time-of-day historical comparison.

  Indicative option history is delayed; do not request up to the current
  minute or compare today's partial session to prior full daily bars.
  """
  from datetime import timedelta,datetime
  from zoneinfo import ZoneInfo
  ny=ZoneInfo('America/New_York')
  safe_end=now-timedelta(minutes=20) if self.feed=='indicative' else now
  cutoff=safe_end.astimezone(ny)
  today=cutoff.date()
  found={}
  for i in range(0,len(contracts),30):
   batch=contracts[i:i+30]
   params={'symbols':','.join(batch),'timeframe':'1Hour',
           'start':str(today-timedelta(days=18)),'end':safe_end.isoformat(),
           'limit':10000}
   pages=0
   while True:
    data=self.get('/v1beta1/options/bars',params)
    for sym,bars in (data.get('bars') or {}).items():
     found.setdefault(sym,[]).extend(bars)
    token=data.get('next_page_token')
    if not token:break
    pages+=1
    if pages>=5:raise RuntimeError('Option bars pagination limit; incomplete')
    params['page_token']=token
  output={}
  for sym,bars in found.items():
   daily={};seen={}
   for row in bars:
    try:
     t=datetime.fromisoformat(row['t'].replace('Z','+00:00')).astimezone(ny)
     v=int(row['v'])
     if v<0 or (t.hour,t.minute)>(cutoff.hour,cutoff.minute):continue
     daily[t.date()]=daily.get(t.date(),0)+v
     if t.date()==today and (today not in seen or t>seen[today]):seen[today]=t
    except (KeyError,ValueError,TypeError,OverflowError):continue
   if today not in daily:continue
   previous=[v for d,v in sorted(daily.items()) if d<today]
   output[sym]={'volume':daily[today],
                'as_of':seen[today].isoformat() if today in seen else cutoff.isoformat(),
                'historical_volume':previous[-5:],
                'current_session':True,
                'delayed':self.feed=='indicative',
                'method':'1Hour option aggregates, prior sessions limited to same local clock cutoff'}
  return output

 def open_interest(self, contract, now):
  """Read only Alpaca paper Trading API contract metadata (no orders)."""
  from datetime import date
  import requests
  r=requests.get('https://paper-api.alpaca.markets/v2/options/contracts/'+contract,
                 headers=self.headers,timeout=10,allow_redirects=False)
  if not r.ok:raise ProviderError(r.status_code)
  item=r.json()
  value=item.get('open_interest')
  try:
   oi=int(value)
   observed=date.fromisoformat(item['open_interest_date'])
   if oi<0 or (now.date()-observed).days not in range(0,8):return None
  except (ValueError,TypeError,KeyError):return None
  return {'open_interest':oi,'date':str(observed)}
