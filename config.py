
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

# ---------------------------------------------------------------------------
# Deriv trading (optional - powers the "Place Demo Trade" approval flow)
# ---------------------------------------------------------------------------
DERIV_API_TOKEN = os.environ.get("DERIV_API_TOKEN", "")
DERIV_APP_ID = os.environ.get("DERIV_APP_ID", "1089")
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id={app_id}"

# Our display name -> (Deriv underlying symbol code, category)
DERIV_SYMBOL_MAP = {
    "EUR/USD": ("frxEURUSD", "forex"),
    "GBP/USD": ("frxGBPUSD", "forex"),
    "USD/JPY": ("frxUSDJPY", "forex"),
    "USD/CHF": ("frxUSDCHF", "forex"),
    "AUD/USD": ("frxAUDUSD", "forex"),
    "USD/CAD": ("frxUSDCAD", "forex"),
    "NZD/USD": ("frxNZDUSD", "forex"),
    "EUR/GBP": ("frxEURGBP", "forex"),
    "Gold Spot (XAU/USD)": ("frxXAUUSD", "gold"),
    "BTC/USD": ("cryBTCUSD", "crypto"),
    "ETH/USD": ("cryETHUSD", "crypto"),
}

# Synthetic indices - these exist only on Deriv (no Yahoo Finance data), so
# the display name IS the symbol used everywhere (no separate ticker).
# They trade 24/7, including weekends.
SYNTHETIC_SYMBOLS = {
    "Volatility 10 Index": "R_10",
    "Volatility 25 Index": "R_25",
    "Volatility 50 Index": "R_50",
    "Volatility 75 Index": "R_75",
    "Volatility 100 Index": "R_100",
    "Boom 500 Index": "BOOM500",
    "Boom 1000 Index": "BOOM1000",
    "Crash 500 Index": "CRASH500",
    "Crash 1000 Index": "CRASH1000",
    "Step Index": "STPRNG",
}
DERIV_SYMBOL_MAP.update({name: (code, "synthetic") for name, code in SYNTHETIC_SYMBOLS.items()})

# Candle granularity (seconds) used when pulling synthetic index history
# directly from Deriv, matched to our existing timeframe options.
SYNTHETIC_GRANULARITY = {
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
}

# A small curated subset included in Scan Markets / Live Signals, kept short
# since each one requires its own Deriv API round-trip (unlike the batched
# yfinance calls used for forex/gold/crypto).
SCAN_SYNTHETICS = {
    "Volatility 75 Index": "R_75",
    "Boom 1000 Index": "BOOM1000",
    "Crash 1000 Index": "CRASH1000",
}

# Conservative leverage per category. Deriv enforces its own max per symbol -
# if a value here exceeds what's allowed, Deriv's API returns a clear error
# that the bot will show you, so you know to lower it here.
DERIV_MULTIPLIER = {
    "forex": 50,
    "gold": 20,
    "crypto": 5,
    "synthetic": 20,
    "default": 20,
}


STAKE_OPTIONS = [1, 5, 10, 20]
DEFAULT_STAKE = 1
