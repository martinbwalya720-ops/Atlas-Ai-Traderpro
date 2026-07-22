"""
Atlas AI Trader PRO
--------------------
A Telegram Forex/Gold/Crypto market-scanning and signal bot built with
python-telegram-bot v20+ and yfinance.

Run:
    export BOT_TOKEN="123456:ABC-your-token"
    python bot.py

See README.md for full setup and deployment instructions.
"""

import logging
import html
import uuid
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import keyboards as kb
import storage
import market_data
import news
import economic_calendar as econ_cal
import deriv_trading

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("atlas_ai_trader_pro")

WELCOME_TEXT = (
    "\U0001F916 *Welcome to Atlas AI Trader PRO*\n\n"
    "Your all-in-one market scanning assistant for Forex, Gold, and Crypto.\n"
    "Use the menu below to get started.\n\n"
    f"{config.DISCLAIMER}"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _safe_reply(message, text: str, reply_markup=None):
    """Send a message, automatically falling back to plain text if Markdown
    parsing fails (e.g. unescaped special characters slipping through from
    dynamic/external content), so a formatting glitch never blocks the
    whole message from being delivered."""
    try:
        return await message.reply_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        if "parse entities" not in str(e).lower() and "can't parse" not in str(e).lower():
            raise
        logger.warning("Markdown parse failed, resending as plain text: %s", e)
        return await message.reply_text(
            text, reply_markup=reply_markup, disable_web_page_preview=True,
        )


async def _send_or_edit(update: Update, text: str, reply_markup=None):
    """Edit the triggering message if this came from a button press,
    otherwise send a new message. Falls back to plain text automatically
    if Markdown parsing fails on the given content."""
    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        except BadRequest as e:
            if "parse entities" in str(e).lower() or "can't parse" in str(e).lower():
                logger.warning("Markdown parse failed on edit, resending as plain text: %s", e)
                try:
                    await query.edit_message_text(
                        text, reply_markup=reply_markup, disable_web_page_preview=True,
                    )
                except Exception:
                    await _safe_reply(query.message, text, reply_markup)
            else:
                # message content identical or too old to edit -> send fresh
                await _safe_reply(query.message, text, reply_markup)
        except Exception:
            await _safe_reply(query.message, text, reply_markup)
    else:
        await _safe_reply(update.effective_message, text, reply_markup)


def _clear_input_state(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting", None)


def _escape_md(value) -> str:
    """Escape Telegram Markdown special characters in dynamic/untrusted text
    (e.g. raw error messages from external APIs) so they can't break message
    formatting or get silently dropped."""
    text = str(value)
    for ch in ("_", "*", "`", "[", "]"):
        text = text.replace(ch, "\\" + ch)
    return text


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_input_state(context)
    storage.get_user(update.effective_user.id)  # ensure record exists
    await _send_or_edit(update, WELCOME_TEXT, kb.main_menu())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Atlas AI Trader PRO \u2014 Help*\n\n"
        "/start \u2014 Open the main menu\n"
        "/menu \u2014 Same as /start\n"
        "/scan \u2014 Quick market scan\n"
        "/watchlist \u2014 View your watchlist\n"
        "/journal \u2014 View your trade journal\n"
        "/settings \u2014 Open settings\n"
        "/cancel \u2014 Cancel a pending input (e.g. adding a symbol)\n\n"
        f"{config.DISCLAIMER}"
    )
    await _send_or_edit(update, text, kb.main_menu())


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_input_state(context)
    await update.effective_message.reply_text("Cancelled.", reply_markup=None)
    await _send_or_edit(update, WELCOME_TEXT, kb.main_menu())


async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_scan(update, context)


async def watchlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_watchlist(update, context)


async def journal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_journal(update, context)


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_settings(update, context)


# ---------------------------------------------------------------------------
# Callback query router
# ---------------------------------------------------------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if data == "menu:main":
        _clear_input_state(context)
        await _send_or_edit(update, WELCOME_TEXT, kb.main_menu())
        return

    if data == "menu:scan":
        await query.answer()
        await _send_or_edit(
            update,
            "*\U0001F50D Scan Markets*\n\nRun a full scan across major Forex pairs, Gold and BTC/ETH.",
            kb.scan_menu(),
        )
        return
    if data == "scan:run":
        await _run_scan(update, context)
        return

    if data == "menu:forex":
        await query.answer()
        await _send_or_edit(update, "*\U0001F4B1 Forex Pairs*\n\nChoose a pair:", kb.symbol_list_menu(config.FOREX_PAIRS, "forex"))
        return

    if data == "menu:gold":
        await query.answer()
        await _send_or_edit(update, "*\U0001F947 Gold*\n\nChoose an instrument:", kb.symbol_list_menu(config.GOLD_SYMBOLS, "gold"))
        return

    if data == "menu:crypto":
        await query.answer()
        await _send_or_edit(update, "*\u20BF Crypto*\n\nChoose a pair:", kb.symbol_list_menu(config.CRYPTO_PAIRS, "crypto"))
        return

    if data == "menu:synthetics":
        await query.answer()
        await _send_or_edit(
            update,
            "*\U0001F4CA Synthetics*\n\nDeriv's synthetic indices \u2014 trade 24/7, including weekends.\nChoose an index:",
            kb.symbol_list_menu(config.SYNTHETIC_SYMBOLS, "synthetic"),
        )
        return

    if data.startswith("sym:"):
        await _show_instrument(update, context, data)
        return

    if data.startswith("refresh:"):
        _, symbol, display = data.split(":", 2)
        await _show_signal(update, context, symbol, display)
        return

    if data.startswith("wladd:"):
        _, symbol, display = data.split(":", 2)
        added = storage.add_to_watchlist(update.effective_user.id, symbol, display)
        await query.answer("Added to watchlist \u2b50" if added else "Already in your watchlist")
        return

    if data.startswith("dpropose:"):
        _, symbol, display = data.split(":", 2)
        await _propose_trade(update, context, symbol, display)
        return

    if data.startswith("dtrade:approve:"):
        trade_id = data.split(":", 2)[2]
        await _approve_trade(update, context, trade_id)
        return

    if data.startswith("dtrade:reject:"):
        trade_id = data.split(":", 2)[2]
        pending = context.bot_data.get("pending_trades", {})
        pending.pop(trade_id, None)
        await query.answer("Trade cancelled")
        await _send_or_edit(update, "\u274c Trade proposal cancelled. No order was placed.", kb.main_menu())
        return

    if data == "settings:stake":
        await query.answer()
        settings = storage.get_settings(update.effective_user.id)
        await _send_or_edit(update, "Choose your default trade stake (demo funds):", kb.stake_menu(settings.get("stake", config.DEFAULT_STAKE)))
        return

    if data.startswith("setstake:"):
        amount = int(data.split(":", 1)[1])
        storage.update_setting(update.effective_user.id, "stake", amount)
        await query.answer(f"Stake set to ${amount}")
        await _show_settings(update, context)
        return

    if data == "menu:live":
        await _show_live_menu(update, context)
        return
    if data == "live:sub":
        storage.update_setting(update.effective_user.id, "live_signals", True)
        await query.answer("Subscribed to live signals \U0001F514")
        await _show_live_menu(update, context)
        return
    if data == "live:unsub":
        storage.update_setting(update.effective_user.id, "live_signals", False)
        await query.answer("Unsubscribed \U0001F515")
        await _show_live_menu(update, context)
        return
    if data == "live:now":
        await _run_scan(update, context, title="\U0001F4E1 Live Signals")
        return

    if data == "menu:watchlist":
        await query.answer()
        await _send_or_edit(update, "*\u2b50 Watchlist*", kb.watchlist_menu())
        return
    if data == "watchlist:view":
        await _show_watchlist(update, context)
        return
    if data == "watchlist:add":
        await query.answer()
        context.user_data["awaiting"] = "watchlist_add"
        await _send_or_edit(
            update,
            "Send me the symbol you'd like to add.\n\n"
            "Examples: `EURUSD=X`, `GC=F`, `BTC-USD`\n"
            "Tip: browse Forex/Gold/Crypto menus and use 'Add to Watchlist' for exact tickers.",
            kb.cancel_menu(),
        )
        return
    if data == "watchlist:remove":
        await query.answer()
        items = storage.get_watchlist(update.effective_user.id)
        if not items:
            await _send_or_edit(update, "Your watchlist is empty.", kb.watchlist_menu())
            return
        await _send_or_edit(update, "Select a symbol to remove:", kb.watchlist_remove_menu(items))
        return
    if data.startswith("wlrm:"):
        symbol = data.split(":", 1)[1]
        storage.remove_from_watchlist(update.effective_user.id, symbol)
        await query.answer("Removed")
        await _show_watchlist(update, context)
        return

    if data == "menu:journal":
        await query.answer()
        await _send_or_edit(update, "*\U0001F4D3 Trade Journal*", kb.journal_menu())
        return
    if data == "journal:view":
        await _show_journal(update, context)
        return
    if data == "journal:add":
        await query.answer()
        context.user_data["awaiting"] = "journal_add"
        await _send_or_edit(
            update,
            "Send your trade in this format (one line):\n\n"
            "`SYMBOL SIDE ENTRY EXIT NOTES`\n\n"
            "Example:\n`EURUSD BUY 1.0850 1.0910 Broke above resistance`\n\n"
            "_NOTES is optional._",
            kb.cancel_menu(),
        )
        return
    if data == "journal:clear":
        await query.answer()
        await _send_or_edit(update, "Are you sure you want to clear your entire journal?", kb.journal_clear_confirm())
        return
    if data == "journal:clear_confirm":
        storage.clear_journal(update.effective_user.id)
        await query.answer("Journal cleared")
        await _show_journal(update, context)
        return

    if data == "menu:news":
        await _show_news(update, context)
        return
    if data == "news:refresh":
        await _show_news(update, context)
        return

    if data == "menu:calendar":
        await _show_calendar(update, context)
        return
    if data == "calendar:refresh":
        await _show_calendar(update, context)
        return

    if data == "menu:settings":
        await _show_settings(update, context)
        return
    if data == "settings:risk":
        await query.answer()
        await _send_or_edit(update, "Choose your risk level:", kb.risk_menu())
        return
    if data.startswith("setrisk:"):
        level = data.split(":", 1)[1]
        storage.update_setting(update.effective_user.id, "risk", level)
        await query.answer(f"Risk level set to {level}")
        await _show_settings(update, context)
        return
    if data == "settings:timeframe":
        await query.answer()
        await _send_or_edit(update, "Choose your default timeframe:", kb.timeframe_menu())
        return
    if data.startswith("settf:"):
        tf = data.split(":", 1)[1]
        storage.update_setting(update.effective_user.id, "timeframe", tf)
        await query.answer(f"Timeframe set to {config.TIMEFRAMES[tf]['label']}")
        await _show_settings(update, context)
        return
    if data == "settings:toggle_live":
        settings = storage.get_settings(update.effective_user.id)
        new_val = not settings.get("live_signals", False)
        storage.update_setting(update.effective_user.id, "live_signals", new_val)
        await query.answer("Live signals " + ("enabled" if new_val else "disabled"))
        await _show_settings(update, context)
        return

    if data == "cancel:input":
        _clear_input_state(context)
        await query.answer("Cancelled")
        await _send_or_edit(update, WELCOME_TEXT, kb.main_menu())
        return

    await query.answer()


# ---------------------------------------------------------------------------
# Screen builders
# ---------------------------------------------------------------------------

async def _show_instrument(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    _, category, symbol, display = data.split(":", 3)
    await _show_signal(update, context, symbol, display)


async def _show_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str, display: str):
    query = update.callback_query
    await query.answer("Fetching data\u2026")
    settings = storage.get_settings(update.effective_user.id)
    timeframe = settings.get("timeframe", config.DEFAULT_TIMEFRAME)

    if display in config.SYNTHETIC_SYMBOLS:
        result = await deriv_trading.get_synthetic_signal(symbol, timeframe)
    else:
        result = market_data.get_signal(symbol, timeframe)

    text = market_data.format_signal_message(display, symbol, timeframe, result)
    tradeable = (
        "error" not in result
        and result.get("signal") in ("BUY", "SELL")
        and display in config.DERIV_SYMBOL_MAP
    )
    await _send_or_edit(update, text, kb.instrument_actions(symbol, display, tradeable=tradeable))


async def _propose_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str, display: str):
    query = update.callback_query
    await query.answer("Preparing trade proposal\u2026")

    user_id = update.effective_user.id
    settings = storage.get_settings(user_id)
    timeframe = settings.get("timeframe", config.DEFAULT_TIMEFRAME)

    if display in config.SYNTHETIC_SYMBOLS:
        result = await deriv_trading.get_synthetic_signal(symbol, timeframe)
    else:
        result = market_data.get_signal(symbol, timeframe)

    if "error" in result or result.get("signal") not in ("BUY", "SELL"):
        await _send_or_edit(update, "\u26a0\ufe0f This symbol no longer has an active BUY/SELL signal. Try refreshing.", kb.main_menu())
        return

    mapping = config.DERIV_SYMBOL_MAP.get(display)
    if not mapping:
        await _send_or_edit(update, "\u26a0\ufe0f This symbol isn't available for demo trade execution on Deriv.", kb.main_menu())
        return
    deriv_symbol, category = mapping

    stake = settings.get("stake", config.DEFAULT_STAKE)
    multiplier = config.DERIV_MULTIPLIER.get(category, config.DERIV_MULTIPLIER["default"])
    entry = result["price"]
    sl = result.get("stop_loss")
    tp = result.get("take_profit")

    potential_profit = potential_loss = None
    if sl and tp and entry:
        potential_profit = stake * multiplier * abs(tp - entry) / entry
        potential_loss = stake * multiplier * abs(entry - sl) / entry

    trade_id = uuid.uuid4().hex[:8]
    pending = context.bot_data.setdefault("pending_trades", {})
    pending[trade_id] = {
        "user_id": user_id,
        "deriv_symbol": deriv_symbol,
        "category": category,
        "display": display,
        "direction": result["signal"],
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "stake": stake,
    }

    lines = [
        "*\U0001F4E5 Trade Proposal \u2014 DEMO Account*",
        "",
        f"Instrument: *{display}*",
        f"Direction: *{result['signal']}*",
        f"Entry (approx.): `{entry:.5f}`",
        f"Stop-Loss: `{sl:.5f}`" if sl else "Stop-Loss: n/a",
        f"Take-Profit: `{tp:.5f}`" if tp else "Take-Profit: n/a",
        f"Stake: *${stake}*  |  Leverage: *x{multiplier}*",
    ]
    if potential_profit is not None:
        lines.append(f"Potential profit: *~${potential_profit:.2f}*  |  Potential loss: *~${potential_loss:.2f}*")
    lines.append(f"Risk Level: *{result.get('risk_level', 'n/a')}*  |  Confidence: *{result.get('confidence_score', 0)}%*")
    lines.append("")
    lines.append("\u26a0\ufe0f This places a REAL order on your Deriv *demo* account (virtual funds only). "
                  "Nothing happens unless you tap Approve.")

    await _send_or_edit(update, "\n".join(lines), kb.trade_proposal_menu(trade_id))


