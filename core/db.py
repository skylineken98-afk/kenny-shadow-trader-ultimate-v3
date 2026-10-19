import json, uuid
from datetime import datetime, timezone
from core.settings import get

def now(): return datetime.now(timezone.utc).isoformat()

def client():
    url=get('SUPABASE_URL'); key=get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key: return None
    from supabase import create_client
    return create_client(url,key)


def insert(table, row):
    try:
        c = client()
        if c is None:
            return {'ok': False, 'error': 'Supabase configuration missing'}

        result = c.table(table).insert(row).execute()
        return {'ok': True, 'data': result.data}

    except Exception as exc:
        import logging
        logging.error(
            "Supabase INSERT failed for table %s: %s",
            table,
            type(exc).__name__
        )
        return {
            'ok': False,
            'error': str(exc)
        }


def fetch(table,limit=100,filters=None):
    c=client()
    if c is None: return []
    try:
        query=c.table(table).select('*')
        for k,v in (filters or {}).items(): query=query.eq(k,v)
        return query.order('created_at',desc=True).limit(limit).execute().data or []
    except Exception: return []
