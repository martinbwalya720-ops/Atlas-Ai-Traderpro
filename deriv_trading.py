"""
Atlas AI Trader PRO - Deriv Trading Execution
Wraps Deriv's *new* Options API for placing Multiplier contracts (leveraged
buy/sell with stop-loss/take-profit attached).

This module is only ever called AFTER the user taps "Approve & Place
Trade" on a proposal shown in Telegram - nothing here runs automatically
without that explicit human confirmation.

Connection flow (per Deriv's current API, confirmed via their support team
in July 2026 - the old shared app_id + token "authorize" flow no longer
works for new Personal Access Tokens):

  1. REST: GET  /trading/v1/options/accounts            -> list accounts
  2. REST: POST /trading/v1/options/accounts/{id}/otp    -> get a ws_url
  3. WS:   connect directly to that ws_url (OTP already embeds identity)
  4. WS:   proposal -> buy                               -> place the trade

Synthetic index price history (used for signal analysis) still uses the
older public, no-auth WebSocket endpoint, which was independently verified
working and is unaffected by the PAT migration.

Safety: before requesting an OTP, we only proceed with an account we can
positively identify as a demo/virtual account from Deriv's account list.
If that can't be confirmed, the trade is refused rather than guessed.
"""

import asyncio
import json
import logging

import pandas as pd
import requests
import websockets

import market_data
from config import (
    DERIV_APP_ID, DERIV_API_TOKEN, DERIV_WS_URL, DERIV_REST_BASE,
    DERIV_MULTIPLIER, SYNTHETIC_GRANULARITY, DEFAULT_TIMEFRAME,
)

logger = logging.getLogger(__name__)


class DerivError(Exception):
    pass


# ---------------------------------------------------------------------------
# REST helpers (run the blocking `requests` calls off the event loop)
# ---------------------------------------------------------------------------

def _auth_headers() -> dict:
    if not DERIV_API_TOKEN:
        raise DerivError("DERIV_API_TOKEN is not set. Add it in your host's environment variables.")
    if not DERIV_APP_ID:
        raise DerivError(
            "DERIV_APP_ID is not set. Register your own app at "
            "home.deriv.com/dashboard/profile -> API Management -> Explore Deriv API -> "
            "Dashboard, then set DERIV_APP_ID to that value (the old shared '1089' no longer works)."
        )
    return {
        "Authorization": f"Bearer {DERIV_API_TOKEN}",
        "Deriv-App-ID": DERIV_APP_ID,
    }


async def _rest_get(path: str) -> requests.Response:
    headers = _auth_headers()
    return await asyncio.to_thread(
        requests.get, DERIV_REST_BASE + path, headers=headers, timeout=15
    )


async def _rest_post(path: str, json_body: dict = None) -> requests.Response:
    headers = _auth_headers()
    return await asyncio.to_thread(
        requests.post, DERIV_REST_BASE + path, headers=headers, json=json_body, timeout=15
    )


def _looks_like_demo(account: dict) -> bool | None:
    """Best-effort check for a demo/virtual account across possible field
    names/shapes Deriv's account list might return. Returns True/False if
    confident, or None if it genuinely can't tell."""
    for key in ("is_virtual", "is_demo"):
        if key in account:
            return bool(account[key])
    text_fields = " ".join(str(v) for v in account.values()).lower()
    if "demo" in text_fields or "virtual" in text_fields:
        return True
    if "real" in text_fields and "demo" not in text_fields:
        return False
    return None


def _extract_account_id(account: dict) -> str:
    for key in ("id", "account_id", "accountId", "loginid", "login_id"):
        if account.get(key):
            return str(account[key])
    return ""


