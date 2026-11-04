from datetime import date,datetime,timezone
from types import SimpleNamespace as S
from core.v1_primary_scanner import original_v1_score, bounded_score, snapshot_candidate

def test_original_v1_bonus_can_exceed_100_but_display_cannot():
    raw=original_v1_score(1.,2.,.45,2.)
    assert raw==116
    assert bounded_score(raw)==100
    assert bounded_score(-50)==0

def test_v1_contract_snapshot_quality_and_budget():
    stamp=datetime(2026,10,19,14,0,tzinfo=timezone.utc)
    snap=S(latest_quote=S(bid_price=.97,ask_price=1.,timestamp=stamp),
           latest_trade=S(price=.98),greeks=S(delta=.45))
    row=snapshot_candidate('SPY261019C00700000',snap,100,date(2026,10,19),stamp)
    assert row and row['category']=='0DTE'
    assert row['rank_score']==100 and row['raw_rank_score']>100
    assert snapshot_candidate('SPY261019C00700000',snap,99,date(2026,10,19),stamp) is None
