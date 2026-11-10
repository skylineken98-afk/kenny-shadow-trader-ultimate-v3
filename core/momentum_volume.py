"""Default KST momentum/volume qualification for options, stocks and crypto.

One completed intraday OHLCV stream; NO 4H/1H/5M trend-alignment gate.
Observed candle volume is not verified options flow and scores are not win odds.
"""
import math
import pandas as pd

def qualify(df, symbol="", now=None, bar_minutes=1, max_stale_minutes=15,
            min_rvol=1.20, min_move=0.001):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("Aware now required")
    now = now.tz_convert("UTC")
    if df is None or len(df) < 35:
        return dict(symbol=symbol, status="INSUFFICIENT_DATA", side="WAIT",
                    strategy="MOMENTUM_VOLUME", reason="At least 35 intraday bars required")
    try:
        d = df[["Open", "High", "Low", "Close", "Volume"]].copy().sort_index()
        if d.index.tz is None or d.index.has_duplicates:
            raise ValueError("Invalid bar timestamps")
        d.index = d.index.tz_convert("UTC")
        d = d.loc[d.index + pd.Timedelta(minutes=bar_minutes) <= now]
        if len(d) < 35:
            raise ValueError("Insufficient completed candles")
        tail = d.tail(60)
        if (tail.index[-1] + pd.Timedelta(minutes=bar_minutes) - now).total_seconds() < -60*max_stale_minutes:
            return dict(symbol=symbol, status="STALE_DATA", side="WAIT",
                        strategy="MOMENTUM_VOLUME", reason="Last completed candle is stale")
        if (tail.index.to_series().diff().dropna() <= pd.Timedelta(0)).any():
            raise ValueError("Unordered candle timestamps")
        if not all(bool(pd.to_numeric(tail[k], errors="coerce").notna().all()) for k in ("Open","High","Low","Close","Volume")):
            raise ValueError("Missing OHLCV values")
        if not all(math.isfinite(float(v)) for v in tail.to_numpy().ravel()):
            raise ValueError("Nonfinite values")
        if (tail[["Open","High","Low","Close"]] <= 0).any().any() or (tail["Volume"] < 0).any():
            raise ValueError("Invalid prices or negative volume")
        if ((tail["High"] < tail[["Open","Close","Low"]].max(axis=1)) |
            (tail["Low"] > tail[["Open","Close","High"]].min(axis=1))).any():
            raise ValueError("Invalid OHLC geometry")
        # Exclude empty/zero baseline; free providers may supply missing volume.
        vbase = float(tail["Volume"].iloc[-21:-1].mean())
        if vbase <= 0:
            raise ValueError("No verified volume baseline")
        rvol = float(tail["Volume"].iloc[-1]) / vbase
        last = float(tail["Close"].iloc[-1])
        prior3 = float(tail["Close"].iloc[-4])
        move = last / prior3 - 1
        previous_high = float(tail["High"].iloc[-21:-1].max())
        previous_low = float(tail["Low"].iloc[-21:-1].min())
        # Momentum can qualify by accelerating directional price movement OR
        # break of the previous range. No rigid higher-timeframe agreement.
        up = move >= min_move or last > previous_high
        down = move <= -min_move or last < previous_low
        side = "BULLISH" if up and not down else "BEARISH" if down and not up else "WAIT"
        if rvol < min_rvol or side == "WAIT":
            return dict(symbol=symbol, status="WAIT", side="WAIT", strategy="MOMENTUM_VOLUME",
                        reason="Momentum and volume not jointly confirmed",
                        rvol=round(rvol,3), move_3bar_pct=round(move*100,3),
                        bar_closed_at=(tail.index[-1]+pd.Timedelta(minutes=bar_minutes)).isoformat())
        # Volatility-based indicative levels; no option-premium target claims.
        closeprev = tail["Close"].shift(1)
        true_range = pd.concat([(tail["High"]-tail["Low"]),
            (tail["High"]-closeprev).abs(), (tail["Low"]-closeprev).abs()],axis=1).max(axis=1)
        atr = float(true_range.tail(14).mean())
        if not math.isfinite(atr) or atr <= 0:
            raise ValueError("No usable ATR")
        risk = 1.5*atr
        if side == "BULLISH":
            stop, target = last-risk, last+1.5*risk
        else:
            stop, target = last+risk, last-1.5*risk
        if stop <= 0 or target <= 0:
            raise ValueError("Invalid indicative levels")
        return dict(symbol=symbol, status="SETUP", side=side, strategy="MOMENTUM_VOLUME",
                    entry=last, stop=stop, target=target, confidence_label="RULE_BASED_ONLY",
                    rvol=round(rvol,3), move_3bar_pct=round(move*100,3),
                    reason="Recent directional price momentum with volume expansion",
                    bar_closed_at=(tail.index[-1]+pd.Timedelta(minutes=bar_minutes)).isoformat(),
                    frames={}, price=last, volume=float(tail["Volume"].iloc[-1]))
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        return dict(symbol=symbol, status="INSUFFICIENT_DATA", side="WAIT",
                    strategy="MOMENTUM_VOLUME", reason=type(exc).__name__)
