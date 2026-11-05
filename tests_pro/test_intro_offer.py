import uuid,json,hmac,hashlib
import pytest
from kst_pro.intro_offer import code_from_input,intro_coupon,intro_checkout_data
from kst_pro import membership

USER=str(uuid.uuid4())

class Store:
 def __init__(self):
  self.data={};self.calls=[];self.locked=False
 def rows(self,table,**params):
  rows=self.data.get(table,[])
  for k,v in params.items():
   if isinstance(v,str) and v.startswith('eq.'):rows=[x for x in rows if str(x.get(k))==v[3:]]
  return rows
 def call(self,method,table,params=None,data=None,**kw):
  self.calls.append((table,data))
  if table=='rpc/kst_reserve_intro':
   if self.locked:return False
   self.locked=True;return True
  if table=='rpc/kst_release_intro':
   self.locked=False;return True
  return True
 def insert(self,table,row,**kw):self.data.setdefault(table,[]).append(row)

ENV={'STRIPE_SECRET_KEY':'sk_test_owner_only_for_checkout','STRIPE_WEBHOOK_SECRET':'hook_secret',
     'STRIPE_MONTHLY_PRICE_ID':'price_monthly','KST_SITE_URL':'https://kst.example',
     'STRIPE_INTRO_COUPON_ID':'kst_half_year'}

def fake_stripe(method,path,env,data=None,**kwargs):
 if method=='GET' and path.startswith('prices/'):
  return {'active':True,'recurring':{'interval':'month','interval_count':1}}
 if method=='GET' and path.startswith('coupons/'):
  return {'valid':True,'percent_off':50,'duration':'repeating','duration_in_months':12}
 if method=='POST' and path=='checkout/sessions':
  assert data['mode']=='subscription'
  return {'id':'cs_intro_test','url':'https://checkout.stripe.com/test'}
 if method=='GET' and path.startswith('subscriptions/'):
  return {'metadata':{'kst_user':USER},'status':'trialing','customer':'cus_trial',
          'items':{'data':[{'price':{'id':'price_monthly'},'current_period_end':2147483647}]}}
 raise AssertionError((method,path))

def test_two_case_insensitive_codes_share_one_offer():
 assert code_from_input(' Enzo ')=='ENZO'
 assert code_from_input('mayvi')=='MAYVI'
 for code in ('ENZO','MAYVI'):
  params=intro_checkout_data(code,'kst_half_year')
  assert params['subscription_data[trial_period_days]']=='30'
  assert params['discounts[0][coupon]']=='kst_half_year'
 with pytest.raises(ValueError):code_from_input('ENZO+MAYVI')
 with pytest.raises(ValueError):code_from_input('FAKE')

def test_coupon_must_match_first_year_half_off():
 assert intro_coupon(ENV,fake_stripe)=='kst_half_year'
 with pytest.raises(ValueError):intro_coupon({**ENV,'STRIPE_INTRO_COUPON_ID':''},fake_stripe)
 def bad(*args,**kwargs):return {'valid':True,'percent_off':70,'duration':'repeating','duration_in_months':12}
 with pytest.raises(ValueError):intro_coupon(ENV,bad)

def test_checkout_links_promo_to_signed_in_user(monkeypatch):
 monkeypatch.setattr(membership,'stripe_call',fake_stripe)
 db=Store()
 result=membership.checkout(db,USER,{'request_id':str(uuid.uuid4()),'promo_code':'Enzo','user_id':str(uuid.uuid4())},ENV)
 assert result['intro_code']=='ENZO' and result['intro_offer_applied']
 assert db.data['kst_billing_sessions'][0]['intro_code']=='ENZO'
 assert db.data['kst_billing_sessions'][0]['user_id']==USER
 assert db.calls[0]==('rpc/kst_reserve_intro',{'p_user':USER,'p_code':'ENZO'})
 with pytest.raises(ValueError):membership.checkout(db,USER,{'request_id':str(uuid.uuid4()),'promo_code':'MAYVI'},ENV)

def test_unsigned_or_canceled_checkout_never_redeems_code(monkeypatch):
 monkeypatch.setattr(membership,'stripe_call',fake_stripe)
 db=Store()
 membership.checkout(db,USER,{'request_id':str(uuid.uuid4()),'promo_code':'MAYVI'},ENV)
 raw=json.dumps({'id':'evt_check','created':100,'livemode':False,'type':'checkout.session.completed',
                 'data':{'object':{'id':'cs_intro_test','subscription':'sub_intro_test'}}}).encode()
 signed='t=1000,v1='+hmac.new(b'hook_secret',b'1000.'+raw,hashlib.sha256).hexdigest()
 with pytest.raises(ValueError):membership.webhook(db,raw,'t=1000,v1=forged',ENV,now=1000)
 assert all(x[0]!='rpc/kst_redeem_intro' for x in db.calls)
 assert membership.webhook(db,raw,signed,ENV,now=1000)['received']
 assert db.calls[-1]==('rpc/kst_redeem_intro',{'p_user':USER,'p_code':'MAYVI','p_session':'cs_intro_test'})

def test_failed_session_creation_releases_only_reserved_code(monkeypatch):
 db=Store()
 def fails(method,path,env,data=None,**kw):
  if method=='POST':raise RuntimeError('Stripe unavailable')
  return fake_stripe(method,path,env,data,**kw)
 monkeypatch.setattr(membership,'stripe_call',fails)
 with pytest.raises(RuntimeError):membership.checkout(db,USER,{'request_id':str(uuid.uuid4()),'promo_code':'ENZO'},ENV)
 assert db.calls[-1][0]=='rpc/kst_release_intro'
 assert db.locked is False
