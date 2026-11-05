"""Private chat API logic. Supabase verifies tokens; no caller-supplied user IDs."""
import os,json,uuid
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from .logic import uid,public_config,search_terms,build_input,response_text,INSTRUCTIONS
from .vision import prepare_images,CHART_INSTRUCTIONS
class ApiError(Exception):
 def __init__(self,status,message):self.status=status;self.message=message

def http_json(url,headers,body=None,timeout=15):
 raw=None if body is None else json.dumps(body).encode()
 req=Request(url,data=raw,headers={**headers,'Content-Type':'application/json'})
 try:
  with urlopen(req,timeout=timeout) as r:return json.load(r)
 except HTTPError as e:
  if e.code==401:raise ApiError(401,'Authentication failed; check the session or server API credentials')
  if e.code==429:raise ApiError(429,'API rate or quota limit reached; check project usage')
  raise ApiError(502,'An upstream service returned HTTP '+str(e.code))
 except (URLError,TimeoutError):raise ApiError(502,'An upstream service is unavailable; try again later')

def user_from_token(token,env,http=http_json):
 if not token or len(token)>12000:raise ApiError(401,'Sign in to KST Chat')
 config=public_config(env)
 user=http(config['supabase_url']+'/auth/v1/user',{'apikey':config['publishable_key'],'Authorization':'Bearer '+token})
 try:ident=uid(user.get('id'))
 except (ValueError,TypeError):raise ApiError(401,'Invalid signed-in user')
 if user.get('is_anonymous') or not user.get('email_confirmed_at'):raise ApiError(403,'Confirm your email before using KST Chat')
 allowed=[x.strip().lower() for x in env.get('CHAT_ALLOWED_EMAILS','').split(',') if x.strip()]
 if allowed and user.get('email','').lower() not in allowed:raise ApiError(403,'KST Chat is currently limited to invited accounts')
 return ident

def owned(store,user,conversation):
 try:conversation=uid(conversation)
 except (ValueError,TypeError):raise ApiError(400,'Invalid conversation')
 rows=store.rows('kst_chat_conversations',id='eq.'+conversation,user_id='eq.'+user,limit=1)
 if not rows:raise ApiError(404,'Conversation not found')
 return rows[0]

