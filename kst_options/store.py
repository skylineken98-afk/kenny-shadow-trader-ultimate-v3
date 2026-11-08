"""Bounded database calls. Retry only reads and explicitly idempotent upserts."""
import os,time,re,threading,requests

class DatabaseError(RuntimeError):
 def __init__(self,table,status,code=None):
  self.status_code=status
  self.code=code if code and re.fullmatch(r"[A-Z0-9_]{1,30}",str(code)) else "UNKNOWN"
  super().__init__(f"Database {table} HTTP {status}; code {self.code}")

class Store:
 def __init__(self):
  self.url=os.environ['SUPABASE_URL'].strip().rstrip('/')+'/rest/v1/'
  key=os.environ['SUPABASE_SERVICE_ROLE_KEY'].strip();self.headers={'apikey':key,'Content-Type':'application/json'}
  if not key.startswith('sb_secret_'):self.headers['Authorization']='Bearer '+key
  self._local=threading.local()
 def call(self,method,table,params=None,data=None,prefer=None):
  headers=dict(self.headers)
  if prefer:headers['Prefer']=prefer
  safe=method=='GET' or (method=='POST' and prefer and 'resolution=' in prefer and not table.startswith('rpc/'))
  attempts=3 if safe else 1
  if not hasattr(self._local,'session'):self._local.session=requests.Session()
  for attempt in range(attempts):
   try:
    r=self._local.session.request(method,self.url+table,params=params,json=data,headers=headers,timeout=(5,20))
   except (requests.Timeout,requests.ConnectionError):
    if attempt+1==attempts:raise RuntimeError(f'Database {table} transport timeout/unavailable') from None
    time.sleep(2**attempt);continue
   if not r.ok:
    try:code=r.json().get('code')
    except (ValueError,AttributeError):code=None
    if (r.status_code in (429,502,503,504) or code=='57014') and attempt+1<attempts:
     time.sleep(2**attempt);continue
    raise DatabaseError(table,r.status_code,code)
   return r.json() if r.content else []
 def rows(self,table,**params):return self.call('GET',table,params)
 def insert(self,table,data,ignore=False):return self.call('POST',table,data=data,prefer='resolution=ignore-duplicates,return=minimal' if ignore else 'return=minimal')
 def patch(self,table,id,data):return self.call('PATCH',table,{'id':'eq.'+id},data,prefer='return=minimal')
 def health(self,status,message):
  from .engine import utcnow,stamp
  self.call('POST','kst_options_health',data={'id':'options','updated_at':stamp(utcnow()),'status':status,'message':message},prefer='resolution=merge-duplicates,return=minimal')
