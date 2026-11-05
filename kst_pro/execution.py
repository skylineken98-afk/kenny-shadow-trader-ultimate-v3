"""Dedicated Alpaca account runner. OFF by default; no ChatGPT execution tools.
python -m kst_pro.execution status|enable|kill|run
Only deploy after sandbox/order-recovery testing with the selected broker.
"""
import argparse,hashlib,math,os,time
from decimal import Decimal,ROUND_DOWN
from datetime import datetime,timezone
import requests
from kst_options.engine import num,quote,parse,stamp,utcnow,NY
TERMINAL={'filled','canceled','expired','rejected','done_for_day','replaced'}
class Broker:
 def __init__(self,env=os.environ,http=None):
  self.env=env;self.http=http or requests.request
  self.headers={'APCA-API-KEY-ID':env.get('LIVE_ALPACA_API_KEY',''),'APCA-API-SECRET-KEY':env.get('LIVE_ALPACA_API_SECRET','')}
  self.base='https://api.alpaca.markets'
 def call(self,method,path,body=None,params=None):
  r=self.http(method,self.base+'/v2/'+path,headers=self.headers,json=body,params=params,timeout=15,allow_redirects=False)
  if r.status_code==404:return None
  if not r.ok:raise RuntimeError('Broker request failed; inspect broker order status before retrying')
  return r.json()
 def prices(self,symbol,asset_type,now):
  path='/v1beta1/options/quotes/latest' if asset_type=='option' else '/v2/stocks/quotes/latest'
  feed='opra' if asset_type=='option' else self.env.get('LIVE_STOCK_FEED','iex')
  r=self.http('GET','https://data.alpaca.markets'+path,headers=self.headers,params={'symbols':symbol,'feed':feed},timeout=15,allow_redirects=False)
  if not r.ok:return None
  return quote((r.json().get('quotes') or {}).get(symbol,{ }),now,max_age=30)

def configured(env):
 return env.get('LIVE_TRADING_ENABLED')=='true' and env.get('LIVE_DEDICATED_ACCOUNT')=='true' and env.get('LIVE_RISK_ACK')=='I understand live orders use real money' and all(env.get(k) for k in ('LIVE_ACCOUNT_ID','LIVE_ALPACA_API_KEY','LIVE_ALPACA_API_SECRET'))

def limits(env):
 values=[num(env.get(k,d)) for k,d in [('LIVE_ALLOCATION','100'),('LIVE_MAX_ORDER','60'),('LIVE_MAX_DAY_LOSS','10')]]
 if any(x is None or x<=0 for x in values) or values[1]>values[0] or values[2]>values[0]:raise ValueError('Invalid finite live risk limits')
 return values

def reconciled(store,broker,account):
 rows=store.rows('kst_execution_intents',account_id='eq.'+account,order='created_at.asc',limit=10000)
 for row in rows:
  if row['state'] in TERMINAL:continue
  order=broker.call('GET','orders:by_client_order_id',params={'client_order_id':row['client_id']})
  if order:
   update={'state':order['status'],'broker_id':order['id'],'filled_qty':num(order.get('filled_qty')) or 0,'filled_avg_price':num(order.get('filled_avg_price')),'updated_at':stamp(utcnow())}
   store.call('PATCH','kst_execution_intents',{'client_id':'eq.'+row['client_id']},update);row.update(update)
  elif row['state'] not in ('RESERVED','UNKNOWN'):
   store.call('PATCH','kst_execution_intents',{'client_id':'eq.'+row['client_id']},{'state':'UNKNOWN'});row['state']='UNKNOWN'
 # Unknown outcomes block new orders; never blindly re-submit a timed-out intent.
 return rows

