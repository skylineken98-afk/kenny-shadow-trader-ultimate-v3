"""Fail-closed feature readiness: configuration is not proof of integration health."""
import os
from dataclasses import dataclass

REQUIREMENTS = {
 'unusual_whales': ('UNUSUAL_WHALES_API_KEY',),
 'historical_lake': ('UNUSUAL_WHALES_API_KEY','UW_HISTORY_PATH'),
 'earnings_iv': ('UNUSUAL_WHALES_API_KEY','UW_EARNINGS_PATH'),
 'institutional_13f': ('UNUSUAL_WHALES_API_KEY','UW_INSTITUTIONAL_13F_PATH'),
 'supabase_journal': ('SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY'),
 'telegram': ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'),
 'market_scanner': (), 'live_charts': (), 'paper_agents': (),
 'ai_training': (), 'broker_execution': (), 'memberships': (), 'public_launch': (),
}
# Tests executed off-platform cannot establish production-ready capabilities.
NEEDS_VERIFICATION = {
 'unusual_whales':'Authenticated endpoint and licensed entitlements',
 'historical_lake':'History endpoint, retention and usage rights',
 'earnings_iv':'Earnings/IV endpoint and sufficient history',
 'institutional_13f':'13F endpoint coverage and delayed-filing timestamps',
 'supabase_journal':'Database migration and authenticated insert/read',
 'telegram':'Send an opt-in test notification',
 'market_scanner':'Market-wide rotation, scans/hour, completeness and data ages',
 'live_charts':'Intraday/daily candles and level calculation validity',
 'paper_agents':'Persistent fills, fees, positions, challenge restarts',
 'ai_training':'Out-of-sample comparisons and promotion approval',
 'broker_execution':'Broker authorization, idempotency, reconciliation and kill switch',
 'memberships':'Identity, webhooks, payment provider and access audit',
 'public_launch':'Commercial data licensing, penetration review, monitoring and rollback',
}
def audit(environ=None):
 env=os.environ if environ is None else environ
 return {name:{'credentials_present':all(bool(env.get(k)) for k in keys),
               'missing_variables':[k for k in keys if not env.get(k)],
               'status':'NOT_LIVE_VERIFIED', 'next_verification':NEEDS_VERIFICATION[name]}
         for name,keys in REQUIREMENTS.items()}
