"""Run privately in V3 Railway shell. Never prints keys or raw vendor data."""
from core.unusual_whales import connection_check
from core.uw_research_pipeline import collect_private_snapshot, private_summary

if __name__=='__main__':
    status=connection_check()
    print('Connection:',status)
    if status.get('connected'):
        print('SPY private research status:',private_summary(collect_private_snapshot('SPY')))
