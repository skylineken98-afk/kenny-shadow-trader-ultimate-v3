"""Fail-closed, read-only signal -> simulated order processor.

This module NEVER calls a brokerage. It requires actual option-premium quotes for
option simulation; underlying levels cannot be substituted for option levels.
The database must enforce unique (agent, source_signal_id, symbol); workers should
use a singleton scheduler (not multiple concurrent Railway replicas).
"""
import logging
import os
from decimal import Decimal
from core.agents import PROFILES
from core.db import client
from core.paper_lifecycle import PaperAccount, enter, close_trade, PaperRiskError

LOG = logging.getLogger(__name__)

class WorkerError(RuntimeError):
    pass


def _enabled():
    return os.getenv('V3_PAPER_AUTOMATION_ENABLED', 'false').lower() == 'true'


def _db():
    try:
        return client()
    except Exception as exc:
        raise WorkerError('Database unavailable: fail closed') from exc


def _one(table, **filters):
    q = _db().table(table).select('*')
    for k, v in filters.items():
        q = q.eq(k, v)
    records = q.limit(2).execute().data or []
    return records[0] if len(records) == 1 else None


def _record(table, payload):
    return _db().table(table).insert(payload).execute()


def simulate_signal(signal_id, agent, premium_quote):
    """One idempotent simulation attempt. premium_quote is explicit contract data.

    Caller must source fresh and trusted option quotes. Worker never assumes
    a stock's OHLC represents an option premium. No automatic eligibility bypass.
    """
    if not _enabled():
        raise WorkerError('Paper automation disabled')
    if agent not in PROFILES:
        raise WorkerError('Unknown agent')
    signal = _one('ultimate_signals', id=signal_id)
    if not signal or signal.get('status') != 'SETUP':
        raise WorkerError('No eligible stored setup')
    acct = _one('v3_paper_accounts', agent=agent)
    if not acct or acct.get('killed') is not False:
        raise WorkerError('Account missing or emergency stop enabled')
    if not premium_quote or premium_quote.get('source_signal_id') != str(signal_id):
        raise WorkerError('Missing matched verified instrument quote')
    required = ('option_symbol','asset','direction','ask','entry','stop','target','quote_timestamp')
    if not all(premium_quote.get(k) is not None for k in required):
        raise WorkerError('Incomplete contract premium data')
    if premium_quote['asset'] not in ('call','put'):
        raise WorkerError('Options contract only')
    if premium_quote['direction'] != signal.get('side'):
        raise WorkerError('Mismatch with underlying signal direction')
    symbol = str(premium_quote['option_symbol'])
    if not symbol or symbol == signal.get('symbol'):
        raise WorkerError('Expected a distinct OCC option symbol')
    # Fail closed for stale or future-dated quotes.
    from datetime import datetime, timezone
    try:
        stamp = datetime.fromisoformat(str(premium_quote['quote_timestamp']).replace('Z', '+00:00'))
        if stamp.tzinfo is None or not (0 <= (datetime.now(timezone.utc) - stamp).total_seconds() <= 60):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise WorkerError('Quote older than 60 seconds or invalid timestamp') from exc
    if _one('v3_paper_orders', agent=agent, source_signal_id=str(signal_id), symbol=symbol):
        return {'status':'ALREADY_RECORDED', 'agent':agent, 'symbol':symbol}
    account = PaperAccount(agent, Decimal(str(acct['equity'])), Decimal(str(acct['day_start_equity'])),
                           Decimal(str(acct.get('open_cost') or 0)), bool(acct['killed']))
    try:
        trade = enter(account, signal_id=signal_id, symbol=symbol, asset=premium_quote['asset'],
                      direction=premium_quote['direction'], entry=premium_quote['entry'],
                      stop=premium_quote['stop'], target=premium_quote['target'],
                      ask=premium_quote['ask'], quantity=1)
    except PaperRiskError as exc:
        return {'status':'REJECTED','reason':str(exc),'agent':agent,'symbol':symbol}
    # Database unique constraint is final deduplication boundary. The persistent
    # account balance and position exposure must be maintained by a later atomic
    # database procedure before multi-process scheduling is enabled.
    payload = {'agent':agent, 'source_signal_id':str(signal_id), 'symbol':symbol,
               'asset':premium_quote['asset'],'direction':premium_quote['direction'],
               'state':'SIMULATED_OPEN','detail':{**trade,'quote_timestamp':premium_quote['quote_timestamp']},
               'simulation_only':True}
    try:
        _record('v3_paper_orders',payload)
    except Exception as exc:
        raise WorkerError('Order record failed; no fill can be claimed') from exc
    return {'status':'SIMULATED_OPEN','agent':agent,'symbol':symbol,'simulation_only':True}


def request_emergency_stop(agent):
    """Stop future research paper entries. Live brokerage control is not affected."""
    if agent not in PROFILES: raise WorkerError('Unknown agent')
    result = _db().table('v3_paper_accounts').update({'killed':True}).eq('agent',agent).execute()
    if not result.data: raise WorkerError('Emergency stop not confirmed')
    _record('v3_paper_audit',{'agent':agent,'event':'PAPER_STOP_ENABLED','detail':{'source':'dashboard'}})
    return True
