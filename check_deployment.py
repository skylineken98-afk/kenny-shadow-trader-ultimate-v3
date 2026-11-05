"""Offline configuration checks: python check_deployment.py options|chat|push|pro|execution.
Never prints environment values. Success does not verify live services or SQL.
"""
import argparse,json,os
from urllib.parse import urlsplit

def check(service,env):
 issues=[]
 required=['SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY']+{'options':['ALPACA_API_KEY','ALPACA_API_SECRET'],'chat':['OPENAI_API_KEY','CHAT_PROXY_TOKEN'],'push':['VAPID_PRIVATE_KEY','VAPID_SUBJECT'],'pro':['FINNHUB_API_KEY','ALPACA_API_KEY','ALPACA_API_SECRET'],'execution':[]}[service]
 for name in required:
  if not env.get(name,'').strip():issues.append(name+': missing')
 try:
  u=urlsplit(env.get('SUPABASE_URL',''))
  if u.scheme!='https' or not (u.hostname or '').endswith('.supabase.co') or u.username or u.password or u.port not in (None,443):raise ValueError()
 except ValueError:issues.append('SUPABASE_URL: expected the HTTPS project URL')
 if service=='options':
  from kst_options.engine import num
  if env.get('OPTIONS_FEED','opra') not in ('opra','indicative'):issues.append('OPTIONS_FEED: use opra or indicative')
  fee=num(env.get('OPTIONS_ROUND_TRIP_FEE','0'))
  if fee is None or fee<0:issues.append('OPTIONS_ROUND_TRIP_FEE: expected a finite nonnegative number')
  for name,default in [('OPTIONS_SCAN_SECONDS','300'),('OPTIONS_TRACK_SECONDS','60'),('NEWS_POLL_SECONDS','300')]:
   try:
    if int(env.get(name,default))<=0:raise ValueError()
   except ValueError:issues.append(name+': expected a positive integer')
 if service=='chat':
  from kst_chat.logic import public_config
  try:public_config(env)
  except ValueError:issues.append('Configure a public Supabase auth key and valid project URL')
  if len(env.get('CHAT_PROXY_TOKEN',''))<32:issues.append('CHAT_PROXY_TOKEN: requires at least 32 characters')
 if service=='execution':
  from kst_pro.execution import configured,limits
  if not configured(env):issues.append('Execution intentionally disabled or explicit live configuration incomplete')
  try:limits(env)
  except ValueError:issues.append('Live risk limits must be finite and positive')
 if service=='chat' and env.get('STRIPE_SECRET_KEY'):
  for name in ('STRIPE_WEBHOOK_SECRET','STRIPE_MONTHLY_PRICE_ID','KST_SITE_URL'):
   if not env.get(name):issues.append(name+': required when billing is configured')
 if service=='push' and not env.get('VAPID_SUBJECT','').startswith('mailto:'):issues.append('VAPID_SUBJECT: expected mailto: followed by a contact email')
 return {'service':service,'configuration_ok':not issues,'issues':issues,'verification':'Offline only. Verify SQL migrations, credentials, feed entitlements and end-to-end behavior after deployment.'}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('service',choices=['options','chat','push','pro','execution'])
 result=check(parser.parse_args().service,os.environ);print(json.dumps(result,indent=2));raise SystemExit(0 if result['configuration_ok'] else 1)