async def _approve_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, trade_id: str):
    query = update.callback_query
    pending = context.bot_data.get("pending_trades", {})
    trade = pending.pop(trade_id, None)

    if not trade:
        await query.answer("This proposal has expired.")
        await _send_or_edit(update, "\u26a0\ufe0f This trade proposal expired or was already handled.", kb.main_menu())
        return

    if trade["user_id"] != update.effective_user.id:
        await query.answer("Not your proposal.")
        return

    await query.answer("Placing trade\u2026")
    await _send_or_edit(update, "\u23F3 Placing your trade on Deriv, please wait\u2026", None)

    result = await deriv_trading.place_multiplier_trade(
        symbol=trade["deriv_symbol"],
        direction=trade["direction"],
        stake=trade["stake"],
        stop_loss=trade["sl"],
        take_profit=trade["tp"],
        category=trade["category"],
    )

    if result["success"]:
        text = (
            "\u2705 *Trade Placed Successfully*\n\n"
            f"Instrument: *{_escape_md(trade['display'])}*\n"
            f"Direction: *{_escape_md(trade['direction'])}*\n"
            f"Contract ID: `{_escape_md(result['contract_id'])}`\n"
            f"Buy Price: `{_escape_md(result['buy_price'])}`\n\n"
            "This was placed on your *demo* account only."
        )
    else:
        text = (
            "\u274c *Trade Not Placed*\n\n"
            f"Reason: {_escape_md(result['error'])}\n\n"
            "No funds were affected."
        )

    await _safe_reply(update.effective_message, text, kb.main_menu())


