from datetime import datetime, timezone, timedelta
import pytest
from core.alpaca_option_quotes import QuoteError, validate_quote, AlpacaOptionQuoteReader
S='AAPL271217C00150000'
NOW=datetime(2026,10,19,20,0,tzinfo=timezone.utc)
def q(**kwargs):
    return dict({'bp': '1.00','ap': '1.10','t': NOW.isoformat()},**kwargs)
def test_valid():
    assert validate_quote(S,q(),now=NOW)['ask']=='1.10'
def test_stale():
    with pytest.raises(QuoteError,match='Stale'):
        validate_quote(S,q(t=(NOW-timedelta(minutes=4)).isoformat()),now=NOW)
def test_future():
    with pytest.raises(QuoteError,match='Stale'):
        validate_quote(S,q(t=(NOW+timedelta(minutes=1)).isoformat()),now=NOW)
def test_bad_spread():
    with pytest.raises(QuoteError,match='Spread'):
        validate_quote(S,q(bp='.20'),now=NOW)
def test_wrong_symbol():
    with pytest.raises(QuoteError):
        validate_quote('AAPL',q(),now=NOW)
def test_reject_indicative_feed():
    with pytest.raises(QuoteError,match='OPRA'):
        AlpacaOptionQuoteReader(key='x',secret='y',feed='indicative')
class Session:
    def get(self,url,params,headers,timeout):
        assert params['feed']=='opra'
        class Response:
            def raise_for_status(self): pass
            def json(self): return {'quotes': {S:q()}}
        return Response()
def test_reader(monkeypatch):
    import core.alpaca_option_quotes as mod
    monkeypatch.setattr(mod,'validate_quote',lambda symbol,item: {'symbol':symbol})
    assert AlpacaOptionQuoteReader(key='x',secret='y',session=Session()).latest([S]) == {S:{'symbol':S}}
