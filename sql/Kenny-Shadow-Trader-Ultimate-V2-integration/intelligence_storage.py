"""Local SQLite prototype store: persistent only when deployment has a persistent disk."""
import json
import sqlite3
from pathlib import Path
from config import DB_PATH

def dbconnect():
    p=Path(DB_PATH);p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(p,timeout=20);c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=20000')
    c.execute("""CREATE TABLE IF NOT EXISTS news_items (
      id TEXT PRIMARY KEY,source TEXT NOT NULL,headline TEXT NOT NULL,summary TEXT,
      article_url TEXT NOT NULL,published_at TEXT,seen_at TEXT,
      impact_score INTEGER,assets_json TEXT,status TEXT,analysis TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS legacy_signal_archive (
      source_row_id TEXT PRIMARY KEY, contract TEXT,underlying TEXT,option_type TEXT,
      strike TEXT,expiration TEXT,created_at TEXT,entry_price TEXT,current_price TEXT,
      stop_loss TEXT,target_1 TEXT,target_2 TEXT,score TEXT,scanned_at TEXT)""")
    c.commit();return c

def upsert_news(items):
    added=0
    with dbconnect() as db:
        for a in items:
            cur=db.execute("""INSERT OR IGNORE INTO news_items
              (id,source,headline,summary,article_url,published_at,seen_at,impact_score,assets_json,status,analysis)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (a['id'],a['source'],a['headline'],a['summary'],a['article_url'],a['published_at'],a['seen_at'],a['impact_score'],json.dumps(a['assets']),a['status'],a['analysis']))
            added+=cur.rowcount
    return added

def recent_news(limit=100):
    with dbconnect() as db:
        rows=[dict(r) for r in db.execute('SELECT * FROM news_items ORDER BY impact_score DESC,seen_at DESC LIMIT ?', (limit,))]
    for row in rows:row['assets']=json.loads(row.pop('assets_json') or '[]')
    return rows

def archive_csv(path):
    import csv
    n=0
    with open(path,newline='',encoding='utf-8-sig') as f,dbconnect() as db:
        for row in csv.DictReader(f):
            vals=[row.get(k,'') for k in ('id','contract','underlying','option_type','strike','expiration','created_at','entry_price','current_price','stop_loss','target_1','target_2','score','scanned_at')]
            if not vals[0]:continue
            n+=db.execute('INSERT OR IGNORE INTO legacy_signal_archive VALUES ('+','.join('?' for _ in vals)+')',vals).rowcount
    return n