def submit(store,broker,row,exposure,equity,env):
 if not configured(env):raise ValueError('Live submission is disabled')
 allocation,max_order,max_loss=limits(env);day=utcnow().astimezone(NY).date().isoformat()
 ok=store.call('POST','rpc/kst_reserve_execution',data={'p_row':row,'p_exposure':exposure,'p_equity':equity,'p_day':day,'p_allocation':allocation,'p_max_trade':max_order,'p_max_loss':max_loss})
 if not ok:return False
 store.call('PATCH','kst_execution_intents',{'client_id':'eq.'+row['client_id']},{'state':'SUBMITTING'})
 payload={'symbol':row['symbol'],'qty':str(row['quantity']),'side':row['side'],'type':'limit','limit_price':str(row['limit_price']),'time_in_force':'day','client_order_id':row['client_id']}
 if row['asset_type']=='option':payload['position_intent']='buy_to_open' if row['side']=='buy' else 'sell_to_close'
 try:
  order=broker.call('POST','orders',body=payload)
  if not order:raise RuntimeError('No broker acknowledgement')
  store.call('PATCH','kst_execution_intents',{'client_id':'eq.'+row['client_id']},{'state':order['status'],'broker_id':order['id'],'filled_qty':num(order.get('filled_qty')) or 0,'filled_avg_price':num(order.get('filled_avg_price'))})
 except Exception:
  store.call('PATCH','kst_execution_intents',{'client_id':'eq.'+row['client_id']},{'state':'UNKNOWN'})
  raise RuntimeError('Order acknowledgement uncertain. Runner will reconcile by client ID; no automatic retry.') from None
 return True

