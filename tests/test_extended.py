from core.agents import evaluate
from core.tracking import evaluate_signal
from core.controls import execution_guard
from core.options import rank_contracts

def test_no_live(): assert not execution_guard('live',True,True,True)['allowed']
def test_agent_wait(): assert evaluate({'status':'WAIT','frames':{}},'aggressive')['action']=='WAIT'
def test_untriggered(): assert evaluate_signal({'entry':100,'stop':95,'target':110,'side':'BULLISH'},[{'high':99,'low':97}])['state']=='UNTRIGGERED'
def test_options_liquidity():assert rank_contracts([{'bid':1,'ask':1.1,'volume':99,'openInterest':200,'strike':100,'expiration':'2026-11-20','right':'call'}],100,200)