async def _get_ws_url() -> tuple:
    """Discover a demo account and exchange it for a ready-to-use, OTP-
    authenticated WebSocket URL. Returns (ws_url, account_id, currency)."""
    resp = await _rest_get("/trading/v1/options/accounts")
    if resp.status_code != 200:
        raise DerivError(f"Failed to list Deriv accounts: HTTP {resp.status_code} - {resp.text[:300]}")

    try:
        accounts = resp.json().get("data", [])
    except Exception:
        raise DerivError(f"Unexpected response listing accounts: {resp.text[:300]}")

    if not accounts:
        raise DerivError(
            "No trading accounts found on your Deriv profile via the API. "
            "Deriv normally provisions a default demo account automatically - "
            "check home.deriv.com to confirm one exists."
        )

    demo_accounts = [a for a in accounts if _looks_like_demo(a) is True]
    unknown_accounts = [a for a in accounts if _looks_like_demo(a) is None]

    if demo_accounts:
        account = demo_accounts[0]
    elif len(accounts) == 1 and unknown_accounts:
        # Only one account exists and we can't positively confirm it's demo -
        # surface the raw data so we can adjust field-name handling if needed,
        # rather than silently risking a real account.
        raise DerivError(
            "Found exactly one Deriv account but couldn't confirm it's a demo "
            f"account from the API response. Raw account data: {accounts[0]}"
        )
    else:
        raise DerivError(
            f"Could not identify a demo account among {len(accounts)} accounts returned. "
            f"Raw data: {accounts}"
        )

    account_id = _extract_account_id(account)
    if not account_id:
        raise DerivError(f"Could not determine an account ID from Deriv's response: {account}")

    currency = account.get("currency", "USD")

    otp_resp = await _rest_post(f"/trading/v1/options/accounts/{account_id}/otp")
    if otp_resp.status_code != 200:
        raise DerivError(f"Failed to get WebSocket URL: HTTP {otp_resp.status_code} - {otp_resp.text[:300]}")

    try:
        ws_url = otp_resp.json().get("data", {}).get("url")
    except Exception:
        raise DerivError(f"Unexpected response requesting OTP: {otp_resp.text[:300]}")

    if not ws_url:
        raise DerivError(f"Deriv did not return a WebSocket URL: {otp_resp.text[:300]}")

    return ws_url, account_id, currency


async def get_account_info() -> dict:
    """Return basic account info via the new API's account listing."""
    resp = await _rest_get("/trading/v1/options/accounts")
    if resp.status_code != 200:
        raise DerivError(f"Failed to list Deriv accounts: HTTP {resp.status_code} - {resp.text[:300]}")
    accounts = resp.json().get("data", [])
    if not accounts:
        raise DerivError("No trading accounts found.")
    account = accounts[0]
    return {
        "balance": account.get("balance", 0.0),
        "currency": account.get("currency", "USD"),
        "loginid": _extract_account_id(account),
        "is_virtual": bool(_looks_like_demo(account)),
    }


# ---------------------------------------------------------------------------
# Synthetic index price history - unchanged, public endpoint, no auth needed
# ---------------------------------------------------------------------------

async def _fetch_synthetic_candles(symbol: str, granularity: int, count: int = 100) -> list:
    """Pull recent OHLC candles for a synthetic index directly from Deriv.
    No authorization needed - this is public market data on the classic
    endpoint, which remains available independent of the PAT migration."""
    # This is the OLD classic endpoint, used only for public market data.
    # It needs the shared classic app_id (1089), NOT your own registered
    # app - that one is for the new REST+OTP trading API and gets rejected
    # here with an HTTP 401 if used on this legacy endpoint.
    url = DERIV_WS_URL.format(app_id="1089")
    ws = await websockets.connect(url, open_timeout=15, close_timeout=5)
    try:
        req = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": granularity,
        }
        await ws.send(json.dumps(req))
        resp = json.loads(await ws.recv())
        if resp.get("error"):
            raise DerivError(resp["error"].get("message", "Failed to fetch candle history"))
        return resp.get("candles", [])
    finally:
        await ws.close()


