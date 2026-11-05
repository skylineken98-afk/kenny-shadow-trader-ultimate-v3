"""Authenticated extension routes. Identity always comes from verified Auth."""
import hashlib,re,uuid,time
from datetime import datetime,timezone
from . import membership
from .market import ticker,finnhub
from kst_options.engine import num

PREFIXES=('/api/chat/positions','/api/chat/private-alerts','/api/chat/push-link','/api/chat/account','/api/chat/checkout','/api/chat/billing-portal','/api/chat/admin/','/api/chat/market-refresh','/api/chat/ticker-search','/api/chat/history-search')

def handle(method,path,body,user,store,env):
 if path=='/api/chat/account' and method=='GET':return membership.status(store,user,env)
 if path=='/api/chat/checkout' and method=='POST':return membership.checkout(store,user,body,env)
 if path=='/api/chat/billing-portal' and method=='POST':return membership.portal(store,user,env)
 if path.startswith('/api/chat/admin/'):
  if not membership.is_admin(user,env):raise PermissionError('Administrator access required')
  if path=='/api/chat/admin/pass' and method=='POST':return membership.grant(store,user,body,env)
  if path=='/api/chat/admin/system' and method=='GET':
   return {'jobs':store.rows('kst_options_health',order='id.asc',limit=40),'heartbeats':store.rows('kst_service_heartbeats',order='id.asc',limit=30),'incidents':store.rows('kst_system_incidents',order='opened_at.desc',limit=30),'research':store.rows('kst_research_reports',order='created_at.desc',limit=3),'execution':store.rows('kst_execution_intents',select='client_id,symbol,asset_type,side,quantity,state,created_at',order='created_at.desc',limit=20)}
 if path=='/api/chat/ticker-search' and method=='POST':
  q=str(body.get('query') or '').strip()
  if not 1<=len(q)<=64:raise ValueError('Search must contain 1–64 characters')
  result=finnhub('search',{'q':q},env)
  return [{'symbol':r['symbol'],'name':r.get('description',''),'type':r.get('type','')} for r in result.get('result',[])[:10] if re.fullmatch(r'[A-Z][A-Z.\-]{0,9}',r.get('symbol',''))]
 if path=='/api/chat/market-refresh' and method=='POST':
  symbol=ticker(body.get('symbol'));ident=symbol+'-'+str(int(time.time()//300))
  ok=store.call('POST','rpc/kst_queue_market_data',data={'p_user':user,'p_id':ident,'p_symbol':symbol})
  if not ok:raise ValueError('Market refresh allowance reached; try later')
  return {'queued':True,'symbol':symbol,'message':'Company news and earnings detail refresh queued. Feed access depends on configured data entitlements.'}
 if path=='/api/chat/history-search' and method=='POST':
  q=str(body.get('query') or '').strip()
  if not 1<=len(q)<=120:raise ValueError('Search must contain 1–120 characters')
  return store.call('POST','rpc/kst_search_chat_history',data={'p_user':user,'p_query':q})
 if path=='/api/chat/push-link' and method=='POST':
  token=body.get('token','')
  if not isinstance(token,str) or not re.fullmatch(r'[-A-Za-z0-9_]{32,128}',token):raise ValueError('Invalid private notification management token')
  ok=store.call('POST','rpc/kst_link_private_push',data={'p_user':user,'p_hash':hashlib.sha256(token.encode()).hexdigest()})
  if not ok:raise ValueError('Enable notifications in this browser before linking private alerts')
  return {'linked':True}
 if path=='/api/chat/private-alerts' and method=='GET':return store.rows('kst_private_alerts',user_id='eq.'+user,select='id,kind,position_id,symbol,reason,price,quote_at,created_at',order='created_at.desc',limit=100)
 if path.startswith('/api/chat/positions'):
  if method=='POST':membership.require_access(store,user,env)
  if path=='/api/chat/positions' and method=='GET':return store.rows('kst_personal_positions',user_id='eq.'+user,select='id,symbol,quantity,entry,stop,target,trailing_pct,state,created_at,last_bid,quote_at,alert_reason',order='created_at.desc',limit=100)
  if path=='/api/chat/positions' and method=='POST':
   symbol=ticker(body.get('symbol'));values={k:num(body.get(k)) for k in ('quantity','entry','stop','target')}
   if any(v is None or not 0<v<=100000000 for v in values.values()) or not values['stop']<values['entry']<values['target']:raise ValueError('Use positive quantity and prices, with stop below entry and target above entry')
   trailing=num(body.get('trailing_pct')) if body.get('trailing_pct') not in (None,'') else None
   if body.get('trailing_pct') not in (None,'') and (trailing is None or not 0<trailing<1):raise ValueError('Trailing giveback must be between 0 and 1, or blank')
   row={'id':str(uuid.uuid4()),'user_id':user,'symbol':symbol,**values,'trailing_pct':trailing}
   if not store.call('POST','rpc/kst_save_personal_position',data={'p_row':row}):raise ValueError('At most 20 monitored positions per account')
   return {'id':row['id'],'saved':True,'source':'USER_REPORTED','note':'Monitoring only. This is not a verified broker position or order.'}
  if method=='DELETE' and path.startswith('/api/chat/positions/'):
   ident=str(uuid.UUID(path.rsplit('/',1)[-1]));store.call('PATCH','kst_personal_positions',{'id':'eq.'+ident,'user_id':'eq.'+user},{'state':'CANCELLED'});return {'ok':True}
 raise ValueError('Unknown account route or method')
