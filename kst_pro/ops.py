"""Health evidence and private operator incidents; never sends external messages."""
import os,time,hashlib
from datetime import timedelta
from kst_options.engine import utcnow,stamp,parse

def beat(store,service,status='OK',message='Worker loop completed'):
 store.call('POST','kst_service_heartbeats',data={'id':service,'updated_at':stamp(utcnow()),'status':status,'message':message},prefer='resolution=merge-duplicates,return=minimal')

def heartbeat_loop(service):
 from kst_options.store import Store
 while True:
  try:beat(Store(),service)
  except Exception:pass
  time.sleep(30)

def monitor(store,now,env=os.environ):
 expected=[x.strip() for x in env.get('MONITOR_SERVICES','scanner,options,push,chat,pro').split(',') if x.strip()]
 rows={r['id']:r for r in store.rows('kst_service_heartbeats',limit=40)}
 jobs=store.rows('kst_collection_status',limit=80)
 for job in jobs:
  name='job:'+job['id'];expected.append(name)
  rows[name]={**job,'updated_at':job.get('last_finished_at') or job.get('last_attempt_at'),
              'max_age':max(180,int(job.get('interval_seconds') or 60)*2+120)}
 incidents={r['service']:r for r in store.rows('kst_system_incidents',state='eq.OPEN',limit=100)}
 for service in expected:
  row=rows.get(service)
  try:
   age=(now-parse(row['updated_at'])).total_seconds() if row else -1
   healthy=bool(row and row['status'] in ('OK','MARKET_CLOSED','COLLECTING') and 0<=age<=row.get('max_age',180))
  except (KeyError,ValueError,TypeError):healthy=False
  if healthy:
   if service in incidents:store.patch('kst_system_incidents',incidents[service]['id'],{'state':'RECOVERED','recovered_at':stamp(now)})
  elif service not in incidents:
   ident=service+':'+str(int(now.timestamp()//180))
   store.insert('kst_system_incidents',{'id':ident,'service':service,'state':'OPEN'})
   for user in [x.strip() for x in env.get('KST_ADMIN_USER_IDS','').split(',') if x.strip()]:
    import uuid
    try:user=str(uuid.UUID(user))
    except ValueError:continue
    store.insert('kst_private_alerts',{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,ident+user)),'user_id':user,'kind':'SYSTEM_ALERT','reason':service+' collector missing, stale, degraded or failed. Check collection status; no fresh data claimed.'},ignore=True)
 for request in store.rows('kst_data_requests',status='eq.RUNNING',attempts='gte.3',lease_until='lt.'+stamp(now),limit=100):store.patch('kst_data_requests',request['id'],{'status':'ERROR'})
 # Crash recovery is observable. Never re-send uncertain broker orders here.
 stale=store.rows('kst_chat_turns',status='eq.PENDING',created_at='lt.'+stamp(now-timedelta(minutes=5)),limit=100)
 for row in stale:store.patch('kst_chat_turns',row['id'],{'status':'FAILED'})


def health(store,ident,status,message,now=None):
 store.call('POST','kst_options_health',data={'id':ident,'updated_at':stamp(now or utcnow()),'status':status,'message':message},prefer='resolution=merge-duplicates,return=minimal')

