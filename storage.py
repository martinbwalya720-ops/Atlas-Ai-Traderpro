"""
Atlas AI Trader PRO - Storage
Lightweight JSON-file persistence for per-user state (watchlist, journal,
settings, live-signal subscription). Good enough for small/medium bot
deployments without needing an external database.
"""

import json
import os
import threading
from datetime import datetime, timezone

from config import DATA_DIR, USER_DATA_FILE, DEFAULT_RISK, DEFAULT_TIMEFRAME

_lock = threading.Lock()


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w") as f:
            json.dump({}, f)


def _load() -> dict:
    _ensure_store()
    with open(USER_DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict):
    _ensure_store()
    tmp_path = USER_DATA_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, USER_DATA_FILE)


def _default_user() -> dict:
    return {
        "watchlist": [],
        "journal": [],
        "settings": {
            "risk": DEFAULT_RISK,
            "timeframe": DEFAULT_TIMEFRAME,
            "live_signals": False,
        },
    }


def get_user(user_id: int) -> dict:
    """Return (and lazily create) the stored record for a user."""
    uid = str(user_id)
    with _lock:
        data = _load()
        if uid not in data:
            data[uid] = _default_user()
            _save(data)
        user = data[uid]
        # backfill any new fields for users created with an older schema
        defaults = _default_user()
        changed = False
        for key, val in defaults.items():
            if key not in user:
                user[key] = val
                changed = True
        for key, val in defaults["settings"].items():
            if key not in user["settings"]:
                user["settings"][key] = val
                changed = True
        if changed:
            data[uid] = user
            _save(data)
        return user


def save_user(user_id: int, user_data: dict):
    uid = str(user_id)
    with _lock:
        data = _load()
        data[uid] = user_data
        _save(data)


def get_all_user_ids() -> list:
    with _lock:
        data = _load()
        return list(data.keys())


def get_subscribed_user_ids() -> list:
    with _lock:
        data = _load()
        return [
            uid for uid, u in data.items()
            if u.get("settings", {}).get("live_signals", False)
        ]


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------
def add_to_watchlist(user_id: int, symbol: str, display: str) -> bool:
    user = get_user(user_id)
    if any(item["symbol"] == symbol for item in user["watchlist"]):
        return False
    user["watchlist"].append({"symbol": symbol, "display": display})
    save_user(user_id, user)
    return True


def remove_from_watchlist(user_id: int, symbol: str) -> bool:
    user = get_user(user_id)
    before = len(user["watchlist"])
    user["watchlist"] = [i for i in user["watchlist"] if i["symbol"] != symbol]
    save_user(user_id, user)
    return len(user["watchlist"]) < before


def get_watchlist(user_id: int) -> list:
    return get_user(user_id)["watchlist"]


# ---------------------------------------------------------------------------
# Journal helpers
# ---------------------------------------------------------------------------
def add_journal_entry(user_id: int, entry: dict):
    user = get_user(user_id)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    user["journal"].append(entry)
    save_user(user_id, user)


def get_journal(user_id: int) -> list:
    return get_user(user_id)["journal"]


def clear_journal(user_id: int):
    user = get_user(user_id)
    user["journal"] = []
    save_user(user_id, user)


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------
def update_setting(user_id: int, key: str, value):
    user = get_user(user_id)
    user["settings"][key] = value
    save_user(user_id, user)


def get_settings(user_id: int) -> dict:
    return get_user(user_id)["settings"]
