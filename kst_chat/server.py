"""Authenticated JSON/SSE service behind Railway HTTPS and Cloudflare."""
import os,json,hmac,socket,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from .service import handle,user_from_token,ApiError
from .logic import public_config
from .vision import MAX_REQUEST_BYTES
SLOTS=threading.BoundedSemaphore(24)
class Handler(BaseHTTPRequestHandler):
 server_version='KSTChat/2.0'
 def log_message(self,*args):pass
 def reply(self,status,body):
  if getattr(self,'streaming',False):self.emit({'type':'error','error':body.get('error','Request failed')});return
  raw=json.dumps(body,ensure_ascii=False).encode();self.send_response(status)
  for k,v in {'Content-Type':'application/json; charset=utf-8','Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}.items():self.send_header(k,v)
  self.end_headers();self.wfile.write(raw)
 def emit(self,event):
  if not getattr(self,'streaming',False):
   self.send_response(200)
   for k,v in {'Content-Type':'text/event-stream','Cache-Control':'no-store','X-Accel-Buffering':'no','Connection':'close','X-Content-Type-Options':'nosniff'}.items():self.send_header(k,v)
   self.end_headers();self.streaming=True;self.close_connection=True
  if getattr(self,'disconnected',False):return
  try:self.wfile.write(('data: '+json.dumps(event,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
  except (BrokenPipeError,ConnectionResetError):self.disconnected=True
 def read_body(self,limit):
  try:length=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ApiError(400,'Invalid request length')
  if not 0<=length<=limit:raise ApiError(413,'Message payload is too large')
  return self.rfile.read(length)
 def run_api(self):
  self.streaming=False
  if not SLOTS.acquire(blocking=False):self.reply(503,{'error':'Service is busy; please retry shortly'});return
  try:
   self.connection.settimeout(80);path=urlsplit(self.path).path
   if path=='/health' and self.command=='GET':self.reply(200,{'service':'kst-chat','status':'running'});return
   from kst_options.store import Store
   if path=='/ready' and self.command=='GET':
    try:Store().rows('kst_memberships',select='user_id',limit=1);self.reply(200,{'ready':True})
    except Exception:self.reply(503,{'ready':False})
    return
   if path=='/webhooks/stripe' and self.command=='POST':
    from kst_pro.membership import webhook
    raw=self.read_body(131072)
    try:result=webhook(Store(),raw,self.headers.get('Stripe-Signature'),os.environ)
    except (ValueError,KeyError,TypeError):raise ApiError(400,'Invalid payment webhook')
    self.reply(200,result);return
   secret=os.getenv('CHAT_PROXY_TOKEN','')
   if len(secret)<32:raise ApiError(503,'Configure the chat proxy secret on Railway')
   if not hmac.compare_digest(self.headers.get('X-KST-Proxy',''),secret):raise ApiError(403,'Requests must use the KST website')
   if path=='/api/chat/config' and self.command=='GET':self.reply(200,public_config(os.environ));return
   authorization=self.headers.get('Authorization','')
   if not authorization.startswith('Bearer '):raise ApiError(401,'Sign in to KST')
   user=user_from_token(authorization[7:],os.environ)
   raw=self.read_body(MAX_REQUEST_BYTES if path in ('/api/chat/message','/api/chat/stream') and self.command=='POST' else 32768);body={}
   if raw:
    try:body=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ApiError(400,'Invalid JSON')
    if not isinstance(body,dict):raise ApiError(400,'Expected a JSON object')
   streaming=path=='/api/chat/stream' and self.command=='POST'
   result=handle(self.command,'/api/chat/message' if streaming else path,body,user,Store(),os.environ,emit=self.emit if streaming else None,ai_key=self.headers.get('X-KST-User-AI-Key') if path in ('/api/chat/message','/api/chat/stream') else None)
   if streaming:self.emit({'type':'done','result':result})
   else:self.reply(200,result)
  except ApiError as exc:self.reply(exc.status,{'error':exc.message})
  except (socket.timeout,TimeoutError):self.reply(504,{'error':'Request timed out. Check history before retrying.'})
  except Exception:self.reply(502,{'error':'Service failed. Check configuration, migrations and upstream availability.'})
  finally:SLOTS.release()
 do_GET=run_api
 do_POST=run_api
 do_DELETE=run_api

class BoundedServer(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,*args,**kwargs):
  self.connections=threading.BoundedSemaphore(32);super().__init__(*args,**kwargs)
 def get_request(self):
  connection,address=super().get_request();connection.settimeout(8);return connection,address
 def process_request(self,request,address):
  if not self.connections.acquire(blocking=False):
   try:request.sendall(b'HTTP/1.0 503 Busy\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
   finally:self.shutdown_request(request)
   return
  try:super().process_request(request,address)
  except Exception:self.connections.release();raise
 def process_request_thread(self,request,address):
  try:super().process_request_thread(request,address)
  finally:self.connections.release()

if __name__=='__main__':
 from kst_pro.ops import heartbeat_loop
 threading.Thread(target=heartbeat_loop,args=('chat',),daemon=True).start()
 BoundedServer(('0.0.0.0',int(os.getenv('PORT','8080'))),Handler).serve_forever()
