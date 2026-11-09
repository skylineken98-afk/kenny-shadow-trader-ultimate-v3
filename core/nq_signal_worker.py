"""Optional independent data-feed polling and read-only alert publication.

Required data endpoint contract: GET <KST_NQ_DATA_URL>?symbol=NQ or MNQ
returns {"symbol":"NQ","bars":[{"timestamp":"...Z","open":...,
"high":...,"low":...,"close":...,"volume":...}, ...]}.
Use a licensed CME feed. This module NEVER sends requests to a broker.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.nq_signal_alerts import evaluate, signal_message, signal_payload

def http_json(url, data=None, headers=None, timeout=10):
    h = {"Accept": "application/json", **(headers or {})}
    payload = json.dumps(data).encode() if data is not None else None
    if payload is not None:
        h["Content-Type"] = "application/json"
    with urlopen(Request(url, payload, headers=h), timeout=timeout) as resp:
        return json.load(resp)

def init_db(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS nq_alert_outbox (
        signal_id TEXT NOT NULL, channel TEXT NOT NULL,
        payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0,
        error TEXT, created_at TEXT NOT NULL,
        PRIMARY KEY(signal_id, channel))""")
    connection.commit()

def enqueue(connection, signal, channels):
    payload = json.dumps(signal_payload(signal), sort_keys=True)
    for channel in channels:
        connection.execute(
            "INSERT OR IGNORE INTO nq_alert_outbox(signal_id,channel,payload,created_at) VALUES(?,?,?,?)",
            (signal.id, channel, payload, datetime.now(timezone.utc).isoformat()))
    connection.commit()

def deliver(connection, *, telegram_token=None, telegram_chat_id=None,
            supabase_url=None, supabase_key=None):
    pending = connection.execute(
        "SELECT signal_id,channel,payload FROM nq_alert_outbox WHERE sent=0 ORDER BY created_at LIMIT 100").fetchall()
    for signal_id, channel, raw in pending:
        item = json.loads(raw)
        try:
            if channel == "telegram":
                if not telegram_token or not telegram_chat_id:
                    continue
                from types import SimpleNamespace
                message = signal_message(SimpleNamespace(**item))
                result = http_json(
                    "https://api.telegram.org/bot" + telegram_token + "/sendMessage",
                    {"chat_id": telegram_chat_id, "text": message, "disable_web_page_preview": True})
                if not result.get("ok"):
                    raise RuntimeError("Telegram delivery not acknowledged")
            elif channel == "website":
                if not supabase_url or not supabase_key:
                    continue
                # Insert-only with signal_id unique, allowing safe retries.
                http_json(supabase_url.rstrip("/") + "/rest/v1/kst_nq_alerts",
                          {"signal_id": signal_id, "payload": item,
                           "created_at": item["decision_at"]},
                          {"apikey": supabase_key,
                           "Authorization": "Bearer " + supabase_key,
                           "Prefer": "resolution=ignore-duplicates,return=minimal"})
            else:
                raise ValueError("Unsupported channel")
            connection.execute("UPDATE nq_alert_outbox SET sent=1,error=NULL WHERE signal_id=? AND channel=?",
                               (signal_id, channel))
        except Exception as exc:
            # Do not persist credentials or request URL containing the Telegram token.
            connection.execute("UPDATE nq_alert_outbox SET error=? WHERE signal_id=? AND channel=?",
                               (type(exc).__name__, signal_id, channel))
        connection.commit()

def fetch_bars(base_url, symbol, token=None):
    if not base_url.startswith("https://"):
        raise ValueError("Market data endpoint must use HTTPS")
    separator = "&" if "?" in base_url else "?"
    headers = {"Authorization": "Bearer " + token} if token else {}
    response = http_json(base_url + separator + urlencode({"symbol": symbol}), headers=headers)
    if response.get("symbol") != symbol or not isinstance(response.get("bars"), list):
        raise ValueError("Provider symbol or bars mismatch")
    return response["bars"]

def run_once(connection, config, now=None):
    if not config.get("KST_NQ_DATA_URL"):
        return {"status": "NO_LIVE_FEED", "alerts": 0}
    count = 0
    for symbol in ("NQ", "MNQ"):
        try:
            bars = fetch_bars(config["KST_NQ_DATA_URL"], symbol, config.get("KST_NQ_DATA_TOKEN"))
            signal = evaluate(symbol, bars, now=now)
            if signal:
                enqueue(connection, signal, ("telegram", "website"))
                count += 1
        except (ValueError, KeyError, OSError, TimeoutError) as exc:
            # A bad/stale feed must never generate a synthetic alert.
            print(json.dumps({"symbol": symbol, "status": "DATA_UNAVAILABLE",
                              "error_type": type(exc).__name__}), flush=True)
    deliver(connection, telegram_token=config.get("KST_NQ_TELEGRAM_TOKEN"),
            telegram_chat_id=config.get("KST_NQ_TELEGRAM_CHAT_ID"),
            supabase_url=config.get("SUPABASE_URL"),
            supabase_key=config.get("SUPABASE_SERVICE_ROLE_KEY"))
    return {"status": "SIGNALS_ONLY", "alerts": count}

def main():
    if os.getenv("KST_NQ_ORDERS_ENABLED"):
        raise RuntimeError("This read-only worker refuses any order-execution configuration")
    path = os.getenv("KST_NQ_OUTBOX_PATH", "nq_signal_outbox.sqlite3")
    interval = int(os.getenv("KST_NQ_POLL_SECONDS", "15"))
    if not 10 <= interval <= 60:
        raise ValueError("Polling interval must be between 10 and 60 seconds")
    with sqlite3.connect(path) as db:
        init_db(db)
        while True:
            try:
                print(json.dumps(run_once(db, os.environ)), flush=True)
            except Exception as exc:
                print(json.dumps({"status": "WORKER_ERROR", "error_type": type(exc).__name__}), flush=True)
            time.sleep(interval)

if __name__ == "__main__":
    main()
