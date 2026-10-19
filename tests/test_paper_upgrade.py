from core.paper_agent import candidate,create_event_from_signal,conservative_bar_exit
from core.research_analytics import summarize_signals,paper_metrics

def signal():
    return {'id':'10cd1a50-29e8-4f25-9157-f044c90c2341','symbol':'SPY','status':'SETUP',
            'side':'BULLISH','entry':100.,'stop':98.,'target':104.,
            'frames':{'5m':{'rvol':1.5}}}
def test_candidate():
    x=candidate(signal(),'balanced');assert x['eligible'];assert x['qty']>0
    assert x['simulation_only']
def test_deterministic_event():
    a=create_event_from_signal(signal(),'balanced')
    b=create_event_from_signal(signal(),'balanced')
    assert a['id']==b['id'] and a['status']=='CANDIDATE_ONLY'
def test_no_shorts():
    s=signal();s.update(side='BEARISH',stop=104.,target=96.)
    assert not candidate(s,'balanced')['eligible']
def test_conservative_intrabar():
    assert conservative_bar_exit('BUY',98,104,{'low':97,'high':105})==('STOP',98)
def test_metrics():
    assert summarize_signals([{'status':'WAIT','symbol':'IWM'}])['rows']==1
    assert paper_metrics([])['win_rate_pct'] is None
