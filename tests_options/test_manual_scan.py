from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from kst_options.engine import category
from kst_options.worker import scan


def test_swing_window_stays_45_days():
    now = datetime(2026, 11, 6, 20, tzinfo=timezone.utc)
    assert category(now.date() + timedelta(days=4), now) is None
    assert category(now.date() + timedelta(days=5), now) == 'Swings'
    assert category(now.date() + timedelta(days=45), now) == 'Swings'
    assert category(now.date() + timedelta(days=46), now) is None


def test_manual_request_scans_all_configured_symbols():
    now = datetime(2026, 11, 6, 20, tzinfo=timezone.utc)
    class Store:
        def rows(self, table, **kwargs):
            if table == 'kst_signal_requests':
                return [dict(id='manual', category='Swings', budget=100, created_at=now.isoformat())]
            return []
        def call(self, *args, **kwargs): pass
        def patch(self, *args, **kwargs): pass
        def health(self, *args): pass
    class Provider:
        feed = 'indicative'
        def __init__(self): self.symbols = set()
        def chain(self, symbol, lo, hi):
            self.symbols.add(symbol)
            return []
    provider = Provider()
    with patch('kst_options.worker.active', return_value=([.55,.3,.15], 'test')), \
         patch('kst_options.worker.universe', return_value=['AAPL','PFE','RIVN']), \
         patch('kst_options.worker.rotating_batch', return_value=['AAPL']), \
         patch('kst_options.worker.priority_index_symbols', return_value=[]), \
         patch('kst_options.worker.sector_returns', return_value={}):
        scan(Store(), provider, now)
    assert provider.symbols == {'AAPL','PFE','RIVN'}


def test_tracking_ignores_duplicate_signal_quote_pair():
    from kst_options.worker import track
    now = datetime(2026, 11, 6, 20, tzinfo=timezone.utc)
    calls=[]
    class Store:
        def rows(self, *args, **kwargs):
            return [dict(id='s',contract='X',due_at=(now+timedelta(days=1)).isoformat(),quote_at=(now-timedelta(minutes=1)).isoformat(),entry_ask=1)]
        def call(self, *args, **kwargs): calls.append((args,kwargs))
        def patch(self, *args, **kwargs): pass
    class Provider:
        feed='indicative'
        def quotes(self, contracts): return {'X':dict(bp=1,ap=1.01,t=now.isoformat())}
    track(Store(),Provider(),now)
    assert calls[0][1]['params']=={'on_conflict':'signal_id,quote_at'}
    assert 'ignore-duplicates' in calls[0][1]['prefer']
