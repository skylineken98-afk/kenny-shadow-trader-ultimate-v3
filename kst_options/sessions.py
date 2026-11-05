"""Private daily execution review. Flags describe patterns, never motivation."""
from collections import defaultdict,deque
from .engine import parse,NY

def review(rows):
 lots=defaultdict(deque);days={};last_exit={}
 for r in sorted(rows,key=lambda x:(parse(x['filled_at']),x['fill_id'])):
  t=parse(r['filled_at']);day=t.astimezone(NY).date().isoformat();symbol=r['contract'];qty=int(r['quantity']);price=float(r['price']);fee=float(r['fees'])
  d=days.setdefault(day,dict(date=day,buy_fill_count=0,sell_fill_count=0,rapid_reentries=0,realized_pl=0.,realized_peak=0.,max_losing_exit_streak=0,losing_exit_streak=0))
  if r['side']=='BUY':
   d['buy_fill_count']+=1
   if symbol in last_exit and 0<=(t-last_exit[symbol]).total_seconds()<=300:d['rapid_reentries']+=1
   lots[symbol].append([qty,price,fee/qty]);continue
  if sum(l[0] for l in lots[symbol])<qty:raise ValueError('Missing opening history')
  event_pl=0.
  while qty:
   l=lots[symbol][0];n=min(qty,l[0]);event_pl+=n*((price-l[1])*100-l[2]-fee/int(r['quantity']));qty-=n;l[0]-=n
   if not l[0]:lots[symbol].popleft()
  d['sell_fill_count']+=1;d['realized_pl']+=event_pl;d['realized_peak']=max(d['realized_peak'],d['realized_pl'])
  d['losing_exit_streak']=d['losing_exit_streak']+1 if event_pl<0 else 0
  d['max_losing_exit_streak']=max(d['max_losing_exit_streak'],d['losing_exit_streak']);last_exit[symbol]=t
 for d in days.values():
  d['giveback_dollars']=d['realized_peak']-d['realized_pl']
  d['giveback_fraction']=d['giveback_dollars']/d['realized_peak'] if d['realized_peak']>0 else None
  d['note']='Realized fills only. Rapid re-entry means another BUY fill in the same contract within five minutes of a SELL; not proof of revenge trading or chop. No automatic trading lock.'
 return list(days.values())
