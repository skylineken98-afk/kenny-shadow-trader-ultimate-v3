"""Opt-in Web Push for public paper events and stock research exits. Never logs subscription endpoints."""
import os,json,time,logging
from urllib.parse import urlparse
from .engine import utcnow,stamp

def allowed_endpoint(endpoint):
 try:
  u=urlparse(endpoint);h=u.hostname or ''
  return u.scheme=='https' and u.port in (None,443) and not u.username and not u.password and (h=='fcm.googleapis.com' or h.endswith('.push.apple.com') or h=='updates.push.services.mozilla.com' or h.endswith('.push.services.mozilla.com') or h.endswith('.notify.windows.com'))
 except (ValueError,TypeError):return False

def notification(event):
 title='KST PAPER · '+event['agent']+' · '+event['action']
 body=event['contract']+' · '+str(event['quantity'])+' contract · $'+format(float(event['price']),'.2f')+' premium'
 if event.get('realized_pl') is not None:body+=' · Paper P/L $'+format(float(event['realized_pl']),'.2f')
 return {'title':title,'body':body,'tag':'kst-'+event['id'],'url':'/#progress','event_at':event['created_at']}

def cycle(store,send,stock=False):
 deliveries='kst_stock_push_deliveries' if stock else 'kst_push_deliveries'
 events_table='kst_stock_alerts' if stock else 'kst_trade_activity'
 jobs=store.call('POST','rpc/kst_claim_stock_push' if stock else 'rpc/kst_claim_push',data={})
 for job in jobs:
  subs=store.rows('kst_push_subscriptions',id='eq.'+job['subscription_id'],active='eq.true',limit=1)
  events=store.rows(events_table,id='eq.'+job['event_id'],limit=1)
  if not subs or not events or not allowed_endpoint(subs[0]['endpoint']):store.patch(deliveries,job['id'],{'state':'SKIPPED'});continue
  sub,event=subs[0],events[0]
  # Check again after claim: preference changes and opt-outs take effect before send.
  if ('STOCK_EXIT' if stock else event['action']) not in sub['event_types']:store.patch(deliveries,job['id'],{'state':'SKIPPED'});continue
  try:
   send({'endpoint':sub['endpoint'],'keys':sub['keys']},stock_notification(event) if stock else notification(event))
   store.patch(deliveries,job['id'],{'state':'SENT','sent_at':stamp(utcnow())})
  except Exception as exc:
   status=getattr(exc,'status_code',None)
   response=getattr(exc,'response',None)
   if status is None and response is not None:status=response.status_code
   if status in (404,410):store.patch('kst_push_subscriptions',sub['id'],{'active':False})
   state='FAILED' if status in (404,410) or job['attempts']>=3 else 'PENDING'
   store.patch(deliveries,job['id'],{'state':state})

def stock_notification(event):
 return {'title':'KST STOCK research · '+event['symbol'],'body':event['reason']+' observed near $'+format(float(event['price']),'.2f')+'. Review your plan; no sale executed.','tag':'kst-stock-'+event['id'],'url':'/#stocks','event_at':event['created_at']}

def main():
 from .store import Store
 from pywebpush import webpush
 import requests
 key=os.environ['VAPID_PRIVATE_KEY'];subject=os.environ['VAPID_SUBJECT']
 if not subject.startswith('mailto:'):raise ValueError('VAPID_SUBJECT must be a contact mailto URL')
 session=requests.Session();session.max_redirects=0
 def send(sub,payload):
  webpush(subscription_info=sub,data=json.dumps(payload),vapid_private_key=key,vapid_claims={'sub':subject},ttl=300,timeout=5,requests_session=session)
 store=Store()
 while True:
  for stock in (False,True):
   try:cycle(store,send,stock=stock)
   except Exception:logging.warning('Push cycle failed; check credentials, migration and delivery state')
  try:
   from kst_pro.private_push import cycle as private_cycle
   private_cycle(store,send)
   from kst_pro.ops import beat
   beat(store,'push')
  except Exception:logging.warning('Private push unavailable; check r5 migration and configuration')
  time.sleep(5)
if __name__=='__main__':logging.basicConfig(level=logging.INFO);main()
