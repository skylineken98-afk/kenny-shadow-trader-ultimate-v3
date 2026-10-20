"""Mandatory approvals. No trade execution or public vendor redistribution here."""
from .v3_readiness import REQUIREMENTS

GATES={
 'paper_scanning':('market_scanner','supabase_journal'),
 'paper_agent_challenges':('paper_agents','supabase_journal'),
 'model_promotion':('ai_training',),
 'live_broker':('broker_execution','paper_agents','supabase_journal'),
 'paid_memberships':('memberships',),
 'public_uw_data':('unusual_whales','public_launch'),
 'public_release':('public_launch','memberships','live_charts','market_scanner'),
}
def allowed(feature, evidence=None, *, explicit_approval=False):
 if feature not in GATES:raise ValueError('Unknown feature')
 verified=evidence or {}
 lacking=[name for name in GATES[feature] if verified.get(name) is not True]
 if not explicit_approval:return {'allowed':False,'missing':lacking,'reason':'Explicit approval required'}
 return {'allowed':not lacking,'missing':lacking,'reason':'Verified gates met' if not lacking else 'Verification incomplete'}
