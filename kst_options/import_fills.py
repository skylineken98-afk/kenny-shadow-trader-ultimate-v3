"""Optional private CSV import, NOT a live broker integration.
python -m kst_options.import_fills fills.csv
Columns: fill_id,filled_at,contract,side,quantity,price,fees
Long-option FIFO realized P/L; unsupported short sales abort before any writes.
"""
import csv,sys
from collections import defaultdict,deque
from .engine import parse,num
def pnl(rows):
 lots=defaultdict(deque);realized=0
 for r in sorted(rows,key=lambda x:parse(x['filled_at'])):
  q=int(r['quantity']);price=float(r['price']);fees=float(r['fees']);symbol=r['contract']
  if r['side']=='BUY':lots[symbol].append([q,price,fees/q])
  else:
   if sum(l[0] for l in lots[symbol])<q:raise ValueError('Unmatched SELL: import complete long-position history first. Shorts are unsupported.')
   while q:
    lot=lots[symbol][0];n=min(q,lot[0]);realized+=n*((price-lot[1])*100-lot[2]-fees/int(r['quantity']));q-=n;lot[0]-=n
    if not lot[0]:lots[symbol].popleft()
 return realized

def completed_lots(rows):
 lots=defaultdict(deque);completed=[]
 for r in sorted(rows,key=lambda x:(parse(x['filled_at']),x['fill_id'])):
  qty=int(r['quantity'])
  if r['side']=='BUY':lots[r['contract']].append({'entry':r,'left':qty,'pl':-float(r['fees'])})
  else:
   if sum(l['left'] for l in lots[r['contract']])<qty:raise ValueError('Unmatched SELL')
   while qty:
    lot=lots[r['contract']][0];n=min(qty,lot['left']);entry=lot['entry']
    lot['pl']+=n*(float(r['price'])-float(entry['price']))*100-n*float(r['fees'])/int(r['quantity'])
    qty-=n;lot['left']-=n
    if not lot['left']:
     completed.append({'id':entry['fill_id'],'created_at':entry['filled_at'],'closed_at':r['filled_at'],'contract':r['contract'],'realized_pl':lot['pl'],'outcome_return':lot['pl']/(float(entry['price'])*100*int(entry['quantity'])) if float(entry['price'])>0 else None})
     lots[r['contract']].popleft()
 return completed

def save_outcomes(store,rows):
 count=0
 for lot in completed_lots(rows):
  if lot['outcome_return'] is None:continue
  # No future data: attach only a recent OPRA research context known before entry.
  signals=store.rows('kst_option_signals',contract='eq.'+lot['contract'],quality_label='eq.QUALIFIED',feed='eq.opra',created_at='lte.'+lot['created_at'],order='created_at.desc',limit=1)
  if not signals or (parse(lot['created_at'])-parse(signals[0]['created_at'])).total_seconds()>5400:continue
  store.insert('kst_trade_outcomes',{**lot,'features':signals[0]['features'],'state':'CLOSED','feed':'actual','source':'USER_IMPORTED_NOT_BROKER_VERIFIED'},ignore=True);count+=1
 return count

def main(path):
 from .store import Store
 store=Store();existing=[];offset=0
 while True:
  page=store.rows('kst_imported_fills',order='filled_at.asc,fill_id.asc',limit=500,offset=offset);existing.extend(page)
  if len(page)<500:break
  offset+=500
 by_id={r['fill_id']:r for r in existing};new=[]
 with open(path,newline='') as f:
  for r in csv.DictReader(f):
   t=parse(r['filled_at']);q=num(r['quantity']);price=num(r['price']);fees=num(r.get('fees') or 0)
   if not r['fill_id'] or not r['contract'] or t.tzinfo is None or r['side'] not in ('BUY','SELL') or q is None or q<=0 or int(q)!=q or price is None or price<0 or fees is None or fees<0:raise ValueError('Invalid fill row')
   row={**{k:r[k] for k in ('fill_id','filled_at','contract','side')},'quantity':int(q),'price':price,'fees':fees,'source':'USER_IMPORTED_NOT_BROKER_VERIFIED'}
   if row['fill_id'] in by_id:
    prev=by_id[row['fill_id']]
    if any(str(prev[k])!=str(row[k]) for k in ('contract','side')) or any(float(prev[k])!=float(row[k]) for k in ('quantity','price','fees')) or parse(prev['filled_at'])!=t:raise ValueError('Conflicting fill_id')
    continue
   by_id[row['fill_id']]=row;new.append(row)
 total=pnl(list(by_id.values()))
 if new:store.insert('kst_imported_fills',new,ignore=True)
 matched=save_outcomes(store,list(by_id.values()))
 from .sessions import review
 from .engine import utcnow,stamp
 reports=review(list(by_id.values()))
 for report in reports:
  store.call('POST','kst_session_reviews',data={'id':report['date'],'updated_at':stamp(utcnow()),'report':report},prefer='resolution=merge-duplicates,return=minimal')
 if reports:
  latest=reports[-1]
  print(f"Latest session {latest['date']}: realized ${latest['realized_pl']:.2f}; realized peak ${latest['realized_peak']:.2f}; giveback ${latest['giveback_dollars']:.2f}; rapid same-contract reentries {latest['rapid_reentries']}. Pattern review, not proof of motive.")
 from .learning import train
 train(store)
 print(f'{matched} completed lots have matching historical context. Imported {len(new)} private fill rows. User-imported FIFO realized P/L: ${total:.2f}. Not broker verified.')
if __name__=='__main__':main(sys.argv[1])
