"""Server-owned monthly billing and independent administrator gift passes."""
import hashlib,hmac,json,re,time,uuid
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
import requests
from kst_options.engine import parse
from .intro_offer import code_from_input,intro_coupon,intro_checkout_data

def is_admin(user,env):return user in [x.strip() for x in env.get('KST_ADMIN_USER_IDS','').split(',') if x.strip()]

def entitlement(row,now=None):
 now=now or datetime.now(timezone.utc)
 if row.get('paid_lifetime') or row.get('pass_lifetime'):return True
 for name in ('paid_until','pass_until'):
  try:
   if row.get(name) and parse(row[name])>now:return True
  except (ValueError,TypeError):pass
 return False

def status(store,user,env):
 rows=store.rows('kst_memberships',user_id='eq.'+user,limit=1);row=rows[0] if rows else {}
 return {'user_id':user,'pro':entitlement(row) or is_admin(user,env),'admin':is_admin(user,env),'enforced':env.get('MEMBERSHIP_ENFORCED','false')=='true','paid_until':row.get('paid_until'),'pass_until':row.get('pass_until'),'lifetime_pass':bool(row.get('pass_lifetime')),'checkout_available':bool(env.get('STRIPE_SECRET_KEY') and env.get('STRIPE_MONTHLY_PRICE_ID') and env.get('KST_SITE_URL') and env.get('STRIPE_WEBHOOK_SECRET')),'intro_offer':'ENZO or MAYVI: 30 days free, then 50% through first 12 months from signup; one per account'}

def require_access(store,user,env):
 if env.get('MEMBERSHIP_ENFORCED','false')=='true' and not status(store,user,env)['pro']:raise PermissionError('This feature requires Pro membership or an active free pass')

def stripe_call(method,path,env,data=None,params=None,idempotency=None,http=None):
 key=env.get('STRIPE_SECRET_KEY')
 if not key:raise ValueError('Billing is not configured')
 if key.startswith(('sk_live_','rk_live_'))!=(env.get('BILLING_LIVE_MODE','false')=='true'):raise ValueError('Stripe key and configured billing mode do not match')
 headers={'Stripe-Version':'2025-04-30.basil'}
 if idempotency:headers['Idempotency-Key']=idempotency
 r=(http or requests.request)(method,'https://api.stripe.com/v1/'+path,auth=(key,''),data=data,params=params,headers=headers,timeout=20,allow_redirects=False)
 if not r.ok:raise RuntimeError('Payment provider request failed; verify billing configuration')
 return r.json()

def checkout(store,user,body,env):
 if status(store,user,env)['pro']:raise ValueError('An active membership/pass already provides Pro access')
 ident=str(uuid.UUID(str(body.get('request_id'))));price=env.get('STRIPE_MONTHLY_PRICE_ID','')
 site=env.get('KST_SITE_URL','').rstrip('/');u=urlsplit(site)
 if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):raise ValueError('Configure KST_SITE_URL as the production HTTPS origin')
 if not env.get('STRIPE_WEBHOOK_SECRET'):raise ValueError('Stripe webhook signing is required before checkout can accept money')
 if not re.fullmatch(r'price_[A-Za-z0-9]+',price):raise ValueError('Configure the monthly Stripe price')
 price_info=stripe_call('GET','prices/'+price,env)
 if not price_info.get('active') or (price_info.get('recurring') or {}).get('interval')!='month' or (price_info.get('recurring') or {}).get('interval_count',1)!=1:raise ValueError('Configure an active monthly recurring Stripe price')
 code=code_from_input(body.get('promo_code'))
 coupon=intro_coupon(env,stripe_call) if code else None
 reserved=False
 if code:
  reserved=bool(store.call('POST','rpc/kst_reserve_intro',data={'p_user':user,'p_code':code}))
  if not reserved:raise ValueError('An introductory offer is already used or pending for this account. Only one ENZO or MAYVI code is allowed.')
 try:
  checkout_data={
   'mode':'subscription','line_items[0][price]':price,'line_items[0][quantity]':'1',
   'client_reference_id':user,'metadata[kst_user]':user,
   'subscription_data[metadata][kst_user]':user,
   'success_url':site+'/#account','cancel_url':site+'/#account',
   # Short expiry matches the database 40-minute reservation lock.
   'expires_at':str(int(time.time())+31*60)}
  if code:checkout_data.update(intro_checkout_data(code,coupon))
  result=stripe_call('POST','checkout/sessions',env,data=checkout_data,
    idempotency='kst-checkout-'+user+'-'+ident)
  url=result.get('url','');p=urlsplit(url)
  if p.scheme!='https' or p.hostname!='checkout.stripe.com':raise RuntimeError('Unexpected payment destination')
  store.insert('kst_billing_sessions',{'id':result['id'],'user_id':user,'plan':'monthly','intro_code':code},ignore=True)
  return {'url':url,'intro_code':code,'intro_offer_applied':bool(code)}
 except Exception:
  if reserved:
   try:store.call('POST','rpc/kst_release_intro',data={'p_user':user,'p_code':code})
   except Exception:pass
  raise

