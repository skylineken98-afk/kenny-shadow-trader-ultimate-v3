import hashlib,hmac,json,io,base64,time,uuid
from datetime import datetime,timedelta,timezone
import pytest
from kst_pro.membership import entitlement,webhook,grant,checkout
from kst_pro.market import normalize_earnings,historical_reactions
from kst_pro.research import entry_features,replay,evaluate
from kst_pro.routes import handle
from kst_pro.execution import configured,limits,submit
from kst_chat.streaming import consume
LIVE={'LIVE_TRADING_ENABLED':'true','LIVE_DEDICATED_ACCOUNT':'true','LIVE_RISK_ACK':'I understand live orders use real money','LIVE_ACCOUNT_ID':'owner','LIVE_ALPACA_API_KEY':'test-only','LIVE_ALPACA_API_SECRET':'test-only'}
NOW=datetime(2026,11,5,15,tzinfo=timezone.utc);A=str(uuid.uuid4());B=str(uuid.uuid4())
class Store:
 def __init__(self):self.data={};self.calls=[]
 def rows(self,table,**params):
  rows=list(self.data.get(table,[]))
  for k,v in params.items():
   if isinstance(v,str) and v.startswith('eq.'):rows=[r for r in rows if str(r.get(k))==v[3:]]
  return rows[:params.get('limit',1000)]
 def call(self,method,table,params=None,data=None,**kw):self.calls.append((method,table,params,data));return True
 def insert(self,table,row,**kw):self.data.setdefault(table,[]).append(row)

def test_passes_expire_and_do_not_depend_on_paid_subscription():
 assert entitlement({'pass_lifetime':True},NOW)
 assert entitlement({'pass_until':(NOW+timedelta(days=1)).isoformat()},NOW)
 assert not entitlement({'paid_until':(NOW-timedelta(seconds=1)).isoformat()},NOW)
 db=Store()
 with pytest.raises(PermissionError):grant(db,A,{'user_id':B,'action':'lifetime'},{})
 grant(db,A,{'user_id':B,'action':'month'},{'KST_ADMIN_USER_IDS':A})
 assert db.calls[-1][1]=='rpc/kst_admin_grant_pass' and db.calls[-1][3]['p_actor']==A and db.calls[-1][3]['p_subject']==B

def sign(payload,secret,t):
 raw=json.dumps(payload).encode();return raw,'t='+str(t)+',v1='+hmac.new(secret.encode(),str(t).encode()+b'.'+raw,hashlib.sha256).hexdigest()

def test_webhook_rejects_forged_expired_or_wrong_mode_events():
 db=Store();env={'STRIPE_WEBHOOK_SECRET':'test-secret'};event={'id':'evt_test','livemode':False,'type':'ignored'};raw,sig=sign(event,'test-secret',1000)
 assert webhook(db,raw,sig,env,now=1000)['ignored']
 for badraw,badsig,now in [(raw+'x'.encode(),sig,1000),(raw,sig,1500),(raw,'t=1000,v1=bad',1000)]:
  with pytest.raises(ValueError):webhook(db,badraw,badsig,env,now=now)
 with pytest.raises(ValueError):webhook(db,raw,sig,{**env,'BILLING_LIVE_MODE':'true'},now=1000)

def test_subscription_webhook_uses_current_provider_state_and_preserves_gifts(monkeypatch):
 db=Store();env={'STRIPE_WEBHOOK_SECRET':'secret','STRIPE_MONTHLY_PRICE_ID':'price_month'}
 event={'id':'evt_1','created':100,'livemode':False,'type':'customer.subscription.updated','data':{'object':{'id':'sub_test','metadata':{'kst_user':A}}}}
 raw,sig=sign(event,'secret',1000)
 monkeypatch.setattr('kst_pro.membership.stripe_call',lambda *a,**kw:dict(metadata={'kst_user':A},customer='cus_test',status='active',items={'data':[{'price':{'id':'price_month'},'current_period_end':2000}]}))
 assert webhook(db,raw,sig,env,now=1000)['received']
 payload=db.calls[-1][3];assert payload['p_user']==A and payload['p_until'] and payload['p_lifetime'] is False

