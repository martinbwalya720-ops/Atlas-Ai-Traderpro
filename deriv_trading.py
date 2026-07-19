"""
Atlas AI Trader PRO - Deriv Trading Execution
Thin async wrapper around Deriv's WebSocket API for placing "Multiplier"
contracts (leveraged buy/sell with stop-loss/take-profit attached).

This module is only ever called AFTER the user taps "Approve & Place
Trade" on a proposal shown in Telegram - nothing here runs automatically
without that explicit human confirmation.

Safety: before placing any order, we verify the authorized account is
flagged as a DEMO (virtual-money) account by Deriv itself. If the token
turns out to belong to a real-money account, the trade is refused.
"""

import json
import logging

import websockets

from config import DERIV_APP_ID, DERIV_API_TOKEN, DERIV_WS_URL, DERIV_MULTIPLIER

logger = logging.getLogger(__name__)


class DerivError(Exception):
    pass


async def _connect_and_authorize():
    if not DERIV_API_TOKEN:
        raise DerivError("DERIV_API_TOKEN is not set. Add it in your host's environment variables.")

    url = DERIV_WS_URL.format(app_id=DERIV_APP_ID)
    ws = await websockets.connect(url, open_timeout=15, close_timeout=5)
    await ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
    resp = json.loads(await ws.recv())
    if resp.get("error"):
        await ws.close()
        raise DerivError(resp["error"].get("message", "Authorization failed"))
    return ws, resp.get("authorize", {})


async def get_account_info() -> dict:
    """Return basic account info: balance, currency, is_virtual, loginid."""
    ws, auth = await _connect_and_authorize()
    try:
        return {
            "balance": auth.get("balance", 0.0),
            "currency": auth.get("currency", "USD"),
            "loginid": auth.get("loginid", ""),
            "is_virtual": bool(auth.get("is_virtual", 0)),
        }
    finally:
        await ws.close()


async def place_multiplier_trade(symbol: str, direction: str, stake: float,
                                  stop_loss: float, take_profit: float,
                                  category: str = "forex") -> dict:
    """
    Place a Deriv 'Multiplier' contract (leveraged, with SL/TP attached).

    direction: "BUY" or "SELL"
    Returns: {"success": bool, "contract_id": int|None, "buy_price": float|None,
              "longcode": str, "error": str|None, "is_virtual": bool}
    """
    contract_type = "MULTUP" if direction == "BUY" else "MULTDOWN"
    multiplier = DERIV_MULTIPLIER.get(category, DERIV_MULTIPLIER["default"])

    try:
        ws, auth = await _connect_and_authorize()
    except DerivError as e:
        return {"success": False, "error": str(e), "is_virtual": False, "contract_id": None}

    is_virtual = bool(auth.get("is_virtual", 0))

    # Hard safety check: refuse to trade unless this is confirmed a demo account.
    if not is_virtual:
        await ws.close()
        return {
            "success": False,
            "error": "SAFETY ABORT: this API token belongs to a REAL-money account, "
                     "not a demo account. No trade was placed.",
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
            "currency": auth.get("currency", "USD"),
            "symbol": symbol,
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
                "is_virtual": is_virtual,
                "contract_id": None,
            }

        proposal = proposal_resp.get("proposal", {})
        proposal_id = proposal.get("id")
        ask_price = proposal.get("ask_price")

        if not proposal_id:
            return {
                "success": False,
                "error": "Deriv did not return a valid proposal for this symbol/parameters.",
                "is_virtual": is_virtual,
                "contract_id": None,
            }

        await ws.send(json.dumps({"buy": proposal_id, "price": ask_price}))
        buy_resp = json.loads(await ws.recv())

        if buy_resp.get("error"):
            return {
                "success": False,
                "error": buy_resp["error"].get("message", "Buy request failed"),
                "is_virtual": is_virtual,
                "contract_id": None,
            }

        buy = buy_resp.get("buy", {})
        return {
            "success": True,
            "contract_id": buy.get("contract_id"),
            "buy_price": buy.get("buy_price"),
            "longcode": buy.get("longcode", ""),
            "is_virtual": is_virtual,
            "error": None,
        }
    except Exception as e:
        logger.exception("Deriv trade execution failed")
        return {"success": False, "error": str(e), "is_virtual": is_virtual, "contract_id": None}
    finally:
        await ws.close()