async def _run_scan(update: Update, context: ContextTypes.DEFAULT_TYPE, title: str = "\U0001F50D Market Scan"):
    query = update.callback_query
    if query:
        await query.answer("Scanning markets\u2026")
    settings = storage.get_settings(update.effective_user.id)
    timeframe = settings.get("timeframe", config.DEFAULT_TIMEFRAME)

    lines = [f"*{title}*", f"_Timeframe: {config.TIMEFRAMES[timeframe]['label']}_", ""]
    for display, symbol in config.SCAN_UNIVERSE.items():
        result = market_data.get_signal(symbol, timeframe)
        if "error" in result:
            continue
        emoji = market_data.SIGNAL_EMOJI.get(result["signal"], "\u26aa")
        risk_emoji = market_data.RISK_EMOJI.get(result["risk_level"], "\u26aa")
        lines.append(
            f"{emoji} *{display}* \u2014 {result['signal']} ({result['confidence']}, {result['confidence_score']}%) "
            f"| {risk_emoji} Risk: {result['risk_level']}"
        )

    for display, symbol in config.SCAN_SYNTHETICS.items():
        result = await deriv_trading.get_synthetic_signal(symbol, timeframe)
        if "error" in result:
            continue
        emoji = market_data.SIGNAL_EMOJI.get(result["signal"], "\u26aa")
        risk_emoji = market_data.RISK_EMOJI.get(result["risk_level"], "\u26aa")
        lines.append(
            f"{emoji} *{display}* \u2014 {result['signal']} ({result['confidence']}, {result['confidence_score']}%) "
            f"| {risk_emoji} Risk: {result['risk_level']}"
        )

    lines.append("")
    lines.append(config.DISCLAIMER)
    await _send_or_edit(update, "\n".join(lines), kb.scan_menu())


