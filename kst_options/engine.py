"""Pure research calculations. Immutable ask entry; bid marks; one standard contract."""
import math,re
from decimal import Decimal, InvalidOperation
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
NY=ZoneInfo('America/New_York')
BASE=[0.55,0.30,0.15]
BUDGETS=[30,50,100,200,500,1000,3000]
def utcnow():return datetime.now(timezone.utc)
def stamp(t):return t.isoformat()
def parse(t):return datetime.fromisoformat(str(t).replace('Z','+00:00'))
def num(x):
 try:
  n=float(x)
  return n if math.isfinite(n) else None
 except (ValueError,TypeError):return None
def quote(q,now,max_age=300):
 bid,ask=num(q.get('bp')),num(q.get('ap'))
 try:t=parse(q.get('t'))
 except (ValueError,TypeError):return None
 if t.tzinfo is None or bid is None or ask is None or bid<0 or ask<=0 or ask<bid:return None
 if not 0<=(now-t).total_seconds()<=max_age:return None
 return bid,ask,t
def category(exp,now):
 d=(exp-now.astimezone(NY).date()).days
 return '0DTE' if d==0 else 'Swings' if 5<=d<=45 else 'LEAPS' if 270<=d<=730 else None
def candidate(contract,snapshot,now,feed,weights=BASE,relaxed=False):
 match=re.fullmatch(r'([A-Z.]+)(\d{6})([CP])(\d{8})',contract)
 if not match:return None
 try:exp=datetime.strptime(match[2],'%y%m%d').date()
 except ValueError:return None
 local=now.astimezone(NY)
 if local.weekday()>4 or not (9*60+30<=local.hour*60+local.minute<16*60):return None
 cat=category(exp,now);q=quote(snapshot.get('latestQuote') or {},now,max_age=60)
 if cat is None or q is None:return None
 bid,ask,t=q
 if bid<=0 or ask*100>3000:return None
 spread=(ask-bid)/((ask+bid)/2)
 if spread>(.25 if relaxed else .15):return None
 delta=num((snapshot.get('greeks') or {}).get('delta'))
 if delta is None or not ((.15 if relaxed else .20)<=abs(delta)<=(.85 if relaxed else .80)):return None
 # Structural quality only; never a probability of profit.
 f=[max(0,1-spread/.15),max(0,1-abs(abs(delta)-.5)/.3),1-min(1,ask*100/3000)]
 return dict(risk_snapshot={'exit_policy':'profit-lock-v1','greeks':{k:num((snapshot.get('greeks') or {}).get(k)) for k in ('delta','gamma','theta','vega','rho')},'implied_volatility':num(snapshot.get('impliedVolatility')),'observed_at':stamp(now),'source':'Provider snapshot. Greek and IV timestamps/units are not independently verified; quote time is not a Greek timestamp.'},quality_label='WATCHLIST' if relaxed else 'QUALIFIED',contract=contract,underlying=match[1],expiration=str(exp),option_type='CALL' if match[3]=='C' else 'PUT',strike=int(match[4])/1000,category=cat,entry_ask=ask,entry_bid=bid,quote_at=stamp(t),feed=feed,features=f,score=score(f,weights))
def score(f,w):return round(100*sum(a*b for a,b in zip(f,w)),3)
def deadline(c,now):
 horizon={'0DTE':timedelta(hours=1),'Swings':timedelta(days=1),'LEAPS':timedelta(days=7)}[c['category']]
 expiry=datetime.combine(datetime.fromisoformat(c['expiration']).date(),datetime.min.time(),NY).replace(hour=16).astimezone(timezone.utc)
 return expiry if (c.get('risk_snapshot') or {}).get('exit_policy')=='profit-lock-v1' else min(now+horizon,expiry)
