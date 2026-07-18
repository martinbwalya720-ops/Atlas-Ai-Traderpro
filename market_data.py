"""
Atlas AI Trader PRO - Market Data Engine
Fetches OHLC data via yfinance and computes a simple SMA/RSI based signal.
"""

import logging
import pandas as pd
import yfinance as yf

from config import TIMEFRAMES, DEFAULT_TIMEFRAME

logger = logging.getLogger(__name__)

# Alternate tickers to try if the primary one returns no data
# (mainly useful for Gold, which Yahoo exposes under a couple of symbols).
_FALLBACK_TICKERS = {
    "XAUUSD=X": ["GC=F"],
    "GC=F": ["XAUUSD=X"],
}


def _download(ticker: str, interval: str, period: str) -> pd.DataFrame:
    try:
        df = yf.download(
            ticker,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=True,
        )
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.warning("yfinance download failed for %s: %s", ticker, e)
    return pd.DataFrame()


def fetch_history(symbol: str, timeframe: str = DEFAULT_TIMEFRAME) -> pd.DataFrame:
    """Fetch historical OHLC data for a symbol, trying fallback tickers."""
    tf = TIMEFRAMES.get(timeframe, TIMEFRAMES[DEFAULT_TIMEFRAME])
    df = _download(symbol, tf["interval"], tf["period"])
    if df.empty:
        for alt in _FALLBACK_TICKERS.get(symbol, []):
            df = _download(alt, tf["interval"], tf["period"])
            if not df.empty:
                break
    return df


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    # avoid divide-by-zero
    avg_loss = avg_loss.replace(0, 1e-10)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def analyze(df: pd.DataFrame) -> dict:
    """Compute indicators and a directional signal from an OHLC dataframe."""
    close = df["Close"].dropna()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    if len(close) < 20:
        return {"error": "Not enough data points to analyze this symbol yet."}

    sma20 = close.rolling(window=20, min_periods=1).mean()
    sma50 = close.rolling(window=50, min_periods=1).mean()
    rsi = compute_rsi(close)

    last_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price
    change_pct = ((last_price - prev_price) / prev_price * 100) if prev_price else 0.0

    last_sma20 = float(sma20.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])
    last_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    signal, confidence = _decide_signal(last_price, last_sma20, last_sma50, last_rsi)

    return {
        "price": last_price,
        "change_pct": change_pct,
        "sma20": last_sma20,
        "sma50": last_sma50,
        "rsi": last_rsi,
        "signal": signal,
        "confidence": confidence,
    }


def _decide_signal(price, sma20, sma50, rsi):
    """Very simple trend + momentum rule set."""
    bullish_trend = price > sma20 > sma50
    bearish_trend = price < sma20 < sma50

    if bullish_trend and rsi < 70:
        strength = "Strong" if rsi < 60 else "Moderate"
        return "BUY", strength
    if bearish_trend and rsi > 30:
        strength = "Strong" if rsi > 40 else "Moderate"
        return "SELL", strength
    if rsi >= 70:
        return "SELL", "Overbought"
    if rsi <= 30:
        return "BUY", "Oversold"
    return "HOLD", "Neutral"


def get_signal(symbol: str, timeframe: str = DEFAULT_TIMEFRAME) -> dict:
    df = fetch_history(symbol, timeframe)
    if df.empty:
        return {"error": "No market data available right now (symbol may be closed or rate-limited)."}
    return analyze(df)


SIGNAL_EMOJI = {"BUY": "\U0001F7E2", "SELL": "\U0001F534", "HOLD": "\U0001F7E1"}


def format_signal_message(display_name: str, symbol: str, timeframe: str, result: dict) -> str:
    if "error" in result:
        return f"*{display_name}* ({symbol})\n\u26a0\ufe0f {result['error']}"

    emoji = SIGNAL_EMOJI.get(result["signal"], "\u26aa")
    arrow = "\u25b2" if result["change_pct"] >= 0 else "\u25bc"
    tf_label = TIMEFRAMES.get(timeframe, TIMEFRAMES[DEFAULT_TIMEFRAME])["label"]

    return (
        f"*{display_name}* `({symbol})`\n"
        f"Timeframe: {tf_label}\n"
        f"Price: `{result['price']:.5f}`  {arrow} {result['change_pct']:.2f}%\n"
        f"SMA20: `{result['sma20']:.5f}`   SMA50: `{result['sma50']:.5f}`\n"
        f"RSI(14): `{result['rsi']:.1f}`\n\n"
        f"{emoji} *Signal: {result['signal']}* ({result['confidence']})"
    )
