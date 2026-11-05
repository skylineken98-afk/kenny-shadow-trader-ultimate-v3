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
