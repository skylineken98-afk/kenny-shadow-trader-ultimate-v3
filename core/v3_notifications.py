"""Telegram test alerts. Explicit approval required; no automatic subscriptions."""
import os
import requests

class NotificationError(RuntimeError):pass

def send_private_test(text='V3 notification test',*,approved=False,session=None):
 if not approved:return {'sent':False,'reason':'Approval required'}
 token=os.environ.get('TELEGRAM_BOT_TOKEN','').strip()
 chat=os.environ.get('TELEGRAM_CHAT_ID','').strip()
 if not token or not chat:return {'sent':False,'reason':'Missing Telegram configuration'}
 if not isinstance(text,str) or len(text)>500:return {'sent':False,'reason':'Invalid message'}
 try:
  resp=(session or requests).post('https://api.telegram.org/bot'+token+'/sendMessage',
            json={'chat_id':chat,'text':text,'disable_web_page_preview':True},timeout=15)
  resp.raise_for_status()
  ok=resp.json().get('ok') is True
  return {'sent':ok,'reason':'Accepted' if ok else 'Telegram rejected message'}
 except (requests.RequestException,ValueError):return {'sent':False,'reason':'Delivery not verified'}
