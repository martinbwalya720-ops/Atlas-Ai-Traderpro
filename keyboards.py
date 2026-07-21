"""
Atlas AI Trader PRO - Keyboards
All InlineKeyboardMarkup layouts live here, kept separate from handler logic.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import FOREX_PAIRS, GOLD_SYMBOLS, CRYPTO_PAIRS, TIMEFRAMES, RISK_LEVELS, STAKE_OPTIONS, DEFAULT_STAKE


def main_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("\U0001F50D Scan Markets", callback_data="menu:scan")],
        [
            InlineKeyboardButton("\U0001F947 Gold", callback_data="menu:gold"),
            InlineKeyboardButton("\U0001F4B1 Forex", callback_data="menu:forex"),
        ],
        [
            InlineKeyboardButton("\u20BF Crypto", callback_data="menu:crypto"),
            InlineKeyboardButton("\U0001F4CA Synthetics", callback_data="menu:synthetics"),
        ],
        [
            InlineKeyboardButton("\U0001F4E1 Live Signals", callback_data="menu:live"),
            InlineKeyboardButton("\u2B50 Watchlist", callback_data="menu:watchlist"),
        ],
        [
            InlineKeyboardButton("\U0001F4D3 Trade Journal", callback_data="menu:journal"),
            InlineKeyboardButton("\U0001F4F0 Market News", callback_data="menu:news"),
        ],
        [
            InlineKeyboardButton("\U0001F4C5 Econ Calendar", callback_data="menu:calendar"),
            InlineKeyboardButton("\u2699\ufe0f Settings", callback_data="menu:settings"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def back_button(target: str = "menu:main") -> InlineKeyboardButton:
    return InlineKeyboardButton("\u2b05\ufe0f Back", callback_data=target)


def symbol_list_menu(symbol_map: dict, category: str) -> InlineKeyboardMarkup:
    rows = []
    for display, symbol in symbol_map.items():
        rows.append([InlineKeyboardButton(display, callback_data=f"sym:{category}:{symbol}:{display}")])
    rows.append([back_button()])
    return InlineKeyboardMarkup(rows)


def instrument_actions(symbol: str, display: str, tradeable: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F504 Refresh Signal", callback_data=f"refresh:{symbol}:{display}")],
    ]
    if tradeable:
        rows.append([InlineKeyboardButton("\U0001F4E5 Place Demo Trade", callback_data=f"dpropose:{symbol}:{display}")])
    rows.append([InlineKeyboardButton("\u2b50 Add to Watchlist", callback_data=f"wladd:{symbol}:{display}")])
    rows.append([back_button()])
    return InlineKeyboardMarkup(rows)


def trade_proposal_menu(trade_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\u2705 Approve & Place Trade", callback_data=f"dtrade:approve:{trade_id}")],
        [InlineKeyboardButton("\u274c Cancel", callback_data=f"dtrade:reject:{trade_id}")],
    ]
    return InlineKeyboardMarkup(rows)


def stake_menu(current_stake) -> InlineKeyboardMarkup:
    rows = []
    for amt in STAKE_OPTIONS:
        label = f"${amt}" + (" \u2705" if amt == current_stake else "")
        rows.append([InlineKeyboardButton(label, callback_data=f"setstake:{amt}")])
    rows.append([back_button("menu:settings")])
    return InlineKeyboardMarkup(rows)


def scan_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F50D Run Full Scan", callback_data="scan:run")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def live_signals_menu(subscribed: bool) -> InlineKeyboardMarkup:
    toggle_text = "\U0001F515 Unsubscribe" if subscribed else "\U0001F514 Subscribe to Live Signals"
    toggle_data = "live:unsub" if subscribed else "live:sub"
    rows = [
        [InlineKeyboardButton(toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton("\U0001F50D Get Signals Now", callback_data="live:now")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def watchlist_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F441\ufe0f View Watchlist", callback_data="watchlist:view")],
        [InlineKeyboardButton("\u2795 Add Symbol", callback_data="watchlist:add")],
        [InlineKeyboardButton("\u2796 Remove Symbol", callback_data="watchlist:remove")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def watchlist_remove_menu(items: list) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        rows.append([InlineKeyboardButton(
            f"\u274c {item['display']}", callback_data=f"wlrm:{item['symbol']}"
        )])
    rows.append([back_button("menu:watchlist")])
    return InlineKeyboardMarkup(rows)


def journal_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F4D6 View Journal", callback_data="journal:view")],
        [InlineKeyboardButton("\u2795 Add Trade", callback_data="journal:add")],
        [InlineKeyboardButton("\U0001F5D1\ufe0f Clear Journal", callback_data="journal:clear")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def journal_clear_confirm() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\u2705 Yes, clear it", callback_data="journal:clear_confirm")],
        [back_button("menu:journal")],
    ]
    return InlineKeyboardMarkup(rows)


def news_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F504 Refresh News", callback_data="news:refresh")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def calendar_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F504 Refresh Calendar", callback_data="calendar:refresh")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def settings_menu(settings: dict) -> InlineKeyboardMarkup:
    live_status = "ON \u2705" if settings.get("live_signals") else "OFF \u274c"
    rows = [
        [InlineKeyboardButton(f"\U0001F3AF Risk Level: {settings.get('risk')}", callback_data="settings:risk")],
        [InlineKeyboardButton(f"\u23F1\ufe0f Timeframe: {TIMEFRAMES[settings.get('timeframe')]['label']}", callback_data="settings:timeframe")],
        [InlineKeyboardButton(f"\U0001F4E1 Live Signals: {live_status}", callback_data="settings:toggle_live")],
        [InlineKeyboardButton(f"\U0001F4B0 Trade Stake: ${settings.get('stake', DEFAULT_STAKE)}", callback_data="settings:stake")],
        [back_button()],
    ]
    return InlineKeyboardMarkup(rows)


def risk_menu() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(level, callback_data=f"setrisk:{level}")] for level in RISK_LEVELS]
    rows.append([back_button("menu:settings")])
    return InlineKeyboardMarkup(rows)


def timeframe_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(v["label"], callback_data=f"settf:{k}")]
        for k, v in TIMEFRAMES.items()
    ]
    rows.append([back_button("menu:settings")])
    return InlineKeyboardMarkup(rows)


def cancel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("\u274c Cancel", callback_data="cancel:input")]])
