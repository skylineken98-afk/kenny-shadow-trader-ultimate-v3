"""Rule-based research agents: no unsupported learning/performance claims."""
from dataclasses import dataclass
@dataclass(frozen=True)
class AgentProfile:
    name:str
    max_risk_fraction:float
    min_rvol:float
    allow_neutral:bool=False
PROFILES={
    'conservative':AgentProfile('conservative',0.005,1.10),
    'balanced':AgentProfile('balanced',0.01,1.00),
    'aggressive':AgentProfile('aggressive',0.02,0.8),
    'challenge':AgentProfile('challenge',0.025,0.8),
    'daily_10pct_research':AgentProfile('daily_10pct_research',0.01,1.0),
}
def evaluate(signal,profile='balanced'):
    a=PROFILES[profile];f=signal.get('frames') or {};short=f.get('5m') or {}
    eligible=signal.get('status')=='SETUP' and float(short.get('rvol',0))>=a.min_rvol
    return {'agent':a.name,'eligible':eligible,'action':'RESEARCH' if eligible else 'WAIT',
            'reason':'Multi-timeframe alignment and RVOL filter' if eligible else 'Conditions not confirmed',
            'risk_fraction':a.max_risk_fraction,'model':'DETERMINISTIC_RULES_NOT_AI','live_orders':False}