async def _show_live_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    settings = storage.get_settings(update.effective_user.id)
    subscribed = settings.get("live_signals", False)
    status_text = "Subscribed \u2705" if subscribed else "Not subscribed"
    text = (
        "*\U0001F4E1 Live Signals*\n\n"
        f"Status: {status_text}\n"
        f"When subscribed, you'll receive automatic scans roughly every "
        f"{config.LIVE_SIGNAL_INTERVAL_SECONDS // 60} minutes."
    )
    await _send_or_edit(update, text, kb.live_signals_menu(subscribed))


async def _show_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    items = storage.get_watchlist(update.effective_user.id)
    if not items:
        text = "*\u2b50 Watchlist*\n\nYour watchlist is empty. Add symbols from Forex/Gold/Crypto menus or type one in."
        await _send_or_edit(update, text, kb.watchlist_menu())
        return

    settings = storage.get_settings(update.effective_user.id)
    timeframe = settings.get("timeframe", config.DEFAULT_TIMEFRAME)
    lines = ["*\u2b50 Watchlist*", ""]
    for item in items:
        result = market_data.get_signal(item["symbol"], timeframe)
        if "error" in result:
            lines.append(f"\u26aa *{item['display']}* \u2014 data unavailable")
            continue
        emoji = market_data.SIGNAL_EMOJI.get(result["signal"], "\u26aa")
        lines.append(f"{emoji} *{item['display']}* \u2014 {result['signal']} | Price {result['price']:.5f}")

    await _send_or_edit(update, "\n".join(lines), kb.watchlist_menu())


