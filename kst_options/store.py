import os,requests
class Store:
 def __init__(self):
  self.url=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
  key=os.environ['SUPABASE_SERVICE_ROLE_KEY'];self.headers={'apikey':key,'Content-Type':'application/json'}
  if not key.startswith('sb_secret_'):self.headers['Authorization']='Bearer '+key
 def call(self,method,table,params=None,data=None,prefer=None):
  headers=dict(self.headers)
  if prefer:headers['Prefer']=prefer
  r=requests.request(method,self.url+table,params=params,json=data,headers=headers,timeout=30)
  if not r.ok:raise RuntimeError(f'Database {table} HTTP {r.status_code}; verify migration/credentials')
  return r.json() if r.content else []
 def rows(self,table,**params):return self.call('GET',table,params)
 def insert(self,table,data,ignore=False):return self.call('POST',table,data=data,prefer='resolution=ignore-duplicates,return=minimal' if ignore else 'return=minimal')
 def patch(self,table,id,data):return self.call('PATCH',table,{'id':'eq.'+id},data,prefer='return=minimal')
 def health(self,status,message):
  from .engine import utcnow,stamp
  self.call('POST','kst_options_health',data={'id':'options','updated_at':stamp(utcnow()),'status':status,'message':message},prefer='resolution=merge-duplicates,return=minimal')
