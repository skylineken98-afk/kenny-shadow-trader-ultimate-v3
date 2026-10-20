"""Append-only, private, timestamped research audit log (no secrets/raw licensed feeds)."""
import json, os, re
from datetime import datetime,timezone
from uuid import uuid4

ALLOWED={'signal_created','signal_expired','alert_attempted','paper_order_requested',
         'paper_order_filled','paper_order_rejected','position_closed',
         'challenge_restart','model_evaluated','feed_unavailable'}

def event(kind, *, symbol=None, source='v3', details=None):
 if kind not in ALLOWED: raise ValueError('Unsupported audit event')
 if symbol is not None and not re.fullmatch(r'[A-Za-z0-9.\-]{1,18}',symbol):raise ValueError('Invalid symbol')
 detail=details or {}
 if not isinstance(detail,dict):raise ValueError('details must be a mapping')
 if len(json.dumps(detail))>3000:raise ValueError('Event details too large')
 forbidden=('token','secret','api_key','password','authorization','raw_payload')
 if any(any(w in str(k).lower() for w in forbidden) for k in detail):raise ValueError('Secret-like field rejected')
 return {'event_id':str(uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
         'kind':kind,'symbol':symbol,'source':source,'details':detail}

def append_jsonl(entry,filename):
 """Local development-only journal. Cloud production requires a durable DB."""
 from pathlib import Path
 dest=Path(filename)
 dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('a',encoding='utf-8') as fh:fh.write(json.dumps(entry,sort_keys=True)+'\n')
 return entry['event_id']
