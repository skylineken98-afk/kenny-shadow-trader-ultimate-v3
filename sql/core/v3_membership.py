"""Verified webhook state transition helper. Billing gateway integration NOT included."""
from datetime import datetime,timezone

STATES={'trial','active','past_due','canceled','expired'}

def transition(current, event, *, verified_webhook=False, event_id=None):
 if not verified_webhook or not event_id:return {'accepted':False,'state':current,'reason':'Verified signed webhook required'}
 allowed={'trial':{'paid':'active','expired':'expired'},
          'active':{'failed':'past_due','canceled':'canceled'},
          'past_due':{'paid':'active','expired':'expired','canceled':'canceled'},
          'canceled':{},'expired':{}}
 if current not in STATES or event not in allowed[current]:return {'accepted':False,'state':current,'reason':'Unsupported transition'}
 return {'accepted':True,'state':allowed[current][event],'event_id':event_id,
         'observed_at':datetime.now(timezone.utc).isoformat()}
