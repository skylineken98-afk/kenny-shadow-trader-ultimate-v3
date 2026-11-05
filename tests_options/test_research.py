from datetime import datetime,timedelta,timezone
import unittest
from kst_options.engine import candidate,mark,stamp,category
from kst_options.learning import propose
from kst_options.import_fills import completed_lots,pnl
NOW=datetime(2026,11,4,15,tzinfo=timezone.utc)
def snap(bid=1,ask=1.05,t=NOW):return {'latestQuote':{'bp':bid,'ap':ask,'t':stamp(t)},'greeks':{'delta':.5}}
def test_candidate_rejects_old_crossed_missing_delta_and_high_spread():
 assert candidate('SPY261104C00600000',snap(),NOW,'opra')['category']=='0DTE'
 for s in [snap(t=NOW-timedelta(minutes=6)),snap(bid=2,ask=1),snap(bid=.5,ask=1),{**snap(),'greeks':{}}]:assert candidate('SPY261104C00600000',s,NOW,'opra') is None
 assert candidate('BAD',snap(),NOW,'opra') is None
 assert category(datetime(2027,11,4).date(),NOW)=='LEAPS'
def test_mark_ask_entry_bid_exit_fees_and_no_future_or_reused_quote():
 signal={'entry_ask':1,'quote_at':stamp(NOW-timedelta(minutes=1)),'due_at':stamp(NOW+timedelta(hours=1))}
 r=mark(signal,{'bp':1.5,'ap':1.55,'t':stamp(NOW)},NOW,1)
 assert r['estimated_pl']==49 and r['estimated_return']==.49
 assert signal['entry_ask']==1
 assert mark(signal,{'bp':1.5,'ap':1.55,'t':stamp(NOW+timedelta(seconds=1))},NOW) is None
 assert mark({**signal,'last_quote_at':stamp(NOW)},{'bp':1.5,'ap':1.55,'t':stamp(NOW)},NOW) is None
 late=NOW+timedelta(hours=2)
 r=mark(signal,{'bp':2,'ap':2.1,'t':stamp(late)},late)
 assert r['state']=='UNRESOLVED' and r['outcome_return'] is None
 r=mark(signal,{'bp':2,'ap':2.1,'t':stamp(NOW+timedelta(hours=1))},NOW+timedelta(hours=1))
 assert r['state']=='CLOSED' and r['target_seen']
def test_partial_exits_and_fees_all_count():
 rows=[{'fill_id':'a','filled_at':stamp(NOW),'contract':'X','side':'BUY','quantity':2,'price':1,'fees':2},
 {'fill_id':'b','filled_at':stamp(NOW+timedelta(minutes=1)),'contract':'X','side':'SELL','quantity':1,'price':2,'fees':1},
 {'fill_id':'c','filled_at':stamp(NOW+timedelta(minutes=2)),'contract':'X','side':'SELL','quantity':1,'price':.5,'fees':1}]
 assert completed_lots(rows[:2])==[]
 assert completed_lots(rows)[0]['realized_pl']==46
 assert pnl(rows)==46
 with unittest.TestCase().assertRaises(ValueError):completed_lots(rows[1:])
def sample(i,feed='opra'):
 t=NOW+timedelta(days=i)
 return {'contract':f'X{i}','created_at':stamp(t),'closed_at':stamp(t+timedelta(hours=1)),'state':'CLOSED','feed':feed,'features':[.5,.5,.5],'outcome_return':-.2}
def test_learning_excludes_indicative_requires_samples_and_never_promotes_ties():
 assert propose([sample(i,'indicative') for i in range(200)]) is None
 assert propose([sample(i) for i in range(99)]) is None
 result=propose([sample(i) for i in range(120)])
 assert result['state']=='REJECTED' and result['report']['holdout_count']==24
 assert propose([{**sample(i),'closed_at':stamp(NOW+timedelta(days=1000))} for i in range(120)]) is None
 assert propose([sample(1) for i in range(200)]) is None

def test_learning_promotes_only_when_later_outcomes_improve():
 rows=[]
 for i in range(150):
  r=sample(i);winner=i%2==0;r['features']=[0,1,0] if winner else [1,0,0];r['outcome_return']=.3 if winner else -.3;rows.append(r)
 proposal=propose(rows)
 assert proposal['state']=='PROMOTED'
 assert proposal['report']['challenger_holdout_return']>proposal['report']['champion_holdout_return']+.02
 assert abs(sum(proposal['weights'])-1)<1e-9
 # A later reversal must reject the same challenger, with no holdout retuning.
 for r in rows[120:]:r['outcome_return']=-r['outcome_return']
 assert propose(rows)['state']=='REJECTED'

def test_session_giveback_is_across_closed_trades():
 from kst_options.sessions import review
 rows=[]
 for i,(side,price) in enumerate([('BUY',1),('SELL',6),('BUY',6),('SELL',1)]):
  rows.append({'fill_id':str(i),'filled_at':stamp(NOW+timedelta(minutes=i)),'contract':'SPX','side':side,'quantity':1,'price':price,'fees':0})
 report=review(rows)[0]
 assert report['realized_peak']==500 and report['realized_pl']==0
 assert report['giveback_dollars']==500 and report['giveback_fraction']==1
 assert report['rapid_reentries']==1 and report['buy_fill_count']==2

