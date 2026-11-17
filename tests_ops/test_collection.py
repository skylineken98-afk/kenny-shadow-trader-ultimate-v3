import sys,types,unittest,math
from unittest.mock import Mock,patch
from datetime import datetime,timezone,timedelta
try:import requests
except ImportError:
 requests=types.ModuleType('requests');requests.Timeout=type('Timeout',(Exception,),{});requests.ConnectionError=type('ConnectionError',(Exception,),{});requests.Session=Mock;requests.get=Mock();sys.modules['requests']=requests
from kst_options.store import Store,DatabaseError
from kst_pro.collection import during_session,loop
from kst_pro.history import trendlines
from kst_pro.ops import monitor
class Checks(unittest.TestCase):
 def store(self):
  with patch.dict('os.environ',{'SUPABASE_URL':'https://example.invalid','SUPABASE_SERVICE_ROLE_KEY':'test'}):s=Store()
  s._local.session=Mock();return s
 def response(self,status,body):return types.SimpleNamespace(ok=status<400,status_code=status,json=lambda:body,content=b'{}')
 def test_retry_read(self):
  s=self.store();s._local.session.request.side_effect=[self.response(503,{}),self.response(200,[])]
  with patch('kst_options.store.time.sleep'):self.assertEqual(s.rows('x'),[])
  self.assertEqual(s._local.session.request.call_count,2)
 def test_never_repeat_rpc(self):
  s=self.store();s._local.session.request.side_effect=requests.Timeout()
  with self.assertRaises(RuntimeError):s.call('POST','rpc/kst_agent_open',data={})
  self.assertEqual(s._local.session.request.call_count,1)
 def test_error_excludes_secrets(self):
  s=self.store();s._local.session.request.return_value=self.response(401,{'code':'42501','message':'secret'})
  with self.assertRaises(DatabaseError) as e:s.rows('x')
  self.assertNotIn('secret',str(e.exception))
 def test_closed_session(self):
  fn=Mock()
  with patch('kst_pro.collection.market_open',return_value=False):r=during_session(fn)(Mock())
  self.assertEqual(r['status'],'MARKET_CLOSED');fn.assert_not_called()
 def test_monitor_stale_and_degraded(self):
  now=datetime.now(timezone.utc)
  for status,age in [('OK',3600),('DEGRADED',0)]:
   s=Mock();s.rows.side_effect=lambda table,**kw:[{'id':'news','status':status,'last_finished_at':(now-timedelta(seconds=age)).isoformat(),'interval_seconds':300}] if table=='kst_collection_status' else []
   monitor(s,now,env={'MONITOR_SERVICES':''});self.assertTrue(s.insert.called)
 def test_failure_preserves_success(self):
  stop=Mock();stop.is_set.side_effect=[False,True];s=Mock()
  with patch('kst_pro.collection.Store',return_value=s):loop('test',60,Mock(side_effect=ValueError('secret')),stop)
  writes=[c.kwargs['data'] for c in s.call.call_args_list if c.args[1]=='kst_collection_status']
  self.assertTrue(any(r['status']=='CONFIG' for r in writes));self.assertFalse(any('last_success_at' in r for r in writes))
 def test_confirmed_anchors_and_pending_outcomes(self):
  now=datetime(2026,11,8,tzinfo=timezone.utc);bars=[]
  for i in range(100):
   low=100+i*.8+4*math.cos(i*math.pi/5)
   bars.append({'bar_at':(now-timedelta(days=100-i)).isoformat(),'low':low,'high':low+2,'close':low+1,'volume':100})
  lines,events=trendlines(bars,'SPY','1d',now);self.assertTrue(lines)
  for line in lines:self.assertGreater(line['identified_bar_at'],line['anchor_b_at'])
  self.assertTrue(all(e['bar_at']>next(l['identified_bar_at'] for l in lines if l['id']==e['line_id']) for e in events))
  self.assertTrue(any(e['details']['forward_returns_pct']['20'] is None for e in events))
if __name__=='__main__':unittest.main()