async def _show_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    entries = storage.get_journal(update.effective_user.id)
    if not entries:
        text = "*\U0001F4D3 Trade Journal*\n\nNo trades logged yet. Tap 'Add Trade' to log your first one."
        await _send_or_edit(update, text, kb.journal_menu())
        return

    lines = ["*\U0001F4D3 Trade Journal* (latest 10)", ""]
    for e in entries[-10:][::-1]:
        try:
            pnl = float(e["exit"]) - float(e["entry"])
            if e.get("side", "").upper() == "SELL":
                pnl = -pnl
            pnl_str = f"{pnl:+.5f}"
        except (ValueError, KeyError):
            pnl_str = "n/a"
        ts = e.get("timestamp", "")
        date_str = ts[:10] if ts else ""
        lines.append(
            f"\u2022 *{e.get('symbol','?')}* {e.get('side','?')} | "
            f"Entry {e.get('entry','?')} \u2192 Exit {e.get('exit','?')} | "
            f"P/L {pnl_str} ({date_str})"
        )
        if e.get("notes"):
            lines.append(f"  _{html.escape(e['notes'])}_")

    await _send_or_edit(update, "\n".join(lines), kb.journal_menu())


async def _show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("Fetching news\u2026")
    items = news.get_market_news()
    text = news.format_news_message(items)
    await _send_or_edit(update, text, kb.news_menu())


