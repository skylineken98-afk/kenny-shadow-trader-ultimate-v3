import threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from kst_chat import server

def test_http_transport_enforces_proxy_login_and_image_request_limit(monkeypatch):
 monkeypatch.setenv('CHAT_PROXY_TOKEN','x'*40)
 monkeypatch.setattr(server,'user_from_token',lambda *args:'00000000-0000-0000-0000-000000000001')
 http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
 thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
 base='http://127.0.0.1:'+str(http.server_port)
 try:
  with urlopen(base+'/health',timeout=2) as r:assert r.status==200
  for headers,status in [({},403),({'X-KST-Proxy':'x'*40},401),({'X-KST-Proxy':'x'*40,'Authorization':'Bearer test','Content-Length':str(3*1024*1024+1)},413)]:
   req=Request(base+'/api/chat/message',data=b'',headers=headers,method='POST')
   try:urlopen(req,timeout=2)
   except HTTPError as exc:assert exc.code==status
   else:raise AssertionError('Request should have failed')
 finally:http.shutdown();http.server_close();thread.join(timeout=2)
