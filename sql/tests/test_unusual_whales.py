import pytest
from unittest.mock import Mock
from core import unusual_whales as u

def test_connection(monkeypatch):
    monkeypatch.setenv('UNUSUAL_WHALES_API_KEY','fake-secret')
    sess=Mock();resp=Mock(status_code=200);resp.json.return_value={'data':[{'ticker':'SPY'}]};sess.get.return_value=resp
    assert u.connection_check(sess)=={'connected':True,'records_returned':1}
    args,kw=sess.get.call_args
    assert args[0]=='https://api.unusualwhales.com/api/option-trades/flow-alerts'
    assert kw['headers']['Authorization']=='Bearer fake-secret'

def test_missing(monkeypatch):
    monkeypatch.delenv('UNUSUAL_WHALES_API_KEY',raising=False)
    assert not u.connection_check()['connected']

def test_denied(monkeypatch):
    monkeypatch.setenv('UNUSUAL_WHALES_API_KEY','fake-secret')
    sess=Mock();sess.get.return_value=Mock(status_code=403)
    out=u.connection_check(sess)
    assert not out['connected'] and 'fake-secret' not in str(out)

def test_rejects_bad_input(monkeypatch):
    monkeypatch.setenv('UNUSUAL_WHALES_API_KEY','fake-secret')
    with pytest.raises(ValueError):u.darkpool('../SPY')
    with pytest.raises(ValueError):u.flow_alerts(201)
    with pytest.raises(ValueError):u._request('https://evil.example')

def test_paths(monkeypatch):
    monkeypatch.setenv('UNUSUAL_WHALES_API_KEY','fake-secret')
    got=[]
    monkeypatch.setattr(u,'_request',lambda path,params=None,session=None:got.append(path))
    u.stock_flow('spy');u.greek_exposure('QQQ');u.darkpool('iwm');u.congressional_trades()
    assert got==['/api/stock/SPY/flow-recent','/api/stock/QQQ/greek-exposure','/api/darkpool/IWM','/api/congress/recent-trades']