def snapshot(store,message="",user=None):
 now=datetime.now(timezone.utc);sources=[];context={'as_of':now.isoformat(),'limitations':['Read-only database snapshots. No unrestricted web search or broker access.']}
 def gather(key,table,params,prefix,time_field):
  try:
   if key in ('options','setups','stock_plans') and symbols:
    params={**params,('underlying' if key=='options' else 'symbol'):'in.('+','.join(symbols)+')'}
   rows=store.rows(table,**params)
   if key=='setups':
    for r in rows:
     frames=(r.get('details') or {}).get('frames') or {}
     r['details']={'frames':{name:{k:v for k,v in (f or {}).items() if k in ('price','trend','support','resistance','rvol','candle_evidence')} for name,f in frames.items()}}
     for f in r['details']['frames'].values():
      evidence=f.get('candle_evidence')
      if isinstance(evidence,dict):f['candle_evidence']={**evidence,'patterns':evidence.get('patterns',[])[-3:]}
   for i,r in enumerate(rows):
    r['reference']=prefix+str(i+1);sources.append({'id':r['reference'],'label':r.get('title') or r.get('contract') or r.get('symbol') or key,'time':r.get(time_field),'url':r.get('url') if table=='kst_news' else None})
   context[key]=rows
  except Exception:context[key]={'status':'unavailable'}
 import re
 blocked={'AI','IV','ATM','OTM','ITM','EPS','KST','VWAP','EMA','RSI','MACD','OHLC','OPRA','PAPER','LEAPS','BUY','SELL','DTE'}
 symbols=list(dict.fromkeys(x for x in re.findall(r'\b[A-Z]{2,6}\b',message) if x not in blocked))[:4]
 for name,symbol in {'tesla':'TSLA','nvidia':'NVDA','apple':'AAPL','microsoft':'MSFT','amazon':'AMZN','alphabet':'GOOGL','google':'GOOGL','bitcoin':'BTC'}.items():
  if re.search(r'\b'+name+r'\b',message.lower()) and symbol not in symbols:symbols.append(symbol)
 if symbols:
  gather('company_news','kst_company_news',{'select':'symbol,title,url,source,published_at,fetched_at','symbol':'in.('+','.join(symbols)+')','published_at':'gte.'+(now-timedelta(days=7)).isoformat(),'order':'published_at.desc','limit':8},'C','published_at')
  gather('earnings','kst_earnings',{'select':'symbol,report_date,timing,fetched_at,source,details','symbol':'in.('+','.join(symbols)+')','active':'eq.true','report_date':'gte.'+now.date().isoformat(),'order':'report_date.asc','limit':4},'E','fetched_at')
 if user:
  gather('user_reported_positions','kst_personal_positions',{'select':'symbol,quantity,entry,stop,target,state,last_bid,quote_at','user_id':'eq.'+user,'state':'eq.MONITORING','order':'created_at.desc','limit':8},'U','quote_at')
 gather('news','kst_news',{'select':'title,url,source,published_at,sectors','published_at':'gte.'+(now-timedelta(hours=48)).isoformat(),'order':'published_at.desc','limit':8},'N','published_at')
 gather('options','kst_option_signals',{'select':'risk_snapshot,contract,category,score,quality_label,context_label,quote_at,entry_ask,last_bid,last_quote_at,state','order':'created_at.desc','limit':12},'O','quote_at')
 gather('paper_activity','kst_trade_activity',{'select':'agent,action,contract,price,realized_pl,created_at,simulation_only','order':'created_at.desc','limit':8},'P','created_at')
 gather('setups','ultimate_signals',{'select':'symbol,status,side,created_at,details','order':'created_at.desc','limit':3},'S','created_at')
 gather('stock_plans','kst_stock_plans',{'select':'symbol,state,created_at,quote_at,feed,entry_ask,last_bid,stop,target,reason,exit_reason','order':'created_at.desc','limit':8},'T','quote_at')
 gather('learning','kst_option_models',{'select':'version,state,sample_count,created_at','order':'created_at.desc','limit':1},'L','created_at')
 gather('spx_proxy','kst_market_proxy',{'select':'updated_at,payload','id':'eq.SPX','limit':1},'X','updated_at')
 try:context['paper_accounts']=store.call('POST','rpc/kst_ai_progress',data={})
 except Exception:context['paper_accounts']={'status':'unavailable'}
 # Add focused market-research evidence without changing broker permissions.
 try:
  from .market_research import market_research
  research, extra_sources = market_research(store, message, now)
  if research:
   context['market_research'] = research
   sources.extend(extra_sources)
 except Exception:
  context['market_research'] = {'status':'UNAVAILABLE'}
 return context,sources

