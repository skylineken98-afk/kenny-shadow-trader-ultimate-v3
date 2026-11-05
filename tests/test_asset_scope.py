from core.asset_scope import in_scope_symbol
from core.settings import symbols
from core.paper import open_paper_trade
from core.strategy_discovery import THEMES


def test_symbol_allow_policy(monkeypatch):
    monkeypatch.setenv('SCAN_SYMBOLS', 'SPX,SPY,QQQ,BTC-USD,ETH-USD,EURUSD=X,NQ=F,^GSPC,ES=F, AAPL, SPY')
    assert symbols() == ['SPX', 'SPY', 'QQQ', 'BTC-USD', 'ETH-USD', 'AAPL']
    assert in_scope_symbol('SOL-USD')
    assert not in_scope_symbol('EURUSD=X')
    assert not in_scope_symbol('NQ=F')


def test_removed_assets_rejected_before_db():
    for asset in ('forex', 'future'):
        result = open_paper_trade('NQ=F', asset, 'BUY', 100, 98, 104)
        assert result['ok'] is False


def test_research_catalog_has_no_fx():
    assert 'crypto' in THEMES
    assert 'crypto_forex' not in THEMES
    assert not any('FX ' in theme for names in THEMES.values() for theme in names)