async def _show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("Fetching calendar\u2026")
    events = econ_cal.get_upcoming_events()
    text = econ_cal.format_calendar_message(events)
    await _send_or_edit(update, text, kb.calendar_menu())


async def _show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    settings = storage.get_settings(update.effective_user.id)
    text = "*\u2699\ufe0f Settings*\n\nCustomize your risk level, default timeframe and live signal alerts."
    await _send_or_edit(update, text, kb.settings_menu(settings))


# ---------------------------------------------------------------------------
# Free-text input handler (watchlist add / journal add)
# ---------------------------------------------------------------------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return  # not in an input flow; ignore stray text

    text = (update.effective_message.text or "").strip()

    if awaiting == "watchlist_add":
        symbol = text.upper().replace(" ", "")
        result = market_data.get_signal(symbol)
        if "error" in result:
            await _safe_reply(
                update.effective_message,
                f"\u26a0\ufe0f Couldn't find data for `{_escape_md(symbol)}`. Double check the ticker and try again, "
                "or /cancel.",
            )
            return
        added = storage.add_to_watchlist(update.effective_user.id, symbol, symbol)
        _clear_input_state(context)
        safe_symbol = _escape_md(symbol)
        msg = f"\u2b50 Added *{safe_symbol}* to your watchlist." if added else f"*{safe_symbol}* is already in your watchlist."
        await _safe_reply(update.effective_message, msg, kb.watchlist_menu())
        return

    if awaiting == "journal_add":
        parts = text.split(maxsplit=4)
        if len(parts) < 4:
            await _safe_reply(
                update.effective_message,
                "Please use the format: `SYMBOL SIDE ENTRY EXIT NOTES`\n"
                "Example: `EURUSD BUY 1.0850 1.0910 Broke resistance`",
            )
            return

        symbol, side, entry, exit_ = parts[0], parts[1], parts[2], parts[3]
        notes = parts[4] if len(parts) > 4 else ""

        try:
            float(entry)
            float(exit_)
        except ValueError:
            await _safe_reply(
                update.effective_message,
                "Entry and Exit must be numbers. Example:\n`EURUSD BUY 1.0850 1.0910 Broke resistance`",
            )
            return

        if side.upper() not in ("BUY", "SELL"):
            await update.effective_message.reply_text("SIDE must be BUY or SELL.")
            return

        storage.add_journal_entry(update.effective_user.id, {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "entry": entry,
            "exit": exit_,
            "notes": notes,
        })
        _clear_input_state(context)
        await _safe_reply(
            update.effective_message,
            f"\u2705 Trade logged: *{_escape_md(symbol.upper())}* {_escape_md(side.upper())} {_escape_md(entry)} \u2192 {_escape_md(exit_)}",
            kb.journal_menu(),
        )
        return


