"""Independent virtual-account polling; never submits broker orders."""
import logging,time
from .engine import utcnow,NY,stamp
from .store import Store
from .provider import Provider
from .progress import cycle
log=logging.getLogger('kst_paper')

def run_background():
 store=Store();provider=None
 while True:
  now=utcnow();local=now.astimezone(NY)
  session=local.weekday()<5 and 570<=local.hour*60+local.minute<960
  try:
   if provider is None:provider=Provider()
   cycle(store,provider,now,allow_open=True)
   store.call('POST','kst_options_health',data={'id':'paper_agents','updated_at':stamp(utcnow()),'status':'OK','message':('Independent paper cycle; target 15-second polling plus processing latency. ' if session else 'Market closed; no new paper entries. ')+provider.feed+' research quotes only; no broker fills.'},prefer='resolution=merge-duplicates,return=minimal')
  except Exception as exc:
   log.warning('Paper research cycle failed (%s); no fill invented',type(exc).__name__)
   try:store.call('POST','kst_options_health',data={'id':'paper_agents','updated_at':stamp(utcnow()),'status':'ERROR','message':'Paper research cycle failed; no fill invented. Check data and schema.'},prefer='resolution=merge-duplicates,return=minimal')
   except Exception:pass
  time.sleep(15 if session else 60)
