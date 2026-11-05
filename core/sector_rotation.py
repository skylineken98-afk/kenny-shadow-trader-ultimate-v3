"""Sector rotation screen: daily ETF price/volume proxies, NOT actual capital flows.

Only return independently fetched, nonempty, timestamped data. All indicators
are derived from price/volume and must not be labeled institutional flows.
"""
from datetime import datetime, timezone
import math

from core.market import history
from core.flow_intelligence import measure_flow

SECTORS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
    "Communication Services": "XLC",
}
BENCHMARK = "SPY"


def _return_pct(closes, sessions):
    if len(closes) <= sessions or float(closes.iloc[-sessions-1]) <= 0:
        return None
    return round((float(closes.iloc[-1]) / float(closes.iloc[-sessions-1]) - 1) * 100, 2)


def screen_sector_data(load=history, now=None):
    """One snapshot, using completed daily bars only. No fabricated fill data."""
    import pandas as pd

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    rows, notices = [], []
    benchmark = None
    frames = {}
    # Deliberately ignore today's potentially incomplete daily bar. During
    # market hours this view represents the previous COMPLETED session.
    for ticker in [BENCHMARK, *SECTORS.values()]:
        try:
            df = load(ticker, period="3mo", interval="1d")
            if df is None or df.empty:
                raise ValueError("no daily candles")
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            dates = df.index
            if dates.tz is None:
                from zoneinfo import ZoneInfo
                dates = dates.tz_localize(ZoneInfo("America/New_York"))
            else:
                dates = dates.tz_convert("America/New_York")
            df = df.loc[dates.date < now.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()]
            df = df.dropna(subset=["Close", "High", "Low", "Volume"])
            if len(df) < 23 or (df["Close"].astype(float) <= 0).any():
                raise ValueError("fewer than 23 valid completed trading sessions")
            last = df.index[-1]
            day = str(last.date())
            age_days = (now.date() - last.date()).days
            if age_days > 5:
                raise ValueError(f"last completed session {day} is stale")
            frames[ticker] = df
        except Exception as exc:
            notices.append(f"{ticker}: unavailable ({type(exc).__name__}: {exc})")

    if BENCHMARK not in frames:
        return [], ["SPY benchmark unavailable; relative-strength ranking suppressed.", *notices]

    benchmark = _return_pct(frames[BENCHMARK]["Close"], 20)
    if benchmark is None:
        return [], ["SPY benchmark lacks 20-session history.", *notices]

    for sector, ticker in SECTORS.items():
        df = frames.get(ticker)
        if df is None:
            continue
        try:
            c = df["Close"].astype(float)
            ret20, ret5 = _return_pct(c, 20), _return_pct(c, 5)
            flow = measure_flow(df, 20)
            if ret20 is None or ret5 is None or flow is None:
                raise ValueError("insufficient price/volume history")
            cmf = float(flow["chaikin_money_flow"])
            if not math.isfinite(cmf):
                raise ValueError("invalid volume pressure")
            rows.append({
                "Sector": sector,
                "ETF": ticker,
                "As of (session)": str(df.index[-1].date()),
                "20d return %": ret20,
                "5d return %": ret5,
                "vs SPY 20d (pp)": round(ret20 - benchmark, 2),
                "20d volume pressure (CMF)": cmf,
                "Volume proxy": flow["direction"],
            })
        except Exception as exc:
            notices.append(f"{ticker}: unavailable ({type(exc).__name__}: {exc})")
    rows.sort(key=lambda r: r["vs SPY 20d (pp)"], reverse=True)
    return rows, notices