def _candles_to_dataframe(candles: list) -> pd.DataFrame:
    return pd.DataFrame({
        "Open": [float(c["open"]) for c in candles],
        "High": [float(c["high"]) for c in candles],
        "Low": [float(c["low"]) for c in candles],
        "Close": [float(c["close"]) for c in candles],
    })


async def get_synthetic_signal(symbol: str, timeframe: str = DEFAULT_TIMEFRAME) -> dict:
    """Fetch a synthetic index's recent candles from Deriv and run the same
    multi-indicator analysis engine used for forex/gold/crypto."""
    granularity = SYNTHETIC_GRANULARITY.get(timeframe, SYNTHETIC_GRANULARITY[DEFAULT_TIMEFRAME])
    try:
        candles = await _fetch_synthetic_candles(symbol, granularity, count=100)
        if not candles:
            return {"error": "No data returned for this synthetic index right now."}
        df = _candles_to_dataframe(candles)
        return market_data.analyze(df)
    except DerivError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("Failed to fetch/analyze synthetic index %s", symbol)
        return {"error": f"Could not fetch data for this index: {type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# Trade execution - new REST + OTP + WebSocket flow
# ---------------------------------------------------------------------------

async def place_multiplier_trade(symbol: str, direction: str, stake: float,
                                  stop_loss: float, take_profit: float,
                                  category: str = "forex") -> dict:
    """
    Place a Deriv 'Multiplier' contract (leveraged, with SL/TP attached),
    using the new account-discovery + OTP + WebSocket flow.

    direction: "BUY" or "SELL"
    Returns: {"success": bool, "contract_id": int|None, "buy_price": float|None,
              "error": str|None, "is_virtual": bool}
    """
    contract_type = "MULTUP" if direction == "BUY" else "MULTDOWN"
    multiplier = DERIV_MULTIPLIER.get(category, DERIV_MULTIPLIER["default"])

    try:
        ws_url, account_id, currency = await _get_ws_url()
    except DerivError as e:
        return {"success": False, "error": str(e), "is_virtual": False, "contract_id": None}

    try:
        ws = await websockets.connect(ws_url, open_timeout=15, close_timeout=5)
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not connect to Deriv's trading WebSocket: {e}",
            "is_virtual": False,
            "contract_id": None,
        }

    try:
        limit_order = {}
        if stop_loss:
            limit_order["stop_loss"] = round(abs(stop_loss), 5)
        if take_profit:
            limit_order["take_profit"] = round(abs(take_profit), 5)

        proposal_req = {
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": currency,
            "underlying_symbol": symbol,
            "multiplier": multiplier,
        }
        if limit_order:
            proposal_req["limit_order"] = limit_order

        await ws.send(json.dumps(proposal_req))
        proposal_resp = json.loads(await ws.recv())

        if proposal_resp.get("error"):
            return {
                "success": False,
                "error": proposal_resp["error"].get("message", "Proposal request failed"),
                "is_virtual": True,
                "contract_id": None,
            }

        proposal = proposal_resp.get("proposal", {})
        proposal_id = proposal.get("id")
        ask_price = proposal.get("ask_price")

        if not proposal_id:
            return {
                "success": False,
                "error": f"Deriv did not return a valid proposal. Response: {proposal_resp}",
                "is_virtual": True,
                "contract_id": None,
            }

        await ws.send(json.dumps({"buy": proposal_id, "price": ask_price}))
        buy_resp = json.loads(await ws.recv())

        if buy_resp.get("error"):
            return {
                "success": False,
                "error": buy_resp["error"].get("message", "Buy request failed"),
                "is_virtual": True,
                "contract_id": None,
            }

        buy = buy_resp.get("buy", {})
        return {
            "success": True,
            "contract_id": buy.get("contract_id"),
            "buy_price": buy.get("buy_price"),
            "account_id": account_id,
            "is_virtual": True,
            "error": None,
        }
    except Exception as e:
        logger.exception("Deriv trade execution failed")
        return {"success": False, "error": str(e), "is_virtual": True, "contract_id": None}
    finally:
        await ws.close()
