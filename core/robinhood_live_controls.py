"""Broker-independent live-execution safety layer.

Research/development utility. Does NOT submit, authorize, or route real orders.
Reconciliation requires official broker snapshots provided by a separately
approved/authenticated connector. A live order cannot be authorized here.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import hashlib
import json
import sqlite3


class LiveControlError(RuntimeError):
    pass


def _decimal(v):
    try:
        d = Decimal(str(v))
        if not d.is_finite():
            raise InvalidOperation
        return d
    except (InvalidOperation, TypeError, ValueError):
        raise LiveControlError('Invalid finite amount')


@dataclass(frozen=True)
class AllocationPolicy:
    allocation: Decimal = Decimal('100')
    max_new_order: Decimal = Decimal('60')
    max_daily_loss: Decimal = Decimal('5')
    max_open_exposure: Decimal = Decimal('60')

    def __post_init__(self):
        if not (Decimal('0') < self.max_new_order <= self.max_open_exposure <= self.allocation):
            raise LiveControlError('Invalid allocation/exposure caps')
        if not (Decimal('0') < self.max_daily_loss <= self.allocation):
            raise LiveControlError('Invalid daily stop')

    def review(self, *, order_notional, account_buying_power, open_exposure, daily_realized_loss,
               pending_order_notional=0, broker_state_confirmed=False):
        vals = list(map(_decimal, (order_notional, account_buying_power, open_exposure,
                                   daily_realized_loss, pending_order_notional)))
        order, buying_power, exposure, loss, pending = vals
        reasons=[]
        if not broker_state_confirmed: reasons.append('BROKER_STATE_NOT_RECONCILED')
        if any(v < 0 for v in vals): reasons.append('NEGATIVE_INPUT')
        if order <= 0 or order > self.max_new_order: reasons.append('ORDER_CAP')
        if order > buying_power: reasons.append('BUYING_POWER')
        if exposure + pending + order > self.max_open_exposure: reasons.append('EXPOSURE_CAP')
        if loss >= self.max_daily_loss: reasons.append('DAILY_LOSS_LIMIT')
        return {'passes_risk_checks': not reasons, 'reasons': reasons,
                'authorizes_broker_submission': False}


def proposal_key(account_ref, source_signal_id, instrument_id, action):
    if not all(isinstance(x, str) and x.strip() for x in (account_ref, source_signal_id, instrument_id, action)):
        raise LiveControlError('Missing proposal identity')
    return hashlib.sha256(json.dumps([account_ref, source_signal_id, instrument_id, action],
                                     separators=(',', ':')).encode()).hexdigest()


class OrderResearchLedger:
    """Local single-process test ledger ONLY. Hosted deployment must use atomic DB writes.

    Cannot supply an authoritative view of broker positions or permit trading.
    """
    VALID_STATES = {'PROPOSED', 'SUBMITTED_UNCONFIRMED', 'OPEN', 'PARTIALLY_FILLED',
                    'FILLED', 'CANCELLED', 'REJECTED', 'UNKNOWN'}

    def __init__(self, path=':memory:'):
        self.conn=sqlite3.connect(path, isolation_level=None, timeout=15)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('''CREATE TABLE IF NOT EXISTS live_order_research (
            proposal_key TEXT PRIMARY KEY, broker TEXT NOT NULL, account_ref TEXT NOT NULL,
            instrument_id TEXT NOT NULL, proposed_notional TEXT NOT NULL,
            broker_order_id TEXT UNIQUE, state TEXT NOT NULL, last_verified TEXT,
            created_at TEXT NOT NULL)''')

    def propose(self, *, key, broker, account_ref, instrument_id, notional):
        value=_decimal(notional)
        if value <= 0: raise LiveControlError('Nonpositive notional')
        self.conn.execute('INSERT OR IGNORE INTO live_order_research VALUES (?,?,?,?,?,?,?,?,?)',
                          (key, broker, account_ref, instrument_id, str(value), None,
                           'PROPOSED', None, datetime.now(timezone.utc).isoformat()))
        return dict(self.conn.execute('SELECT * FROM live_order_research WHERE proposal_key=?',(key,)).fetchone())

    def reconcile(self, *, key, broker_order_id, broker_state, broker_snapshot_verified=False):
        if not broker_snapshot_verified: raise LiveControlError('Verified broker snapshot required')
        if broker_state not in self.VALID_STATES - {'PROPOSED', 'SUBMITTED_UNCONFIRMED'}:
            raise LiveControlError('Invalid broker state')
        row=self.conn.execute('SELECT * FROM live_order_research WHERE proposal_key=?',(key,)).fetchone()
        if row is None: raise LiveControlError('Unknown proposal')
        if not isinstance(broker_order_id,str) or not broker_order_id.strip():
            raise LiveControlError('Missing broker order id')
        if row['broker_order_id'] and row['broker_order_id'] != broker_order_id:
            raise LiveControlError('Conflicting broker order id')
        self.conn.execute('''UPDATE live_order_research SET broker_order_id=?,state=?,last_verified=?
                             WHERE proposal_key=?''',(broker_order_id,broker_state,
                               datetime.now(timezone.utc).isoformat(),key))
        return dict(self.conn.execute('SELECT * FROM live_order_research WHERE proposal_key=?',(key,)).fetchone())

    def restart_gate(self, broker_open_order_ids, broker_position_ids, *, snapshot_verified=False):
        if not snapshot_verified: return {'safe_to_resume':False,'reason':'BROKER_SNAPSHOT_REQUIRED'}
        rows=self.conn.execute('SELECT broker_order_id,state FROM live_order_research').fetchall()
        unresolved=[r for r in rows if r['state'] in ('SUBMITTED_UNCONFIRMED','UNKNOWN')]
        if unresolved: return {'safe_to_resume':False,'reason':'UNRESOLVED_ORDERS'}
        local_open={r['broker_order_id'] for r in rows if r['state'] in ('OPEN','PARTIALLY_FILLED')}
        if local_open != set(broker_open_order_ids):
            return {'safe_to_resume':False,'reason':'OPEN_ORDER_MISMATCH'}
        # Position matching must be performed by a separate authoritative broker position ledger.
        return {'safe_to_resume':False,'reason':'POSITION_RECONCILIATION_NOT_IMPLEMENTED',
                'broker_position_count':len(broker_position_ids)}

    def close(self): self.conn.close()
