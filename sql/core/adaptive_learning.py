"""Auditable, opt-in PAPER research learning system; never issues orders.

Uses chronological, filled outcome records. Candidate models are manually promoted.
SQLite is a local development journal, NOT distributed production storage.
"""
from __future__ import annotations
import json, math, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from .research_backtest import evaluate

def _utc(v):
    d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("timezone required")
    return d.astimezone(timezone.utc)

def market_regime(closes, volumes=None):
    """Descriptive simple regime classifier; not a trading signal."""
    xs=[float(x) for x in closes]
    if len(xs)<30 or any(not math.isfinite(x) or x<=0 for x in xs):
        return {"regime":"UNKNOWN","reason":"requires 30 valid closes"}
    returns=[(xs[i]/xs[i-1]-1) for i in range(1,len(xs))]
    recent=returns[-20:]
    vol=pstdev(recent)*(252**.5)
    drift=xs[-1]/xs[-21]-1
    if vol>=.65: mode="HIGH_VOLATILITY"
    elif abs(drift)>.06: mode="UPTREND" if drift>0 else "DOWNTREND"
    else: mode="RANGE_OR_MIXED"
    result={"regime":mode,"annualized_realized_vol":round(vol,6),"twenty_bar_return":round(drift,6)}
    if volumes is not None and len(volumes)>=21:
        v=[float(x) for x in volumes[-21:]]
        if all(math.isfinite(x) and x>=0 for x in v) and mean(v[:-1])>0:
            result["relative_volume_last_bar"]=round(v[-1]/mean(v[:-1]),3)
    return result

class ResearchJournal:
    """Local development store; use persistent Supabase/Postgres in production."""
    def __init__(self,path):
        self.path=str(path)
        self.db=sqlite3.connect(self.path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""CREATE TABLE IF NOT EXISTS model_versions (
          model_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, profile TEXT NOT NULL,
          config_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'CANDIDATE');
          CREATE TABLE IF NOT EXISTS research_observations (
          observation_id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL,
          model_id TEXT NOT NULL, profile TEXT NOT NULL,
          decision_time TEXT NOT NULL, payload_json TEXT NOT NULL,
          FOREIGN KEY(model_id) REFERENCES model_versions(model_id));
          CREATE TABLE IF NOT EXISTS model_reviews (
          review_id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
          champion_id TEXT NOT NULL, challenger_id TEXT NOT NULL,
          evaluation_json TEXT NOT NULL);
        """)
        self.db.commit()
    def close(self): self.db.close()
    def register(self,model_id,profile,config):
        if profile not in ('conservative','balanced','aggressive','challenge','daily_10pct_research'):
            raise ValueError('Unsupported research profile')
        if not isinstance(config,dict):raise ValueError('Config must be object')
        self.db.execute('INSERT INTO model_versions(model_id,created_at,profile,config_json) VALUES (?,?,?,?)',
          (model_id,datetime.now(timezone.utc).isoformat(),profile,json.dumps(config,sort_keys=True)))
        self.db.commit()
    def record(self,observation_id,model_id,profile,observation):
        # Store complete feature/decision/outcome provenance, never secrets.
        if not isinstance(observation,dict):raise ValueError('Observation must be object')
        _utc(observation['decision_time']);_utc(observation['feature_available_at'])
        if _utc(observation['feature_available_at'])>_utc(observation['decision_time']):
            raise ValueError('Future data unavailable at decision time')
        if any(k.lower() in {'api_key','token','password','secret'} for k in observation):
            raise ValueError('Refuse credential fields')
        self.db.execute('INSERT INTO research_observations VALUES (?,?,?,?,?,?)',
          (observation_id,datetime.now(timezone.utc).isoformat(),model_id,profile,
           observation['decision_time'],json.dumps(observation,sort_keys=True)))
        self.db.commit()
    def history(self,model_id):
        return [json.loads(row[0]) for row in self.db.execute(
            'SELECT payload_json FROM research_observations WHERE model_id=? ORDER BY decision_time,observation_id',
            (model_id,))]
    def scorecard(self,model_id):
        rows=self.history(model_id)
        stats=evaluate(rows)
        return {'model_id':model_id,'observations':len(rows),**stats}
    def review(self,champion_id,challenger_id,min_test_trades=30):
        if champion_id==challenger_id:raise ValueError('Need two models')
        a=self.history(champion_id);b=self.history(challenger_id)
        # Strict chronological held-out last 30%, no auto-promotion.
        from .v3_model_validation import time_split
        asplit=time_split(a);bsplit=time_split(b)
        if asplit['status']!='SPLIT' or bsplit['status']!='SPLIT':
            verdict={'status':'INSUFFICIENT_DATA','candidate_for_manual_review':False,'automatic_promotion':False}
        else:
            aeval=evaluate(asplit['test']);beval=evaluate(bsplit['test'])
            enough=min(aeval['count'],beval['count'])>=min_test_trades
            better=(aeval['expectancy_pct'] is not None and beval['expectancy_pct'] is not None
                    and beval['expectancy_pct']>aeval['expectancy_pct'])
            verdict={'status':'REVIEW_READY' if enough else 'INSUFFICIENT_VERIFIED_HOLDOUT',
                     'champion_test':aeval,'challenger_test':beval,
                     'candidate_for_manual_review':bool(enough and better),
                     'automatic_promotion':False,
                     'warning':'Not evidence of profitability. Check costs, drawdowns, clustering, multiple testing and forward paper results.'}
        self.db.execute('INSERT INTO model_reviews(recorded_at,champion_id,challenger_id,evaluation_json) VALUES (?,?,?,?)',
            (datetime.now(timezone.utc).isoformat(),champion_id,challenger_id,json.dumps(verdict)))
        self.db.commit()
        return verdict