def test_requested_top3_labels_fallbacks_and_never_invents_missing_data():
 from kst_options.engine import requested_choices,context_label
 strict=candidate('SPY261104C00600000',snap(),NOW,'opra')
 fallback=candidate('SPY261104P00600000',snap(bid=.85,ask=1.05),NOW,'opra',relaxed=True)
 assert strict and fallback and fallback['quality_label']=='WATCHLIST'
 assert len(requested_choices([strict,fallback],'0DTE',1000))==2
 assert requested_choices([strict],'0DTE',30)==[]
 assert requested_choices([strict,fallback],'0DTE',1000)[0]['quality_label']=='QUALIFIED'
 setup={'status':'SETUP','side':'BULLISH','created_at':stamp(NOW)}
 assert context_label(strict,setup,NOW)=='BULLISH_SETUP_ALIGNED'
 assert context_label(fallback,setup,NOW)=='COUNTER_TREND_RESEARCH'
def test_news_dedup_fields_dates_and_untrusted_links():
 from kst_options.news import parse_feed
 xml=b'<rss><channel><item><title>Fed inflation update</title><link>https://www.cnbc.com/test</link><pubDate>Wed, 04 Nov 2026 14:00:00 GMT</pubDate></item><item><title>Bad</title><link>javascript:alert(1)</link><pubDate>Wed, 04 Nov 2026 14:00:00 GMT</pubDate></item></channel></rss>'
 rows=parse_feed(xml,NOW)
 assert len(rows)==1 and rows[0]['sectors']==['Financials'] and 'summary' not in rows[0]
 assert parse_feed(xml,NOW+timedelta(days=4))==[]

def test_spy_proxy_uses_matched_reference_and_rejects_stale_or_future_data():
 from kst_options.proxy import estimate
 now=datetime(2026,11,4,22,tzinfo=timezone.utc)
 a={'at':'2026-11-04T21:00:00+00:00','spy':600,'spx':6000}
 t={'t':stamp(now),'p':603}
 p=estimate(a,t,now,'sip')
 assert p['status']=='ESTIMATE' and p['estimated_spx']==6030 and p['estimated_point_change']==30
 assert estimate(a,{**t,'t':stamp(now-timedelta(minutes=10))},now,'sip')['estimated_spx'] is None
 assert estimate(a,{**t,'t':stamp(now+timedelta(seconds=1))},now,'sip')['estimated_spx'] is None
 assert estimate(a,{**t,'p':0},now,'sip')['estimated_spx'] is None

def test_paper_outcomes_can_train_but_stay_distinct_from_indicative_quotes():
 rows=[sample(i,'paper_opra') for i in range(120)]
 result=propose(rows)
 assert result and result['sample_count']==120
 assert propose([{**r,'feed':'indicative'} for r in rows]) is None

def test_memory_labels_mixed_timeframes_without_inventing_chop():
 from kst_options.progress import regime
 frames={k:{'trend':'BULLISH'} for k in ('4h','1h','5m')}
 assert regime({'details':{'frames':frames}})=='ALIGNED_UPTREND'
 frames['5m']['trend']='BEARISH'
 assert regime({'details':{'frames':frames}})=='MIXED_TIMEFRAMES'
 assert regime({})=='INSUFFICIENT_CONTEXT'

def test_push_endpoint_restrictions_and_paper_labels():
 from kst_options.push_worker import allowed_endpoint,notification
 assert allowed_endpoint('https://fcm.googleapis.com/fcm/send/test')
 assert allowed_endpoint('https://web.push.apple.com/test')
 for endpoint in ['http://fcm.googleapis.com/test','https://localhost/test','https://fcm.googleapis.com.evil.test/test','https://user@fcm.googleapis.com/test','https://fcm.googleapis.com:999/test']:
  assert not allowed_endpoint(endpoint)
 p=notification({'id':'1','created_at':stamp(NOW),'agent':'balanced','action':'EXIT','contract':'SPY261104C00600000','quantity':1,'price':1.5,'realized_pl':49})
 assert 'PAPER' in p['title'] and '49.00' in p['body'] and p['url']=='/#progress'

def test_push_dispatch_honors_current_preferences_and_idempotent_jobs():
 from kst_options.push_worker import cycle
 class DB:
  def __init__(self):self.updates=[];self.events=['EXIT']
  def call(self,*a,**kw):return [{'id':'job','subscription_id':'sub','event_id':'event','attempts':1}]
  def rows(self,table,**kw):
   if table=='kst_push_subscriptions':return [{'id':'sub','active':True,'event_types':self.events,'endpoint':'https://fcm.googleapis.com/test','keys':{}}]
   return [{'id':'event','created_at':stamp(NOW),'agent':'balanced','action':'EXIT','contract':'SPY','quantity':1,'price':1.5,'realized_pl':49}]
  def patch(self,table,id,data):self.updates.append((table,id,data))
 db=DB();sent=[];cycle(db,lambda sub,payload:sent.append(payload));assert len(sent)==1 and db.updates[-1][2]['state']=='SENT'
 db=DB();db.events=['ENTRY'];sent=[];cycle(db,lambda sub,payload:sent.append(payload));assert not sent and db.updates[-1][2]['state']=='SKIPPED'

if __name__=="__main__":
 for name,func in list(globals().items()):
  if name.startswith("test_"):func();print("PASS",name)
