from datetime import datetime,timedelta,timezone
from kst_options.engine import stamp,candidate
from kst_options.candles import review_candles
from kst_options.stocks import stock_candidate
NOW=datetime(2026,11,4,15,tzinfo=timezone.utc)

def test_candle_followthrough_excludes_forming_and_future_bars():
 rows=[dict(time=stamp(NOW-timedelta(minutes=15)),open=10,high=11,low=8,close=9),dict(time=stamp(NOW-timedelta(minutes=10)),open=8.5,high=12,low=8,close=11.5)]
 result=review_candles(rows,NOW,5);bull=[p for p in result['patterns'] if p['pattern']=='BULLISH_ENGULFING'][0]
 assert bull['directional_follow_through']=='PENDING'
 rows.append(dict(time=stamp(NOW-timedelta(minutes=5)),open=11.5,high=13,low=11,close=12.5))
 rows.append(dict(time=stamp(NOW),open=12,high=20,low=1,close=2))
 result=review_candles(rows,NOW,5);bull=[p for p in result['patterns'] if p['pattern']=='BULLISH_ENGULFING'][0]
 assert result['completed_bars']==3 and bull['directional_follow_through']=='CONFIRMED'
 rows[-2]['close']=7;rows[-2]['low']=6
 bull=[p for p in review_candles(rows,NOW,5)['patterns'] if p['pattern']=='BULLISH_ENGULFING'][0]
 assert bull['directional_follow_through']=='INVALIDATED'

def snap():
 return dict(latestQuote=dict(bp=102,ap=102.1,t=stamp(NOW),**{'as':10}),dailyBar=dict(t='2026-11-04T05:00:00Z',v=600,h=103,l=100),prevDailyBar=dict(t='2026-11-03T05:00:00Z',v=1000,c=100))

def test_stock_plan_uses_fresh_bid_ask_and_explicit_risk():
 s=snap();p=stock_candidate('AAPL',s,NOW,'iex')
 assert p and p['stop']<p['entry_ask']<p['target'] and p['last_bid']==102
 assert 'not time-adjusted' in p['reason']
 s['latestQuote']['t']=stamp(NOW-timedelta(minutes=2));assert stock_candidate('AAPL',s,NOW,'iex') is None
 s=snap();s['latestQuote']['ap']=120;assert stock_candidate('AAPL',s,NOW,'iex') is None
 s=snap();s['dailyBar']['t']='2026-11-03T05:00:00Z';assert stock_candidate('AAPL',s,NOW,'iex') is None

def test_greeks_preserve_missing_values_and_timestamp_limits():
 s={'latestQuote':{'bp':1,'ap':1.05,'t':stamp(NOW)},'greeks':{'delta':.5,'gamma':.02,'vega':float('nan')},'impliedVolatility':.3}
 c=candidate('SPY261104C00600000',s,NOW,'opra');risk=c['risk_snapshot']
 assert risk['greeks']['gamma']==.02 and risk['greeks']['vega'] is None and risk['greeks']['rho'] is None
 assert 'not independently verified' in risk['source']

def test_stock_push_uses_separate_events_and_honors_opt_out():
 from kst_options.push_worker import cycle
 class Store:
  def __init__(self,enabled):self.enabled=enabled;self.patches=[]
  def call(self,method,table,**kw):
   assert table=='rpc/kst_claim_stock_push'
   return [dict(id='job',subscription_id='sub',event_id='event',attempts=1)]
  def rows(self,table,**kw):
   if table=='kst_push_subscriptions':return [dict(id='sub',endpoint='https://fcm.googleapis.com/push/test',keys={},event_types=['STOCK_EXIT'] if self.enabled else [])]
   assert table=='kst_stock_alerts'
   return [dict(id='event',symbol='AAPL',reason='TARGET_REACHED',price=105,created_at=stamp(NOW))]
  def patch(self,table,ident,data):self.patches.append((table,data))
 sent=[];db=Store(True);cycle(db,lambda sub,payload:sent.append(payload),stock=True)
 assert sent[0]['url']=='/#stocks' and 'no sale executed' in sent[0]['body']
 assert db.patches[-1]==('kst_stock_push_deliveries',{'state':'SENT','sent_at':db.patches[-1][1]['sent_at']})
 sent.clear();db=Store(False);cycle(db,lambda *args:sent.append(args),stock=True)
 assert not sent and db.patches[-1][1]['state']=='SKIPPED'

def test_requested_contract_tracking_keeps_its_own_entry_on_retry():
 from kst_options.worker import publish_request_choice
 class Store:
  def __init__(self):self.saved=None
  def insert(self,table,row,**kw):
   if self.saved is None:self.saved=dict(row)
  def rows(self,table,**kw):return [self.saved]
 db=Store();req=dict(id='0DTE-100-29900000',budget=100,created_at=stamp(NOW))
 c=dict(contract='SPY261104C00600000',category='0DTE',expiration='2026-11-04',entry_ask=.50,quote_at=stamp(NOW))
 first=publish_request_choice(db,c,req,NOW,1,'baseline')
 second=publish_request_choice(db,{**c,'entry_ask':.75},req,NOW+timedelta(minutes=1),2,'changed')
 assert first['signal_id']==second['signal_id'] and second['entry_ask']==.50 and second['fee_estimate']==1