def handle(method,path,body,user,store,env,http=http_json,emit=None,ai_key=None):
 now=datetime.now(timezone.utc).isoformat()
 from kst_pro.routes import PREFIXES,handle as extra_handle
 from kst_pro.membership import require_access
 try:
  if path.startswith(PREFIXES):return extra_handle(method,path,body,user,store,env)
  if path=='/api/chat/message' or (path=='/api/chat/suggestions' and method=='POST'):require_access(store,user,env)
 except PermissionError as exc:raise ApiError(403,str(exc))
 except ValueError as exc:raise ApiError(400,str(exc))
 if path=='/api/chat/suggestions':
  if method=='GET':
   saved=store.rows('kst_personal_suggestions',user_id='eq.'+user,select='id,request_id,created_at,category,budget,contracts,request_status',order='created_at.desc',limit=50)
   pending=[r['request_id'] for r in saved if r.get('request_status')=='PENDING']
   completed=store.rows('kst_signal_requests',id='in.('+','.join(pending)+')',status='in.(DONE,ERROR)',limit=50) if pending else []
   completed={r['id']:r for r in completed if r.get('status') in ('DONE','ERROR')}
   changes=[]
   fields=('signal_id','contract','underlying','expiration','option_type','strike','category','entry_ask','entry_bid','quote_at','feed','score','quality_label','context_label','fee_estimate','model_version','requested_at','risk_snapshot')
   for row in saved:
    result=completed.get(row['request_id'])
    if row.get('request_status')=='PENDING' and result:
     row.update(contracts=[{k:c.get(k) for k in fields} for c in (result.get('results') or [])[:3]],request_status=result['status'])
     changes.append({**row,'user_id':user})
   if changes:store.call('POST','kst_personal_suggestions',data=changes,prefer='resolution=merge-duplicates,return=minimal')
   ids=set()
   for row in saved:
    for c in row.get('contracts',[])[:3]:
     try:ids.add(uid(c.get('signal_id')))
     except (ValueError,TypeError):pass
   marks=store.rows('kst_option_signals',id='in.('+','.join(sorted(ids))+')',select='id,contract,state,last_bid,last_quote_at,estimated_pl,estimated_return,outcome_return,closed_at',limit=150) if ids else []
   marks={r['id']:r for r in marks}
   for row in saved:row['tracking']=[marks[c['signal_id']] for c in row.get('contracts',[])[:3] if c.get('signal_id') in marks]
   return saved
  if method=='POST':
   import re
   if 'category' in body:
    category=body.get('category');budget=body.get('budget')
    if category not in ('0DTE','Swings','LEAPS') or type(budget) is not int or budget not in (30,50,100,200,500,1000,3000):raise ApiError(400,'Invalid category or budget')
    import time
    request_id=category+'-'+str(budget)+'-'+str(int(time.time()//60))
    ident=str(uuid.uuid5(uuid.NAMESPACE_URL,user+':'+request_id))
    ok=store.call('POST','rpc/kst_queue_personal_request',data={'p_user':user,'p_id':ident,'p_request':request_id,'p_category':category,'p_budget':budget})
    if not ok:raise ApiError(429,'Personal scan request allowance reached; try again later')
    return {'id':request_id,'status':'QUEUED','message':'Request saved to your private account and queued. View My ideas even if you close this page.'}
   request_id=body.get('request_id')
   if not isinstance(request_id,str) or not re.fullmatch(r'(0DTE|Swings|LEAPS)-(30|50|100|200|500|1000|3000)-[0-9]{8,12}',request_id):raise ApiError(400,'Invalid signal request ID')
   results=store.rows('kst_signal_requests',id='eq.'+request_id,status='eq.DONE',limit=1)
   if not results:raise ApiError(409,'The signal request is not complete yet')
   result=results[0]
   fields=('signal_id','contract','underlying','expiration','option_type','strike','category','entry_ask','entry_bid','quote_at','feed','score','quality_label','context_label','fee_estimate','model_version','requested_at','risk_snapshot')
   contracts=[{k:c.get(k) for k in fields} for c in (result.get('results') or [])[:3]]
   ident=str(uuid.uuid5(uuid.NAMESPACE_URL,user+':'+request_id))
   store.insert('kst_personal_suggestions',{'id':ident,'user_id':user,'request_id':request_id,'category':result['category'],'budget':result['budget'],'contracts':contracts,'request_status':'DONE'},ignore=True)
   return {'id':ident,'saved':True,'count':len(contracts),'note':'Private research suggestions, not purchases or broker fills'}
 if path=='/api/chat/conversations':
  if method=='GET':return store.rows('kst_chat_conversations',user_id='eq.'+user,select='id,title,created_at,updated_at',order='updated_at.desc',limit=50)
  if method=='POST':
   row={'id':str(uuid.uuid4()),'user_id':user,'title':str(body.get('title') or 'New conversation')[:80]};store.insert('kst_chat_conversations',row);return {'id':row['id'],'title':row['title']}
 if path.startswith('/api/chat/conversations/'):
  conv=owned(store,user,path.rsplit('/',1)[-1]);ident=conv['id']
  if method=='GET':
   turns=store.rows('kst_chat_turns',conversation_id='eq.'+ident,user_id='eq.'+user,select='id,user_text,assistant_text,status,sources,created_at,attachments',order='created_at.desc',limit=100)
   return {'conversation':conv,'turns':list(reversed(turns))}
  if method=='DELETE':store.call('DELETE','kst_chat_conversations',{'id':'eq.'+ident,'user_id':'eq.'+user});return {'ok':True}
 if path=='/api/chat/memory':
  if method=='GET':return store.rows('kst_chat_memories',user_id='eq.'+user,select='id,content,created_at',order='created_at.asc',limit=30)
  if method=='POST':
   content=str(body.get('content') or '').strip()
   if not 1<=len(content)<=1000:raise ApiError(400,'Memory must contain 1–1000 characters')
   if len(store.rows('kst_chat_memories',user_id='eq.'+user,limit=30))>=30:raise ApiError(400,'Memory is full; delete an old item first')
   row={'id':str(uuid.uuid4()),'user_id':user,'content':content};store.insert('kst_chat_memories',row);return {'id':row['id'],'content':content}
 if path.startswith('/api/chat/memory/') and method=='DELETE':
  try:ident=uid(path.rsplit('/',1)[-1])
  except ValueError:raise ApiError(400,'Invalid memory ID')
  store.call('DELETE','kst_chat_memories',{'id':'eq.'+ident,'user_id':'eq.'+user});return {'ok':True}
 if path.startswith('/api/chat/memory/') and method=='POST':
  try:ident=uid(path.rsplit('/',1)[-1])
  except ValueError:raise ApiError(400,'Invalid memory ID')
  content=str(body.get('content') or '').strip()
  if not 1<=len(content)<=1000:raise ApiError(400,'Memory must contain 1–1000 characters')
  if not store.rows('kst_chat_memories',id='eq.'+ident,user_id='eq.'+user,limit=1):raise ApiError(404,'Memory not found')
  store.call('PATCH','kst_chat_memories',{'id':'eq.'+ident,'user_id':'eq.'+user},{'content':content});return {'ok':True}
 if path=='/api/chat/message' and method=='POST':
  try:images,attachments=prepare_images(body.get('images'))
  except ValueError as exc:raise ApiError(400,str(exc))
  message=str(body.get('message') or '').strip()
  if images and not message:message='Review these charts: structure, candle patterns, observed reaction, conditional scenarios and missing evidence.'
  if not 1<=len(message)<=4000:raise ApiError(400,'Message must contain 1–4000 characters')
  conv=owned(store,user,body.get('conversation_id'))
  try:turn_id=uid(body.get('request_id'))
  except (ValueError,TypeError):raise ApiError(400,'A unique request ID is required')
  existing=store.rows('kst_chat_turns',id='eq.'+turn_id,user_id='eq.'+user,conversation_id='eq.'+conv['id'],limit=1)
  if existing:
   if existing[0]['status']=='COMPLETE':return {'id':turn_id,'text':existing[0]['assistant_text'],'sources':existing[0]['sources'],'cached':True}
   raise ApiError(409,'This message is pending or failed; open history before sending again')
  # No fallback to an owner key, even if OPENAI_API_KEY exists in Railway.
  # Per-request private credentials MUST come from the authenticated user.
  from .user_provider import validate_key,complete
  provider=str(body.get('ai_provider') or 'openai').lower()
  key=validate_key(provider,ai_key)
  allowed=store.call('POST','rpc/kst_chat_reserve',data={'p_user':user,'p_daily':int(env.get('CHAT_DAILY_LIMIT','40')),'p_minute':6,'p_global':int(env.get('CHAT_GLOBAL_DAILY_LIMIT','500'))})
  if not allowed:raise ApiError(429,'KST Chat has reached its per-minute or daily message allowance')
  history=list(reversed(store.rows('kst_chat_turns',conversation_id='eq.'+conv['id'],user_id='eq.'+user,status='eq.COMPLETE',order='created_at.desc',limit=20)))
  memory=store.rows('kst_chat_memories',user_id='eq.'+user,order='created_at.asc',limit=30)
  recalled=store.call('POST','rpc/kst_chat_search',data={'p_user':user,'p_query':search_terms(message),'p_exclude':conv['id']})
  context,sources=snapshot(store,message,user)
  store.insert('kst_chat_turns',{'id':turn_id,'conversation_id':conv['id'],'user_id':user,'user_text':message,'status':'PENDING','attachments':attachments})
  try:
   text=complete(provider,key,build_input(history,memory,recalled,context,message,images),
      INSTRUCTIONS+'\\n'+CHART_INSTRUCTIONS,
      max_tokens=int(env.get('CHAT_MAX_OUTPUT_TOKENS','1500')),
      emit=emit,openai_http=http)
   store.call('PATCH','kst_chat_turns',{'id':'eq.'+turn_id,'user_id':'eq.'+user},{'assistant_text':text,'status':'COMPLETE','sources':sources,'completed_at':datetime.now(timezone.utc).isoformat()})
   store.call('PATCH','kst_chat_conversations',{'id':'eq.'+conv['id'],'user_id':'eq.'+user},{'updated_at':now,'title':message[:70] if not history else conv['title']})
   return {'id':turn_id,'text':text,'sources':sources}
  except Exception as exc:
   store.call('PATCH','kst_chat_turns',{'id':'eq.'+turn_id,'user_id':'eq.'+user},{'status':'FAILED'})
   if isinstance(exc,ApiError) and exc.status==401:raise ApiError(401,'Your provider API key was rejected; connect a valid key with available credits')
   raise
 raise ApiError(404,'Chat route not found')
