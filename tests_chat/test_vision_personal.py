import base64,io,uuid
from PIL import Image
from kst_chat.vision import prepare_images,CHART_INSTRUCTIONS
from kst_chat.service import handle
from test_chat import Store,ENV,U1,U2,C1,expect

def picture():
 out=io.BytesIO();Image.new('RGB',(64,64),'white').save(out,format='PNG')
 return {'data_url':'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()}

def test_chart_images_are_validated_normalized_and_not_saved():
 images,meta=prepare_images([picture()]);assert images[0]['type']=='input_image' and images[0]['detail']=='high'
 assert images[0]['image_url'].startswith('data:image/jpeg;base64,')
 assert meta[0]['image_retained'] is False and meta[0]['width']==64
 db=Store();payloads=[]
 def http(url,headers,body,**kwargs):
  payloads.append(body);assert body['input'][-1]['content'][1]['type']=='input_image'
  assert body['store'] is False and 'No future candles means pending' in body['instructions']
  return {'output':[{'type':'message','content':[{'type':'output_text','text':'Visible reaction is pending.'}]}]}
 handle('POST','/api/chat/message',{'conversation_id':C1,'message':'','request_id':str(uuid.uuid4()),'images':[picture()]},U1,db,ENV,http)
 assert len(payloads)==1 and 'data:image' not in str(db.data)
 assert db.data['kst_chat_turns'][0]['attachments'][0]['image_retained'] is False

def test_malformed_or_remote_images_fail_before_quota():
 for images in ([{'data_url':'https://example.com/chart.png'}],[{'data_url':'data:image/png;base64,YmFk'}],[picture()]*3,'not-list'):
  db=Store();expect(400,lambda:handle('POST','/api/chat/message',{'conversation_id':C1,'message':'review','request_id':str(uuid.uuid4()),'images':images},U1,db,ENV))
  assert db.reserves==0

def test_private_suggestions_copy_trusted_results_and_remain_owner_scoped():
 db=Store();request='0DTE-100-29900000';signal=str(uuid.uuid4())
 db.data['kst_signal_requests']=[dict(id=request,status='DONE',category='0DTE',budget=100,results=[dict(contract='REAL',signal_id=signal,entry_ask=.50)])]
 db.data['kst_option_signals']=[dict(id=signal,contract='REAL',state='OPEN',last_bid=.60)]
 response=handle('POST','/api/chat/suggestions',{'request_id':request,'contracts':[{'contract':'FORGED'}],'user_id':U2},U1,db,ENV)
 saved=db.data['kst_personal_suggestions'][0]
 assert response['saved'] and saved['user_id']==U1 and saved['contracts'][0]['contract']=='REAL'
 assert handle('GET','/api/chat/suggestions',{},U2,db,ENV)==[]
 rows=handle('GET','/api/chat/suggestions',{},U1,db,ENV)
 assert rows[0]['tracking'][0]['last_bid']==.60

def test_personal_request_is_recorded_before_scanning_with_server_identity():
 class QueueStore(Store):
  def call(self,method,table,params=None,data=None,**kw):
   if table=='rpc/kst_queue_personal_request':
    assert data['p_user']==U1 and data['p_category']=='Swings' and data['p_budget']==100
    return True
   return super().call(method,table,params,data,**kw)
 db=QueueStore();r=handle('POST','/api/chat/suggestions',{'category':'Swings','budget':100,'user_id':U2},U1,db,ENV)
 assert r['status']=='QUEUED'
 expect(400,lambda:handle('POST','/api/chat/suggestions',{'category':'Swings','budget':True},U1,db,ENV))

def test_pending_archive_resolves_after_browser_closed():
 db=Store();ident=str(uuid.uuid4());request='0DTE-100-29900000'
 db.data['kst_personal_suggestions']=[dict(id=ident,user_id=U1,request_id=request,request_status='PENDING',contracts=[])]
 db.data['kst_signal_requests']=[dict(id=request,status='DONE',results=[dict(contract='REAL')])]
 rows=handle('GET','/api/chat/suggestions',{},U1,db,ENV)
 assert rows[0]['request_status']=='DONE' and rows[0]['contracts'][0]['contract']=='REAL'
