from datetime import datetime,timezone,timedelta
from core.scanner_contract_suggestions import match_signal_contracts

NOW=datetime(2026,11,5,20,0,tzinfo=timezone.utc)
def ts(m):return (NOW-timedelta(minutes=m)).isoformat()
def s(symbol="AAPL",side="BULLISH",status="SETUP",mins=2):
 return {"symbol":symbol,"side":side,"status":status,"created_at":ts(mins),"entry":350,"stop":348,"target":354}
def c(symbol="AAPL",typ="CALL",ask=4.99,score=90,mins=2,context="BULLISH_SETUP_ALIGNED"):
 return {"underlying":symbol,"option_type":typ,"entry_ask":ask,"entry_bid":round(ask-.05,2),
  "score":score,"quote_at":ts(mins),"context_label":context,"quality_label":"QUALIFIED",
  "state":"OPEN","contract":symbol+typ+str(score),"strike":350,"expiration":"2026-11-13","feed":"indicative"}

def test_selects_best_under_500():
 rows=match_signal_contracts([s()],[c(ask=5.01,score=99),c(ask=4.99,score=90),c(ask=1.5,score=80)],NOW)
 assert len(rows)==1 and rows[0]["suggestion"]["score"]==90 and rows[0]["premium_cost"]==499

def test_rejects_wrong_direction_and_stale_quotes():
 rows=match_signal_contracts([s()],[c(typ="PUT"),c(mins=40)],NOW)
 assert rows[0]["suggestion"] is None

def test_latest_signal_controls_direction_not_old_setup():
 rows=match_signal_contracts([s(mins=5),s(status="WAIT",side="WAIT",mins=1)],[c()],NOW)
 assert rows[0]["suggestion"] is None and rows[0]["status"]=="WAIT"

def test_bearish_puts_and_multiple_symbols():
 rows=match_signal_contracts([s("AAPL"),s("XOM",side="BEARISH")],
 [c("AAPL"),c("XOM",typ="PUT",context="BEARISH_SETUP_ALIGNED")],NOW)
 assert {r["symbol"] for r in rows if r["suggestion"]}=={"AAPL","XOM"}

def test_never_fabricates_stale_missing_prices():
 rows=match_signal_contracts([s("NVDA")],[],NOW)
 assert rows[0]["suggestion"] is None and rows[0]["premium_cost"] is None
