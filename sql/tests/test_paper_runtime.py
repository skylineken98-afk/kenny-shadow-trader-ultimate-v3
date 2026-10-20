from datetime import datetime,timezone
import pytest
from core.paper_runtime import PaperRuntime, PaperRuntimeError

SYMBOL='SOFI261120C00015000'
def q(bid='1.00',ask='1.05'):
    return {'bp':bid,'ap':ask,'t':datetime.now(timezone.utc).isoformat()}

def test_entry_dedup_stop_restart(tmp_path):
    db=str(tmp_path/'paper.db'); p=PaperRuntime(db)
    with pytest.raises(PaperRuntimeError): p.simulate_entry('balanced','sig',SYMBOL,'BULLISH',q())
    p.arm('balanced',paper_only_ack=True)
    first=p.simulate_entry('balanced','sig',SYMBOL,'BULLISH',q())
    assert first['status']=='SIMULATED_OPEN'
    assert p.simulate_entry('balanced','sig',SYMBOL,'BULLISH',q())['status']=='ALREADY_RECORDED'
    p.close()
    p=PaperRuntime(db)
    assert len(p.snapshot('balanced')['positions'])==1
    exits=p.mark_and_exit('balanced',SYMBOL,q('1.40','1.45'))
    assert len(exits)==1 and float(exits[0]['pnl'])>0
    assert not p.mark_and_exit('balanced',SYMBOL,q('1.40','1.45'))
    p.stop('balanced')
    with pytest.raises(PaperRuntimeError):p.simulate_entry('balanced','other',SYMBOL,'BULLISH',q())
    p.close()

def test_put_and_validation(tmp_path):
    p=PaperRuntime(tmp_path/'db.sqlite');p.arm('conservative',paper_only_ack=True)
    put='SOFI261120P00015000'
    assert p.simulate_entry('conservative','bear',put,'BEARISH',q())['status']=='SIMULATED_OPEN'
    with pytest.raises(PaperRuntimeError):p.simulate_entry('conservative','bad',put,'BULLISH',q())
    p.close()
