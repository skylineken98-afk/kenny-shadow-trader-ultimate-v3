import sqlite3
from pathlib import Path
from config import DB_PATH

def connect():
    Path(DB_PATH).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DB_PATH,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute("""CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY AUTOINCREMENT,ticker TEXT,created_at TEXT,direction TEXT,entry REAL,stop REAL,target REAL,status TEXT DEFAULT 'PROPOSED',source TEXT,UNIQUE(ticker,created_at))""")
    db.execute("""CREATE TABLE IF NOT EXISTS paper_trades(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,ticker TEXT,side TEXT,quantity REAL,entry REAL,exit REAL,closed_at TEXT,fee REAL DEFAULT 0,notes TEXT)""")
    db.commit();return db

def record_signal(s):
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO signals(ticker,created_at,direction,entry,stop,target,source) VALUES(?,?,?,?,?,?,?)',(s['ticker'],s['asof'],s['direction'],s['entry'],s['stop'],s['target'],s['source']))

def recent_signals(limit=250):
    with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM signals ORDER BY id DESC LIMIT ?',(limit,))]

def paper_open(ticker,side,qty,price,at,notes=''):
    with connect() as c:c.execute('INSERT INTO paper_trades(created_at,ticker,side,quantity,entry,notes) VALUES (?,?,?,?,?,?)',(at,ticker,side,qty,price,notes))

def paper_close(trade_id,price,at,fee=0):
    with connect() as c:c.execute('UPDATE paper_trades SET exit=?,closed_at=?,fee=? WHERE id=? AND exit IS NULL',(price,at,fee,trade_id))

def paper_list():
    with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM paper_trades ORDER BY id DESC LIMIT 500')]
