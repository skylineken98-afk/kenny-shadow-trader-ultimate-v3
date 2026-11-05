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
  r=requests.get('https://data.alpaca.markets'+path,params={**params,'feed':self.feed},headers=self.headers,timeout=30)
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
  """Aggregate volume bars; missing historical bars are NOT zero-volume."""
  from datetime import timedelta,datetime
  from zoneinfo import ZoneInfo
  ny=ZoneInfo('America/New_York')
  today=now.astimezone(ny).date()
  found={}
  for i in range(0,len(contracts),30):
   batch=contracts[i:i+30]
   params={'symbols':','.join(batch),'timeframe':'1Day',
           'start':str(today-timedelta(days=18)),'end':now.isoformat(),
           'limit':10000}
   page_count=0
   while True:
    data=self.get('/v1beta1/options/bars',params)
    for sym,bars in data.get('bars',{}).items():
     if sym in found:found[sym].extend(bars)
     else:found[sym]=list(bars)
    token=data.get('next_page_token')
    if not token:break
    page_count+=1
    if page_count>=5:raise RuntimeError('Option bars pagination limit; incomplete')
    params['page_token']=token
  output={}
  for sym,bars in found.items():
   dated=[]
   for row in bars:
    try:
     day=datetime.fromisoformat(row['t'].replace('Z','+00:00')).astimezone(ny).date()
     v=int(row['v'])
     if v<0:continue
     dated.append((day,v,row['t']))
    except (KeyError,ValueError,TypeError):continue
   dated.sort()
   current=[row for row in dated if row[0]==today]
   prior=[row[1] for row in dated if row[0]<today]
   latest=current[-1] if current else (dated[-1] if dated else None)
   if latest:
    output[sym]={'volume':latest[1],
                 'as_of':latest[2],
                 'historical_volume':prior,
                 'current_session':bool(current)}
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
