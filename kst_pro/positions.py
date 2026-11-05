"""Quote monitoring for user-reported long equity positions; no execution."""
import os,requests
from kst_options.engine import quote,utcnow,NY,stamp

def refresh(store,now,http=None):
 local=now.astimezone(NY)
 if local.weekday()>4 or not 570<=local.hour*60+local.minute<960:return
 rows=[];offset=0
 while True:
  page=store.rows('kst_personal_positions',state='eq.MONITORING',order='id.asc',limit=200,offset=offset);rows.extend(page)
  if len(page)<200:break
  offset+=200
 symbols=list(dict.fromkeys(r['symbol'] for r in rows));quotes={}
 for i in range(0,len(symbols),100):
  response=(http or requests.get)('https://data.alpaca.markets/v2/stocks/quotes/latest',params={'symbols':','.join(symbols[i:i+100]),'feed':os.getenv('STOCK_FEED','iex') or 'iex'},headers={'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'],'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET']},timeout=20)
  if not response.ok:raise RuntimeError('Private position quote feed unavailable')
  quotes.update(response.json().get('quotes',{}))
 for row in rows:
  q=quote(quotes.get(row['symbol'],{}),utcnow(),max_age=60)
  if q and q[0]>0:store.call('POST','rpc/kst_mark_personal',data={'p_id':row['id'],'p_bid':q[0],'p_quote':stamp(q[2])})
