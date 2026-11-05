"""Consume real Responses text deltas; require a terminal response before saving."""
import json,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def consume(lines,emit):
 for line in lines:
  if isinstance(line,bytes):line=line.decode('utf-8')
  if not line.startswith('data:'):continue
  value=line[5:].strip()
  if not value or value=='[DONE]':continue
  event=json.loads(value);kind=event.get('type')
  if kind=='response.output_text.delta':emit({'type':'delta','text':str(event.get('delta',''))})
  elif kind in ('response.completed','response.incomplete'):return event['response']
  elif kind in ('error','response.failed'):raise RuntimeError('The model stream failed; check history before retrying')
 raise RuntimeError('The stream ended before a completed response was received')

def request(url,headers,payload,emit,timeout=55):
 start=time.monotonic();req=Request(url,data=json.dumps({**payload,'stream':True}).encode(),headers={**headers,'Content-Type':'application/json','Accept':'text/event-stream'})
 try:response=urlopen(req,timeout=timeout)
 except HTTPError as exc:
  from .service import ApiError
  try:code=json.loads(exc.read(16384)).get('error',{}).get('code')
  except (ValueError,AttributeError):code=None
  if exc.code==401:raise ApiError(503,'Your OpenAI API key was rejected; check your API project access') from None
  if code=='insufficient_quota':raise ApiError(503,'Your OpenAI API project has insufficient credits or quota. Check your own provider billing.') from None
  if exc.code==429:raise ApiError(429,'OpenAI request limit reached. Please wait before retrying.') from None
  if exc.code in (400,403,404):raise ApiError(503,'OpenAI model or project access failed (HTTP '+str(exc.code)+'). Check your provider API project.') from None
  raise ApiError(502,'OpenAI returned HTTP '+str(exc.code)+'. Please check history before retrying.') from None
 with response:
  def lines():
   for line in response:
    if time.monotonic()-start>timeout:raise TimeoutError('Model stream timed out')
    if len(line)>2000000:raise ValueError('Model stream event too large')
    yield line
  return consume(lines(),emit)