def mark(signal,q,now,fee=0):
 fresh=quote(q,now)
 if fresh is None:return None
 bid,ask,t=fresh
 if t<=parse(signal['quote_at']) or (signal.get('last_quote_at') and t<=parse(signal['last_quote_at'])):return None
 entry=float(signal['entry_ask']);pl=(bid-entry)*100-fee;ret=pl/(entry*100)
 oldmax=signal.get('max_return');oldmin=signal.get('min_return')
 result=dict(last_bid=bid,last_quote_at=stamp(t),estimated_pl=pl,estimated_return=ret,max_return=max(ret,oldmax if oldmax is not None else ret),min_return=min(ret,oldmin if oldmin is not None else ret),target_seen=bool(signal.get('target_seen')) or ret>=.5,stop_seen=bool(signal.get('stop_seen')) or ret<=-.3)
 # First observed barrier is separate from the original horizon outcome.
 # Polling cannot establish the path or fills between observations.
 risk=dict(signal.get('risk_snapshot') or {})
 barrier=dict(risk.get('observed_barrier') or {})
 if not barrier and (signal.get('target_seen') or signal.get('stop_seen')):
  barrier={'version':'sampled-v1','outcome':'PRIOR_ORDER_UNKNOWN',
           'limitation':'Legacy barrier flags exist without first-crossing timestamps; audit saved marks'}
  risk['observed_barrier']=barrier
  result['risk_snapshot']=risk
 if not barrier and t<=parse(signal['due_at']) and (ret>=.5 or ret<=-.3):
  barrier={'version':'sampled-v1','outcome':'TARGET_FIRST_OBSERVED' if ret>=.5 else 'STOP_FIRST_OBSERVED',
           'quote_at':stamp(t),'observed_return':ret,'bid':bid,
           'previous_quote_at':signal.get('last_quote_at') or signal['quote_at'],
           'limitation':'First sampled crossing only; intrapoll path and execution unverified'}
  risk['observed_barrier']=barrier
  result['risk_snapshot']=risk
 from .profit_lock import observe
 # Gross premium ladder is distinct from fee-adjusted P/L and horizon labels.
 risk=dict(result.get('risk_snapshot') or signal.get('risk_snapshot') or {})
 risk['profit_lock']=observe(signal,bid,t)
 result['risk_snapshot']=risk
 if risk.get('exit_policy')=='profit-lock-v1' and risk['profit_lock'].get('stop_hit_at'):
  result.update(state='CLOSED',closed_at=stamp(t),outcome_return=ret)
  return result
 # Label only near-horizon executable quotes. No fabricated expiry settlement.
 if t>=parse(signal['due_at']):
  late=(t-parse(signal['due_at'])).total_seconds()
  result.update(state='CLOSED' if late<=1800 else 'UNRESOLVED',closed_at=stamp(now),outcome_return=ret if late<=1800 else None)
 return result

def affordable(ask,budget,fee=0):
 # Reserve the full configured round-trip fee; decimal arithmetic preserves cent boundaries.
 try:
  ask,budget,fee=(Decimal(str(x)) for x in (ask,budget,fee))
  return all(x.is_finite() for x in (ask,budget,fee)) and ask>0 and budget>0 and fee>=0 and ask*100+fee<=budget
 except (InvalidOperation,ValueError,TypeError):return False

def requested_choices(candidates,category,budget,fee=0):
 from .universe import diverse_choices
 choices=[c for c in candidates if c['category']==category and affordable(c['entry_ask'],budget,fee)]
 return diverse_choices(choices,3)

def context_label(contract,setup,now):
 if not setup or setup.get('status')!='SETUP':return 'STRUCTURAL_ONLY'
 try:
  age=(now-parse(setup['created_at'])).total_seconds()
 except (ValueError,TypeError,KeyError):return 'STRUCTURAL_ONLY'
 if not 0<=age<=300:return 'STRUCTURAL_ONLY'
 # Processing time is not evidence that the underlying bars are current.
 try:
  closed=parse(setup['details']['frames']['5m']['bar_closed_at'])
  if not 0<=(now-closed).total_seconds()<=600:return 'STRUCTURAL_ONLY'
 except (KeyError,TypeError,ValueError):return 'STRUCTURAL_ONLY'
 side=setup.get('side')
 if (side=='BULLISH' and contract['option_type']=='CALL') or (side=='BEARISH' and contract['option_type']=='PUT'):return side+'_SETUP_ALIGNED'
 return 'COUNTER_TREND_RESEARCH'
