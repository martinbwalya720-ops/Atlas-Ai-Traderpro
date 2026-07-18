# Atlas AI Trader PRO

A full-featured Telegram bot for scanning Forex, Gold, and Crypto markets —
built with **python-telegram-bot v20+** and **yfinance**.

> ⚠️ **Educational tool only.** Signals are generated from basic technical
> indicators (SMA20/SMA50 trend + RSI14 momentum) and are **not** financial
> advice. Always do your own research and manage risk appropriately.

---

## ✨ Features

| Button | What it does |
|---|---|
| 🔍 **Scan Markets** | Runs a full scan across major Forex pairs, Gold, and BTC/ETH with BUY/SELL/HOLD signals |
| 🥇 **Gold** | Live price + signal for Spot Gold (XAU/USD) and Gold Futures |
| 💱 **Forex** | Live price + signal for 8 major/minor currency pairs |
| ₿ **Crypto** | Live price + signal for BTC, ETH, BNB, SOL, XRP, ADA |
| 📡 **Live Signals** | Subscribe to receive automatic signal alerts on a background schedule |
| ⭐ **Watchlist** | Add/remove/view custom symbols per user |
| 📓 **Trade Journal** | Log trades (symbol, side, entry, exit, notes) with auto P/L calc |
| 📰 **Market News** | Aggregated recent headlines relevant to Forex/Gold/Crypto |
| 📅 **Economic Calendar** | Upcoming medium/high-impact economic events for the week |
| ⚙️ **Settings** | Risk level, default timeframe (15m/1h/1d), live signal toggle |

All data is per-user and stored locally in `data/users.json` (no external
database required).

---

## 🚀 Quick start (local)

1. **Clone and enter the project**
   ```bash
   git clone <your-repo-url> atlas-ai-trader-pro
   cd atlas-ai-trader-pro