def test_checkout_uses_server_price_and_identity_not_browser_values(monkeypatch):
 db=Store();seen=[]
 def stripe(*args,**kw):
  if args[0]=='GET':return {'active':True,'recurring':{'interval':'month','interval_count':1}}
  seen.append(kw);return {'id':'cs_test','url':'https://checkout.stripe.com/test'}
 monkeypatch.setattr('kst_pro.membership.stripe_call',stripe)
 env={'STRIPE_MONTHLY_PRICE_ID':'price_real','KST_SITE_URL':'https://kst.example','STRIPE_SECRET_KEY':'test','STRIPE_WEBHOOK_SECRET':'test-signed'}
 checkout(db,A,{'request_id':str(uuid.uuid4()),'user_id':B,'price':'price_forged'},env)
 assert seen[0]['data']['client_reference_id']==A and seen[0]['data']['line_items[0][price]']=='price_real'
 assert db.data['kst_billing_sessions'][0]['user_id']==A

def test_private_positions_and_alerts_always_use_verified_identity():
 db=Store();db.data['kst_personal_positions']=[{'id':str(uuid.uuid4()),'user_id':B}]
 assert handle('GET','/api/chat/positions',{},A,db,{})==[]
 handle('POST','/api/chat/positions',{'symbol':'AAPL','quantity':2,'entry':100,'stop':95,'target':110,'user_id':B},A,db,{})
 assert db.calls[-1][3]['p_row']['user_id']==A
 handle('DELETE','/api/chat/positions/'+str(uuid.uuid4()),{},A,db,{})
 assert db.calls[-1][2]['user_id']=='eq.'+A
 with pytest.raises(ValueError):handle('POST','/api/chat/positions',{'symbol':'AAPL','quantity':float('nan'),'entry':100,'stop':95,'target':110},A,db,{})
 with pytest.raises(PermissionError):handle('GET','/api/chat/admin/system',{},A,db,{})

def test_earnings_timing_and_missing_data_are_honest():
 rows=normalize_earnings({'earningsCalendar':[{'symbol':'AAPL','date':'2026-11-06','hour':'amc'},{'symbol':'MSFT','date':'2026-11-07','hour':'unknown'},{'symbol':'BAD','date':'bad'}]},NOW)
 assert rows[0]['timing']=='AFTER_CLOSE' and rows[1]['timing']=='UNCONFIRMED'
 assert rows[0]['details']['expected_move'] is None
 bars=[{'date':'2026-11-04','close':100},{'date':'2026-11-05','close':110},{'date':'2026-11-06','close':99}]
 result=historical_reactions([{'date':'2026-11-05','hour':'bmo'},{'date':'2026-11-05','hour':'amc'}],bars)
 assert result[0]['close_to_close_pct']==10 and result[1]['close_to_close_pct']==-10

def test_research_features_exclude_later_fetched_news_and_later_greeks():
 signal={'created_at':NOW.isoformat(),'entry_ask':1,'entry_bid':.95,'risk_snapshot':{'observed_at':(NOW+timedelta(seconds=1)).isoformat(),'greeks':{'delta':.5}}}
 news=[{'published_at':(NOW-timedelta(hours=1)).isoformat(),'fetched_at':(NOW+timedelta(seconds=1)).isoformat()}]
 values=entry_features(signal,news,{})
 assert len(values)==10 and values[1] is None and values[-1]==0
 assert evaluate([])['state']=='COLLECTING'

def test_replay_uses_ordered_quotes_slippage_and_no_invented_close():
 signal={'entry_ask':1,'quote_at':NOW.isoformat(),'due_at':(NOW+timedelta(hours=1)).isoformat(),'fee_estimate':1}
 assert replay(signal,[]) is None
 marks=[{'quote_at':(NOW+timedelta(minutes=1)).isoformat(),'bid':1.6},{'quote_at':(NOW+timedelta(minutes=2)).isoformat(),'bid':1.2}]
 result=replay(signal,marks)
 assert result['reason']=='TRAILING_GIVEBACK' and result['return']<.2

def test_stream_requires_terminal_response_and_emits_actual_deltas():
 sent=[];lines=[b'data: {"type":"response.output_text.delta","delta":"Hello"}\n',b'data: {"type":"response.completed","response":{"status":"completed"}}\n']
 assert consume(lines,sent.append)['status']=='completed' and sent==[{'type':'delta','text':'Hello'}]
 with pytest.raises(RuntimeError):consume(lines[:1],lambda e:None)