def portal(store,user,env):
 rows=store.rows('kst_memberships',user_id='eq.'+user,limit=1)
 if not rows or not rows[0].get('customer_id'):raise ValueError('No billing customer is linked to this account')
 site=env.get('KST_SITE_URL','').rstrip('/');u=urlsplit(site)
 if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Configure the production site URL')
 data=stripe_call('POST','billing_portal/sessions',env,data={'customer':rows[0]['customer_id'],'return_url':site+'/#account'})
 p=urlsplit(data.get('url',''))
 if p.scheme!='https' or p.hostname!='billing.stripe.com':raise RuntimeError('Unexpected billing portal destination')
 return {'url':data['url']}

def webhook(store,raw,signature,env,now=None):
 secret=env.get('STRIPE_WEBHOOK_SECRET','')
 if not secret:raise ValueError('Webhook is not configured')
 pieces={};now=now or time.time()
 for part in str(signature or '').split(','):
  k,_,v=part.partition('=');pieces.setdefault(k,[]).append(v)
 try:t=int(pieces['t'][0])
 except (ValueError,KeyError,IndexError):raise ValueError('Invalid webhook signature') from None
 expected=hmac.new(secret.encode(),str(t).encode()+b'.'+raw,hashlib.sha256).hexdigest()
 if abs(now-t)>300 or not any(hmac.compare_digest(expected,v) for v in pieces.get('v1',[])):raise ValueError('Invalid or expired webhook signature')
 event=json.loads(raw)
 if bool(event.get('livemode'))!=(env.get('BILLING_LIVE_MODE','false')=='true'):raise ValueError('Billing mode mismatch')
 kind=event.get('type','');obj=event.get('data',{}).get('object',{})
 if store.rows('kst_billing_events',id='eq.'+event['id'],limit=1):return {'received':True,'duplicate':True}
 if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded'):
  saved=store.rows('kst_billing_sessions',id='eq.'+str(obj.get('id','')),limit=1)
  if not saved:return {'received':True,'ignored':True}
  user=saved[0]['user_id'];sub_id=obj.get('subscription')
 elif kind in ('customer.subscription.updated','customer.subscription.deleted','customer.subscription.created'):
  user=(obj.get('metadata') or {}).get('kst_user');sub_id=obj.get('id')
 else:return {'received':True,'ignored':True}
 try:user=str(uuid.UUID(str(user)))
 except (ValueError,TypeError):return {'received':True,'ignored':True}
 if not isinstance(sub_id,str) or not re.fullmatch(r'sub_[A-Za-z0-9]+',sub_id):return {'received':True,'ignored':True}
 current=stripe_call('GET','subscriptions/'+sub_id,env)
 if (current.get('metadata') or {}).get('kst_user')!=user:raise ValueError('Subscription ownership mismatch')
 items=(current.get('items') or {}).get('data') or []
 allowed=[i for i in items if (i.get('price') or {}).get('id')==env.get('STRIPE_MONTHLY_PRICE_ID')]
 end=max([int(i.get('current_period_end') or current.get('current_period_end') or 0) for i in allowed] or [0])
 until=datetime.fromtimestamp(end,timezone.utc).isoformat() if allowed and current.get('status') in ('active','trialing') and end>now else None
 # Gift passes remain independent of subscription cancellation/failure.
 store.call('POST','rpc/kst_apply_billing',data={'p_event':event['id'],'p_user':user,'p_created':int(event['created']),'p_until':until,'p_lifetime':False,'p_customer':current.get('customer'),'p_subscription':sub_id})
 # Mark promo redeemed only after a Stripe-signed completed checkout
 # verified against server-recorded session and subscription ownership.
 if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded') and saved[0].get('intro_code') and current.get('status') in ('active','trialing'):
  store.call('POST','rpc/kst_redeem_intro',data={'p_user':user,'p_code':saved[0]['intro_code'],'p_session':obj['id']})
 return {'received':True}

def grant(store,actor,body,env):
 if not is_admin(actor,env):raise PermissionError('Administrator access required')
 subject=str(uuid.UUID(str(body.get('user_id'))));action=body.get('action');now=datetime.now(timezone.utc)
 if action not in ('month','lifetime','revoke'):raise ValueError('Select month, lifetime or revoke')
 store.call('POST','rpc/kst_admin_grant_pass',data={'p_actor':actor,'p_subject':subject,'p_action':action})
 return {'ok':True}
