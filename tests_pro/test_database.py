"""Run only against an explicitly disposable test database (see CI workflow)."""
import os,uuid
from pathlib import Path
import pytest
DSN=os.getenv('KST_TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not DSN,reason='Disposable PostgreSQL test database not configured')

@pytest.fixture(scope='module')
def db():
 psycopg=pytest.importorskip('psycopg')
 with psycopg.connect(DSN,autocommit=True) as conn:
  conn.execute("do $$begin create role anon;exception when duplicate_object then null;end$$")
  conn.execute("do $$begin create role authenticated;exception when duplicate_object then null;end$$")
  conn.execute("do $$begin create role service_role;exception when duplicate_object then null;end$$")
  conn.execute('create schema if not exists auth')
  conn.execute('create table if not exists auth.users(id uuid primary key)')
  conn.execute("create or replace function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$")
  root=Path(__file__).resolve().parents[1]
  for name in ['kst_options/schema.sql','kst_options/stocks.sql','kst_chat/schema.sql','kst_pro/schema.sql','kst_pro/execution.sql']:
   conn.execute((root/name).read_text())
  yield conn

def test_private_alert_is_transactional_and_only_queued_for_its_owner(db):
 from psycopg.types.json import Jsonb
 a,b=uuid.uuid4(),uuid.uuid4();position=uuid.uuid4()
 for user in (a,b):db.execute('insert into auth.users(id) values(%s)',(user,))
 for name,user in [('a',a),('b',b)]:
  db.execute("insert into kst_push_subscriptions(id,endpoint,keys,token_hash,event_types,user_id) values(%s,%s,'{}',%s,'[\"PERSONAL_EXIT\"]',%s)",('test-'+name+str(a),'https://fcm.googleapis.com/'+name+str(a),'hash-'+name+str(a),user))
 row=dict(id=str(position),user_id=str(a),symbol='AAPL',quantity=2,entry=100,stop=95,target=110,trailing_pct=None)
 assert db.execute('select kst_save_personal_position(%s)',(Jsonb(row),)).fetchone()[0]
 db.execute("update kst_personal_positions set created_at=now()-interval '2 minutes' where id=%s",(position,))
 db.execute("select kst_mark_personal(%s,111,now()-interval '1 second')",(position,))
 assert db.execute('select count(*) from kst_private_alerts where position_id=%s',(position,)).fetchone()[0]==1
 owners=db.execute('select s.user_id from kst_private_push_deliveries d join kst_push_subscriptions s on s.id=d.subscription_id join kst_private_alerts e on e.id=d.event_id where e.position_id=%s',(position,)).fetchall()
 assert owners==[(a,)]
 db.execute('select kst_mark_personal(%s,112,now())',(position,))
 assert db.execute('select count(*) from kst_private_alerts where position_id=%s',(position,)).fetchone()[0]==1

def test_billing_event_order_cannot_revoke_gift_or_apply_old_subscription_state(db):
 user=uuid.uuid4();db.execute('insert into auth.users(id) values(%s)',(user,));db.execute('insert into kst_memberships(user_id,pass_lifetime) values(%s,true)',(user,))
 db.execute("select kst_apply_billing(%s,%s,200,now()+interval '30 days',false,'cus_test','sub_test')",('new-'+str(user),user))
 db.execute("select kst_apply_billing(%s,%s,100,null,false,'cus_test','sub_test')",('old-'+str(user),user))
 paid,gift=db.execute('select paid_until is not null,pass_lifetime from kst_memberships where user_id=%s',(user,)).fetchone();assert paid and gift

def test_personal_scan_ownership_survives_page_close_and_is_not_browser_writable(db):
 a,b=uuid.uuid4(),uuid.uuid4()
 for user in (a,b):db.execute('insert into auth.users(id) values(%s)',(user,))
 req='0DTE-100-'+str(int(uuid.uuid4().int%10**10))
 for user in (a,b):assert db.execute('select kst_queue_personal_request(%s,%s,%s,%s,100)',(user,uuid.uuid4(),req,'0DTE')).fetchone()[0]
 assert db.execute('select count(*) from kst_personal_suggestions where request_id=%s',(req,)).fetchone()[0]==2
 assert not db.execute("select has_table_privilege('authenticated','kst_personal_suggestions','INSERT')").fetchone()[0]
 assert not db.execute("select has_function_privilege('authenticated','kst_reserve_execution(jsonb,numeric,numeric,text,numeric,numeric,numeric)','EXECUTE')").fetchone()[0]

def test_live_reservation_enforces_budget_and_duplicate_order_identity(db):
 from psycopg.types.json import Jsonb
 account='test-'+str(uuid.uuid4());db.execute('insert into kst_execution_control(id,killed) values(%s,false)',(account,))
 row=dict(client_id='one-'+account,account_id=account,symbol='AAPL',asset_type='equity',side='buy',quantity=1,limit_price=60,reserved_value=60,plan={})
 def reserve(r):return db.execute("select kst_reserve_execution(%s,0,100,'2026-11-05',100,60,10)",(Jsonb(r),)).fetchone()[0]
 assert reserve(row)
 assert not reserve(row)
 assert not reserve({**row,'client_id':'two-'+account})

def test_two_workers_cannot_both_reserve_the_remaining_allocation(db):
 from concurrent.futures import ThreadPoolExecutor
 import threading,psycopg
 from psycopg.types.json import Jsonb
 account='concurrent-'+str(uuid.uuid4());db.execute('insert into kst_execution_control(id,killed) values(%s,false)',(account,));barrier=threading.Barrier(2)
 def reserve(index):
  row=dict(client_id=account+str(index),account_id=account,symbol='AAPL',asset_type='equity',side='buy',quantity=1,limit_price=60,reserved_value=60,plan={})
  with psycopg.connect(DSN,autocommit=True) as conn:
   barrier.wait(timeout=5)
   return conn.execute("select kst_reserve_execution(%s,0,100,'2026-11-05',100,60,10)",(Jsonb(row),)).fetchone()[0]
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,[0,1]))
 assert sorted(results)==[False,True]