# ---------------------------------------------------------------------------
# Background job: push live signals to subscribed users
# ---------------------------------------------------------------------------

async def live_signal_job(context: ContextTypes.DEFAULT_TYPE):
    subscribed_ids = storage.get_subscribed_user_ids()
    if not subscribed_ids:
        return

    for uid in subscribed_ids:
        try:
            settings = storage.get_settings(int(uid))
            timeframe = settings.get("timeframe", config.DEFAULT_TIMEFRAME)

            lines = ["*\U0001F4E1 Live Signal Update*", ""]
            has_signal = False
            for display, symbol in config.SCAN_UNIVERSE.items():
                result = market_data.get_signal(symbol, timeframe)
                if "error" in result or result["signal"] == "HOLD":
                    continue
                has_signal = True
                emoji = market_data.SIGNAL_EMOJI.get(result["signal"], "\u26aa")
                risk_emoji = market_data.RISK_EMOJI.get(result["risk_level"], "\u26aa")
                lines.append(
                    f"{emoji} *{display}* \u2014 {result['signal']} ({result['confidence']}, {result['confidence_score']}%) "
                    f"| {risk_emoji} Risk: {result['risk_level']}"
                )

            for display, symbol in config.SCAN_SYNTHETICS.items():
                result = await deriv_trading.get_synthetic_signal(symbol, timeframe)
                if "error" in result or result["signal"] == "HOLD":
                    continue
                has_signal = True
                emoji = market_data.SIGNAL_EMOJI.get(result["signal"], "\u26aa")
                risk_emoji = market_data.RISK_EMOJI.get(result["risk_level"], "\u26aa")
                lines.append(
                    f"{emoji} *{display}* \u2014 {result['signal']} ({result['confidence']}, {result['confidence_score']}%) "
                    f"| {risk_emoji} Risk: {result['risk_level']}"
                )

            if has_signal:
                lines.append("")
                lines.append(config.DISCLAIMER)
                await context.bot.send_message(
                    chat_id=int(uid),
                    text="\n".join(lines),
                    parse_mode=ParseMode.MARKDOWN,
                )
        except Exception as e:
            logger.warning("Failed to send live signal to %s: %s", uid, e)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "\u26a0\ufe0f Something went wrong processing that. Please try again."
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    if not config.BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN environment variable is not set. "
            "Set it with: export BOT_TOKEN='your-token-here'"
        )

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CommandHandler("scan", scan_cmd))
    application.add_handler(CommandHandler("watchlist", watchlist_cmd))
    application.add_handler(CommandHandler("journal", journal_cmd))
    application.add_handler(CommandHandler("settings", settings_cmd))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    application.add_error_handler(error_handler)

    if application.job_queue is not None:
        application.job_queue.run_repeating(
            live_signal_job,
            interval=config.LIVE_SIGNAL_INTERVAL_SECONDS,
            first=config.LIVE_SIGNAL_FIRST_RUN_DELAY,
            name="live_signal_job",
        )
    else:
        logger.warning(
            "JobQueue is not available. Install python-telegram-bot[job-queue] "
            "to enable the Live Signals background job."
        )

    logger.info("%s is starting...", config.BOT_NAME)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