def test_live_defaults_are_off_and_ambiguous_submission_is_never_retried():
 assert not configured({})
 with pytest.raises(ValueError):limits({'LIVE_ALLOCATION':'nan'})
 class Broker:
  def call(self,*a,**kw):raise TimeoutError()
 db=Store();row={'client_id':'stable','symbol':'AAPL','quantity':1,'side':'buy','limit_price':10,'asset_type':'equity'}
 with pytest.raises(RuntimeError):submit(db,Broker(),row,0,100,{**LIVE,'LIVE_ALLOCATION':'100','LIVE_MAX_ORDER':'60','LIVE_MAX_DAY_LOSS':'10'})
 assert db.calls[-1][3]['state']=='UNKNOWN' and db.calls[-2][3]['state']=='SUBMITTING'

def test_rich_model_uses_chronological_contract_days_and_never_auto_activates():
 rows=[]
 for day in range(10):
  for i in range(20):
   at=NOW+timedelta(days=day,minutes=i);rows.append(dict(id=str(uuid.uuid4()),contract='C'+str(i),created_at=at.isoformat(),closed_at=(at+timedelta(hours=1)).isoformat(),state='CLOSED',feed='opra',entry_ask=1,quote_at=at.isoformat(),due_at=(at+timedelta(hours=1)).isoformat(),outcome_return=.5 if i>=10 else -.5,score=20-i,rich_features=[float(i)]+[None]*9,marks=[]))
 report=evaluate(rows)
 assert report['independent_contract_days']==200 and report['partition_counts']==[120,40,40]
 assert report['state']=='RESEARCH_PASS' and report['exit_pass'] is False
 assert 'No production promotion' in report['limitations']

def test_reconcile_unknown_order_by_stable_id_without_another_post():
 from kst_pro.execution import reconciled
 db=Store();db.data['kst_execution_intents']=[{'client_id':'stable','state':'UNKNOWN','account_id':'owner','symbol':'AAPL'}];calls=[]
 class Broker:
  def call(self,method,path,**kw):calls.append((method,path,kw));return {'id':'broker','status':'filled','filled_qty':'1','filled_avg_price':'10'}
 rows=reconciled(db,Broker(),'owner')
 assert rows[0]['state']=='filled' and rows[0]['filled_qty']==1
 assert all(call[0]=='GET' for call in calls)

def test_duplicate_reservation_prevents_network_submission():
 class RejectStore(Store):
  def call(self,*a,**kw):return False
 class NoNetwork:
  def call(self,*a,**kw):raise AssertionError('Must not submit')
 assert submit(RejectStore(),NoNetwork(),{'client_id':'duplicate'},0,100,LIVE) is False

def test_backup_authentication_rejects_tampering(tmp_path):
 from kst_pro.backup import decrypt,MAGIC
 from cryptography.hazmat.primitives.ciphers.aead import AESGCM
 key=b'x'*32;nonce=b'n'*12;plain=b'private database';path=tmp_path/'test.kstenc';env={'BACKUP_ENCRYPTION_KEY':base64.b64encode(key).decode()}
 path.write_bytes(MAGIC+nonce+AESGCM(key).encrypt(nonce,plain,MAGIC))
 assert decrypt(path,env)==plain
 data=path.read_bytes();path.write_bytes(data[:-1]+bytes([data[-1]^1]))
 with pytest.raises(Exception):decrypt(path,env)

def test_private_push_cannot_follow_a_browser_link_to_another_account():
 from kst_pro.private_push import cycle
 class PrivateStore(Store):
  def call(self,*a,**kw):
   if a[1]=='rpc/kst_claim_private_push':return [{'id':'job','subscription_id':'s','event_id':'e','attempts':1}]
   return super().call(*a,**kw)
  def patch(self,table,ident,data):self.calls.append(('PATCH',table,ident,data))
 db=PrivateStore();db.data['kst_push_subscriptions']=[dict(id='s',active='true',user_id=B,event_types=['PERSONAL_EXIT'],endpoint='https://fcm.googleapis.com/test')]
 db.data['kst_private_alerts']=[dict(id='e',user_id=A,kind='PERSONAL_EXIT')]
 sent=[];cycle(db,lambda *a:sent.append(a));assert not sent and db.calls[-1][3]['state']=='SKIPPED'
