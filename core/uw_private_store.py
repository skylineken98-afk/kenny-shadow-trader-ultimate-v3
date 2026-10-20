"""Optional server-only, entitlement-gated Supabase storage.
Never publish records from this table; follow vendor retention and license terms.
"""
import os
from .uw_research_pipeline import snapshot_id

def save_snapshot(snapshot, *, license_confirmed=False, client=None):
    if not license_confirmed or os.getenv('UW_PRIVATE_STORAGE_ENABLED','false').lower()!='true':
        return {'saved':False,'reason':'Vendor storage permission and opt-in required'}
    if client is None:
        url=os.environ.get('SUPABASE_URL')
        key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        if not url or not key:return {'saved':False,'reason':'Supabase server credentials unavailable'}
        from supabase import create_client
        client=create_client(url,key)
    row={'id':snapshot_id(snapshot), 'ticker':snapshot['ticker'],
         'observed_at':snapshot['observed_at'], 'source_names':list(snapshot['sources']),
         'payload':snapshot,'access_scope':'private_research'}
    client.table('uw_private_research_snapshots').upsert(row,on_conflict='id').execute()
    return {'saved':True,'id':row['id']}