def cycle(store,broker,env=os.environ):
 if not configured(env):raise ValueError('Live execution is disabled or account configuration is incomplete')
 allocation,max_order,max_loss=limits(env);account=broker.call('GET','account')
 if not account or account['id']!=env['LIVE_ACCOUNT_ID'] or account.get('status')!='ACTIVE' or account.get('trading_blocked') or account.get('account_blocked') or account.get('trade_suspended_by_user'):raise ValueError('Broker account identity or trading eligibility check failed')
 equity=num(account.get('equity'))
 if equity is None or equity<=0:raise ValueError('Invalid broker equity')
 intents=reconciled(store,broker,account['id']);positions=broker.call('GET','positions') or [];orders=broker.call('GET','orders',params={'status':'open','limit':500}) or []
 own_ids={r['client_id'] for r in intents};net={}
 for r in intents:net[r['symbol']]=net.get(r['symbol'],0)+(1 if r['side']=='buy' else -1)*float(r.get('filled_qty') or 0)
 if any(o.get('client_order_id') not in own_ids for o in orders):raise ValueError('Unmanaged broker orders detected; use a dedicated account')
 if any(abs(float(p['qty'])-net.get(p['symbol'],0))>1e-6 or float(p['qty'])<=0 for p in positions):raise ValueError('Unmanaged or mismatched broker positions detected; reconciliation required')
 clock=broker.call('GET','clock')
 if not clock or not clock.get('is_open'):return
 exposure=sum(abs(float(p['market_value'])) for p in positions)
 if any(r['state'] in ('UNKNOWN','RESERVED','SUBMITTING') for r in intents):return
 control=store.rows('kst_execution_control',id='eq.'+account['id'],limit=1)
 if not control:raise ValueError('Initialize and review the live control record before enabling the runner')
 now=utcnow();day=now.astimezone(NY).date().isoformat()
 if control[0].get('day')!=day:
  baseline=num(account.get('last_equity'))
  if baseline is None:raise ValueError('Broker previous-close equity is unavailable')
  baseline=baseline if baseline>0 else equity
  store.call('PATCH','kst_execution_control',{'id':'eq.'+account['id']},{'day':day,'day_start_equity':baseline})
 else:baseline=float(control[0]['day_start_equity'])
 daily_exit=baseline-equity>=max_loss
 if daily_exit:
  store.call('PATCH','kst_execution_control',{'id':'eq.'+account['id']},{'killed':True});control[0]['killed']=True

 # Exits use reconciled owned quantity and fresh bid quotes. Kill blocks entries,
 # while risk-reducing exits continue. Limit exits are not guaranteed to fill.
 for p in positions:
  buys=[r for r in intents if r['symbol']==p['symbol'] and r['side']=='buy' and float(r.get('filled_qty') or 0)>0]
  if not buys or any(o['symbol']==p['symbol'] for o in orders):continue
  owner=buys[-1];plan=owner['plan'];q=broker.prices(p['symbol'],owner['asset_type'],now)
  if not q or q[0]<=0:continue
  entry=float(p['avg_entry_price']);bid=q[0];why='DAILY_LOSS_LIMIT' if daily_exit else 'STOP' if bid<=float(plan['stop']) else 'TARGET' if bid>=float(plan['target']) else None
  if not why:continue
  qty=int(float(p['qty']));price=float(Decimal(str(bid)).quantize(Decimal('.01'),rounding=ROUND_DOWN));generation=sum(1 for r in intents if r['symbol']==p['symbol'] and r['side']=='sell');ident='kst-'+hashlib.sha256((owner['client_id']+':exit:'+str(generation)).encode()).hexdigest()[:40]
  row=dict(client_id=ident,account_id=account['id'],symbol=p['symbol'],asset_type=owner['asset_type'],side='sell',quantity=qty,limit_price=price,reserved_value=0,plan={'reason':why})
  if qty>0 and price>0:submit(store,broker,row,exposure,equity,env)
 if control[0]['killed']:return
 allowed={s.strip().upper() for s in env.get('LIVE_SYMBOLS','SPY,QQQ,IWM').split(',') if s.strip()}
 kind=env.get('LIVE_ASSET','equity')
 if kind not in ('equity','option'):raise ValueError('LIVE_ASSET must be equity or option')
 if kind=='option' and int(account.get('options_trading_level') or 0)<2:raise ValueError('Broker options approval is insufficient')
 candidates=store.rows('kst_stock_plans',state='eq.OPEN',order='score.desc',limit=40) if kind=='equity' else store.rows('kst_option_signals',state='eq.OPEN',feed='eq.opra',quality_label='eq.QUALIFIED',context_label='in.(BULLISH_SETUP_ALIGNED,BEARISH_SETUP_ALIGNED)',order='score.desc',limit=100)
 for c in candidates:
  symbol=c['symbol'] if kind=='equity' else c['contract'];underlying=c['symbol'] if kind=='equity' else c['underlying']
  if underlying not in allowed or any(p['symbol']==symbol for p in positions) or any(o['symbol']==symbol for o in orders):continue
  if (now-parse(c['created_at'])).total_seconds()>300:continue
  asset=broker.call('GET','assets/'+symbol) if kind=='equity' else broker.call('GET','options/contracts/'+symbol)
  if not asset or not asset.get('tradable') or asset.get('status')!='active':continue
  if kind=='option' and (num(asset.get('size'))!=100 or asset.get('deliverables')):continue
  q=broker.prices(symbol,kind,now)
  if not q or q[0]<=0 or (q[1]-q[0])/((q[0]+q[1])/2)>(.01 if kind=='equity' else .15):continue
  multiplier=100 if kind=='option' else 1;ask=q[1];quantity=int(max_order/(ask*multiplier))
  if quantity<1:continue
  price=math.ceil(ask*100)/100;value=quantity*price*multiplier
  buying_power=num(account.get('options_buying_power') if kind=='option' else account.get('buying_power'))
  if buying_power is None or value>buying_power:continue
  ident='kst-'+hashlib.sha256((account['id']+':'+kind+':'+c['id']+':buy').encode()).hexdigest()[:40]
  stop=float(c['stop']) if kind=='equity' else price*.7;target=float(c['target']) if kind=='equity' else price*2
  if not 0<stop<price<target:continue
  row=dict(client_id=ident,account_id=account['id'],symbol=symbol,asset_type=kind,side='buy',quantity=quantity,limit_price=price,reserved_value=value,plan={'source_id':c['id'],'stop':stop,'target':target})
  if submit(store,broker,row,exposure,equity,env):break

if __name__=='__main__':
 from kst_options.store import Store
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['status','enable','kill','run']);args=parser.parse_args();store=Store();account=os.getenv('LIVE_ACCOUNT_ID','')
 if args.action=='status':print({'configured':configured(os.environ),'control':store.rows('kst_execution_control',id='eq.'+account,limit=1) if account else []})
 elif args.action in ('enable','kill'):
  if args.action=='enable' and not configured(os.environ):raise SystemExit('Complete the explicit live configuration before enabling')
  if not account:raise SystemExit('Configure the dedicated account ID')
  store.call('POST','kst_execution_control',data={'id':account,'killed':args.action=='kill'},prefer='resolution=merge-duplicates,return=minimal');print('Live entry control updated')
 else:
  broker=Broker()
  while True:
   try:
    cycle(store,broker)
    from .ops import beat
    beat(store,'execution')
   except Exception:
    try:
     from .ops import beat
     beat(store,'execution','ERROR','Execution blocked or reconciliation required. Check owner account and broker orders.')
    except Exception:pass
   time.sleep(30)
