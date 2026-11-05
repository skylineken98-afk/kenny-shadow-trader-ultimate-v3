"""Delivery always rechecks the authenticated account link and opt-in."""
from kst_options.push_worker import allowed_endpoint
from kst_options.engine import stamp,utcnow

def cycle(store,send):
 for job in store.call('POST','rpc/kst_claim_private_push',data={}):
  subs=store.rows('kst_push_subscriptions',id='eq.'+job['subscription_id'],active='eq.true',limit=1)
  events=store.rows('kst_private_alerts',id='eq.'+job['event_id'],limit=1)
  if not subs or not events:store.patch('kst_private_push_deliveries',job['id'],{'state':'SKIPPED'});continue
  sub,event=subs[0],events[0]
  if sub.get('user_id')!=event['user_id'] or event['kind'] not in sub['event_types'] or not allowed_endpoint(sub['endpoint']):store.patch('kst_private_push_deliveries',job['id'],{'state':'SKIPPED'});continue
  payload={'title':'KST '+('System alert' if event['kind']=='SYSTEM_ALERT' else 'Private stock alert · '+str(event.get('symbol') or '')),'body':event['reason']+('. Review your position; no sale executed.' if event['kind']=='PERSONAL_EXIT' else ''),'tag':'kst-private-'+event['id'],'url':'/#account' if event['kind']=='SYSTEM_ALERT' else '/#positions','event_at':event['created_at']}
  try:
   send({'endpoint':sub['endpoint'],'keys':sub['keys']},payload)
   store.patch('kst_private_push_deliveries',job['id'],{'state':'SENT','sent_at':stamp(utcnow())})
  except Exception as exc:
   response=getattr(exc,'response',None);status=getattr(response,'status_code',None)
   if status in (404,410):store.patch('kst_push_subscriptions',sub['id'],{'active':False})
   store.patch('kst_private_push_deliveries',job['id'],{'state':'FAILED' if status in (404,410) or job['attempts']>=3 else 'PENDING'})
