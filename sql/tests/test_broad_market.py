from datetime import datetime, timezone, timedelta
from core.request_signals import rank_row, discover_contracts
from core.market_wide import shortlist

def test_cheap_contract_budget():
    now=datetime(2026,10,19,17,tzinfo=timezone.utc)
    row={'contractSymbol':'TEST261120C00005000','strike':5,'bid':0.08,'ask':0.09,'volume':120,'openInterest':400,'lastTradeDate':now-timedelta(minutes=30)}
    record=rank_row(row,'TEST','2026-11-20','call',5,'BULLISH',10,now)
    assert record is not None and record['cost']==9.0 and record['price_band']=='budget'
    assert rank_row(row,'TEST','2026-11-20','call',5,'BULLISH',5,now) is None

def test_no_fake_contracts_when_no_setup():
    results,_=discover_contracts(['LOW'],5,analyzer=lambda _: {'status':'WAIT','side':'WAIT'},ticker_factory=lambda _: None)
    assert not any(results.values())
