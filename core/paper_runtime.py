"""Durable single-file SQLite paper research engine (NOT broker execution).

For local development only. Railway containers can have ephemeral disks; use a
transactional hosted database before deploying multiple replicas.
"""
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from core.agents import PROFILES
from core.paper_lifecycle import PaperAccount, enter, close_trade, PaperRiskError
from core.alpaca_option_quotes import OCC, validate_quote

class PaperRuntimeError(ValueError): pass

def utcnow(): return datetime.now(timezone.utc).isoformat()

class PaperRuntime:
    def __init__(self, path):
        self.path=str(path)
        self.db=sqlite3.connect(self.path, timeout=15, isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=15000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS accounts(agent TEXT PRIMARY KEY, cash TEXT NOT NULL, equity TEXT NOT NULL, day_start_equity TEXT NOT NULL, killed INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS positions(id INTEGER PRIMARY KEY AUTOINCREMENT,agent TEXT NOT NULL, signal_id TEXT NOT NULL, symbol TEXT NOT NULL, state TEXT NOT NULL, entry_json TEXT NOT NULL, opened_at TEXT NOT NULL,closed_at TEXT,exit_json TEXT, UNIQUE(agent,signal_id,symbol));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, event TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        for agent in PROFILES:
            self.db.execute('INSERT OR IGNORE INTO accounts VALUES(?,?,?,?,?)',(agent,'10000','10000','10000',1))

    def _transaction(self, fn):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result=fn()
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def audit(self, agent,event,payload):
        self.db.execute('INSERT INTO events(agent,event,payload,created_at) VALUES(?,?,?,?)',(agent,event,json.dumps(payload,sort_keys=True),utcnow()))

    def stop(self, agent):
        if agent not in PROFILES:raise PaperRuntimeError('Unknown agent')
        def op():
            self.db.execute('UPDATE accounts SET killed=1 WHERE agent=?',(agent,))
            self.audit(agent,'KILL_SWITCH_ENABLED',{})
        self._transaction(op)

    def arm(self, agent, *, paper_only_ack=False):
        if agent not in PROFILES or paper_only_ack is not True:raise PaperRuntimeError('Explicit paper-only acknowledgement required')
        def op():
            self.db.execute('UPDATE accounts SET killed=0 WHERE agent=?',(agent,))
            self.audit(agent,'PAPER_ARMED',{})
        self._transaction(op)

    def snapshot(self,agent):
        if agent not in PROFILES: raise PaperRuntimeError('Unknown agent')
        acc=dict(self.db.execute('SELECT * FROM accounts WHERE agent=?',(agent,)).fetchone())
        positions=[dict(x) for x in self.db.execute('SELECT * FROM positions WHERE agent=? ORDER BY id DESC',(agent,))]
        return {'account':acc,'positions':positions}

    def simulate_entry(self,agent,signal_id,symbol, direction,quote,*,stop_fraction=Decimal('.20'),target_fraction=Decimal('.30')):
        """Conservative ask-priced assumed fill; option-premium risk only.
        Quote must contain OCC symbol, bid/ask/time. Direction controls call/put.
        """
        if agent not in PROFILES or not signal_id or not OCC.fullmatch(str(symbol)):raise PaperRuntimeError('Invalid agent, signal or option OCC symbol')
        expected='C' if direction=='BULLISH' else 'P' if direction=='BEARISH' else None
        if not expected or symbol[-9]!=expected:raise PaperRuntimeError('Contract option right does not match direction')
        validated=validate_quote(symbol,quote)
        ask=Decimal(validated['ask'])
        def op():
            row=self.db.execute('SELECT * FROM accounts WHERE agent=?',(agent,)).fetchone()
            if row['killed']:raise PaperRuntimeError('Paper agent stopped')
            old=self.db.execute('SELECT id FROM positions WHERE agent=? AND signal_id=? AND symbol=?',(agent,str(signal_id),symbol)).fetchone()
            if old:return {'status':'ALREADY_RECORDED','position_id':old['id']}
            exposure=sum(Decimal(json.loads(x['entry_json'])['cost']) for x in self.db.execute("SELECT entry_json FROM positions WHERE agent=? AND state='SIMULATED_OPEN'",(agent,)))
            account=PaperAccount(agent,Decimal(row['equity']),Decimal(row['day_start_equity']),exposure,False)
            try:
                trade=enter(account,signal_id=signal_id,symbol=symbol,asset='call' if expected=='C' else 'put',direction=direction,
                    entry=ask,stop=ask*(1-Decimal(str(stop_fraction))),target=ask*(1+Decimal(str(target_fraction))),ask=ask)
            except PaperRiskError as exc: return {'status':'REJECTED','reason':str(exc)}
            # Mark as reserved cash; net liquidation equity stays unchanged until revalued.
            cash=Decimal(row['cash'])-Decimal(trade['cost'])
            if cash<0:return {'status':'REJECTED','reason':'insufficient available cash'}
            self.db.execute('UPDATE accounts SET cash=? WHERE agent=?',(str(cash),agent))
            cursor=self.db.execute('INSERT INTO positions(agent,signal_id,symbol,state,entry_json,opened_at) VALUES(?,?,?,?,?,?)',
                (agent,str(signal_id),symbol,'SIMULATED_OPEN',json.dumps(trade),utcnow()))
            self.audit(agent,'SIMULATED_ENTRY',{'id':cursor.lastrowid,'symbol':symbol,'quote_timestamp':validated['quote_timestamp']})
            return {'status':'SIMULATED_OPEN','position_id':cursor.lastrowid,'simulation_only':True}
        return self._transaction(op)

    def mark_and_exit(self,agent,symbol,quote,*,force_exit=False):
        """Close at available BID when a contract premium stop/target is crossed.
        No intrabar fills or guaranteed stop prices. Stale quotes fail closed.
        """
        validated=validate_quote(symbol,quote)
        bid=Decimal(validated['bid'])
        def op():
            rows=self.db.execute("SELECT * FROM positions WHERE agent=? AND symbol=? AND state='SIMULATED_OPEN'",(agent,symbol)).fetchall()
            results=[]
            for row in rows:
                trade=json.loads(row['entry_json'])
                stop,target=Decimal(trade['stop']),Decimal(trade['target'])
                if not(force_exit or bid<=stop or bid>=target): continue
                exit_result=close_trade(trade,bid=bid)
                exit_result['exit_reason']='FORCED' if force_exit else 'STOP' if bid<=stop else 'TARGET'
                account=self.db.execute('SELECT * FROM accounts WHERE agent=?',(agent,)).fetchone()
                proceeds=bid*int(trade['quantity'])*int(trade['multiplier'])
                cash=Decimal(account['cash'])+proceeds
                equity=Decimal(account['equity'])+Decimal(exit_result['realized_pnl'])
                self.db.execute('UPDATE accounts SET cash=?,equity=? WHERE agent=?',(str(cash),str(equity),agent))
                self.db.execute("UPDATE positions SET state='CLOSED',exit_json=?,closed_at=? WHERE id=?",(json.dumps(exit_result),utcnow(),row['id']))
                self.audit(agent,'SIMULATED_EXIT',{'id':row['id'],'pnl':exit_result['realized_pnl'],'reason':exit_result['exit_reason']})
                results.append({'id':row['id'],'pnl':exit_result['realized_pnl'],'reason':exit_result['exit_reason']})
            return results
        return self._transaction(op)

    def close(self):self.db.close()
