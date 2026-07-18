"""
Atlas AI Trader PRO - Configuration
Central place for symbols, timeframes, and app-wide constants.
"""

import os

# ---------------------------------------------------------------------------
# Bot / runtime config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_NAME = "Atlas AI Trader PRO"

# How often (seconds) the background job scans the market for live signals
LIVE_SIGNAL_INTERVAL_SECONDS = int(os.environ.get("LIVE_SIGNAL_INTERVAL_SECONDS", 900))  # 15 min
LIVE_SIGNAL_FIRST_RUN_DELAY = 30

# Data persistence
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USER_DATA_FILE = os.path.join(DATA_DIR, "users.json")

# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
# Display name -> Yahoo Finance ticker
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
    "EUR/GBP": "EURGBP=X",
}

# Gold has a couple of possible Yahoo tickers depending on region/availability.
# We try them in order (see market_data.fetch_history) until one returns data.
GOLD_SYMBOLS = {
    "Gold Spot (XAU/USD)": "XAUUSD=X",
    "Gold Futures (COMEX)": "GC=F",
}

CRYPTO_PAIRS = {
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "BNB/USD": "BNB-USD",
    "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD",
    "ADA/USD": "ADA-USD",
}

# Universe used by "Scan Markets" and the live-signal background job
SCAN_UNIVERSE = {
    **FOREX_PAIRS,
    "Gold Spot (XAU/USD)": "XAUUSD=X",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
}

# Reference tickers used to aggregate general market headlines
NEWS_TICKERS = ["EURUSD=X", "GC=F", "BTC-USD", "^DJI", "CL=F"]

# yfinance-valid (interval, period) combos we expose to users
TIMEFRAMES = {
    "15m": {"interval": "15m", "period": "5d", "label": "15 Minutes"},
    "1h": {"interval": "60m", "period": "1mo", "label": "1 Hour"},
    "1d": {"interval": "1d", "period": "6mo", "label": "1 Day"},
}
DEFAULT_TIMEFRAME = "1h"

# Economic calendar feed (public, no API key required)
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

RISK_LEVELS = ["Low", "Medium", "High"]
DEFAULT_RISK = "Medium"

DISCLAIMER = (
    "\u26a0\ufe0f *Educational tool only.* Signals are generated from basic "
    "technical indicators (SMA/RSI) and are *not* financial advice. Always "
    "do your own research and manage your risk."
)
