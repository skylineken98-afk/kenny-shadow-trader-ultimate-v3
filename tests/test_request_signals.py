from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from core.request_signals import dte_group, rank_row, discover_contracts

NOW=datetime(2026,10,19,17,0,tzinfo=timezone.utc)
def item(ticker, expiration, put=False):
    return {'contractSymbol':ticker+'261019C00700000'+('P' if put else ''),'strike':700,'bid':2.9,'ask':3.1,'lastPrice':3.05,'percentChange':4.0,
            'volume':120,'openInterest':1200,'lastTradeDate':NOW-timedelta(hours=1)}

def test_expiry_categories():
    from datetime import date
    today=date(2026,10,19)
    assert dte_group('2026-10-19',today)=='0DTE'
    assert dte_group('2026-11-20',today)=='Swings'
    assert dte_group('2028-01-21',today)=='LEAPS'
    assert dte_group('2026-10-20',today) is None

def test_reject_bad_or_stale_quote():
    r=item('SPY','2026-10-19')
    assert rank_row(r,'SPY','2026-10-19','call',700,'BULLISH',500,NOW)
    assert rank_row(r,'SPY','2026-10-19','put',700,'BULLISH',500,NOW) is None
    assert rank_row(r,'SPY','2026-10-19','call',700,'BULLISH',200,NOW) is None
    assert rank_row({**r,'lastTradeDate':NOW-timedelta(days=6)},'SPY','2026-10-19','call',700,'BULLISH',500,NOW) is None

class Frame:
    def __init__(self,rows):self.rows=rows
    def to_dict(self,arg):return self.rows
class Ticker:
    options=['2026-10-19','2026-11-20','2028-01-21']
    def option_chain(self,exp):return SimpleNamespace(calls=Frame([item('SPY',exp)]),puts=Frame([]))
def analyzer(symbol):return {'status':'SETUP','side':'BULLISH','frames':{'5m':{'price':700}}}
def test_all_three_buckets_with_real_vendor_rows_mocked():
    results,notes=discover_contracts(['SPY'],500,now=NOW,ticker_factory=lambda s:Ticker(),analyzer=analyzer)
    assert all(len(results[c])==1 for c in results)
    assert all(results[c][0]['contract'].startswith('SPY') for c in results)

def test_no_technical_alignment_means_no_contracts():
    results,_=discover_contracts(['SPY'],500,now=NOW,ticker_factory=lambda s:Ticker(),analyzer=lambda s:{'status':'WAIT','side':'WAIT'})
    assert all(not rows for rows in results.values())
