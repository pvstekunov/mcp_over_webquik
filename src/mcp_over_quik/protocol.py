"""webQUIK WebSocket protocol constants and message builders.

Reverse-engineered from webquik.sberbank.ru client JS (v7.14.3).
Endpoint: wss://{host}/quik, subprotocol: dumb-increment-protocol
"""

from __future__ import annotations

import json
import platform
import uuid
from datetime import datetime, timezone
from typing import Any

WEBQUIK_VERSION = "7.14.3"
DEFAULT_HOST = "webquik.sberbank.ru"
WS_SUBPROTOCOL = "dumb-increment-protocol"

# Client -> server
MSG_LOGIN = 10000
MSG_PIN = 10001
MSG_CHANGE_PASSWORD = 10003
MSG_PAUSE = 10004
MSG_LOGOUT = 10006
MSG_STATUS_CHECK = 10008
MSG_BOOK_ORDERS = 11001
MSG_BOOK_STOP_ORDERS = 11002
MSG_BOOK_TRADES = 11003
MSG_BOOK_CASH_LIMITS = 11004
MSG_BOOK_DEPO_LIMITS = 11005
MSG_BOOK_FUT_LIMITS = 11006
MSG_BOOK_FUT_POS = 11007
MSG_BOOK_PORTFOLIO = 11013
MSG_BOOK_QUOTES = 11014
MSG_BOOK_SECURITY_INFO = 11020
MSG_SEND_ORDER = 12000
MSG_SEND_STOP_ORDER = 12001
MSG_KILL_ORDER = 12100
MSG_KILL_STOP_ORDER = 12101

# Server -> client
RSP_LOGIN = 20000
RSP_PIN = 20001
RSP_STATUS = 20008
RSP_CLASS_UPDATE = 21000
RSP_ORDERS = 21001
RSP_STOP_ORDERS = 21002
RSP_TRADES = 21003
RSP_CASH_LIMITS = 21004
RSP_DEPO_LIMITS = 21005
RSP_FUT_LIMITS = 21006
RSP_FUT_POS = 21007
RSP_TRAN_REPLY = 21009
RSP_PORTFOLIO = 21013
RSP_QUOTES = 21014
RSP_SECURITY_INFO = 21020
RSP_SEND_ORDER = 22000
RSP_KILL_ORDER = 22100
RSP_PROFILE_GATEWAY = 26000

BOOK_TO_RESPONSE = {
    MSG_BOOK_ORDERS: RSP_ORDERS,
    MSG_BOOK_STOP_ORDERS: RSP_STOP_ORDERS,
    MSG_BOOK_TRADES: RSP_TRADES,
    MSG_BOOK_CASH_LIMITS: RSP_CASH_LIMITS,
    MSG_BOOK_DEPO_LIMITS: RSP_DEPO_LIMITS,
    MSG_BOOK_FUT_LIMITS: RSP_FUT_LIMITS,
    MSG_BOOK_FUT_POS: RSP_FUT_POS,
    MSG_BOOK_PORTFOLIO: RSP_PORTFOLIO,
    MSG_BOOK_QUOTES: RSP_QUOTES,
    MSG_BOOK_SECURITY_INFO: RSP_SECURITY_INFO,
}


def _device_desc() -> str:
    sep = "%%"
    now = datetime.now(timezone.utc).strftime("%A %Y-%m-%d %H:%M:%S.%f GMT%z")
    return (
        f"SYSTEM={platform.system()}{sep}"
        f"OS-VERSION={platform.release()}{sep}"
        f"LOCAL_TIME={now}{sep}"
        f"USER_LOCAL_INFO=en"
    )


def build_login(
    login: str,
    password: str,
    *,
    sid: str | None = None,
    lang: str = "ru",
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Any]:
    return {
        "msgid": MSG_LOGIN,
        "classes": [],
        "login": login,
        "password": password,
        "btc": "true",
        "width": str(width),
        "height": str(height),
        "compressed": "deflate",
        "app_type": "WEB",
        "userAgent": "mcp-over-quik/0.1.0",
        "lang": lang,
        "sid": sid or str(uuid.uuid4()),
        "version": WEBQUIK_VERSION,
        "device_desc": _device_desc(),
        "ccodeOnDepo": "true",
    }


def build_pin(pin: str) -> dict[str, Any]:
    return {"msgid": MSG_PIN, "pin": pin}


def build_book(msgid: int, **extra: Any) -> dict[str, Any]:
    return {"msgid": msgid, **extra}


def build_quotes(class_code: str, sec_code: str, depth: int = 10) -> dict[str, Any]:
    return {
        "msgid": MSG_BOOK_QUOTES,
        "c": class_code,
        "s": sec_code,
        "depth": depth,
    }


def build_security_info(class_code: str, sec_code: str) -> dict[str, Any]:
    return {
        "msgid": MSG_BOOK_SECURITY_INFO,
        "ccode": class_code,
        "scode": sec_code,
    }


def build_order(
    *,
    class_code: str,
    sec_code: str,
    account: str,
    client_code: str,
    quantity: float | int | str,
    sell: bool = False,
    is_market: bool = False,
    price: str | float = "0.0",
) -> dict[str, Any]:
    return {
        "msgid": MSG_SEND_ORDER,
        "isStop": 0,
        "ccode": class_code,
        "scode": sec_code,
        "account": account,
        "clientCode": client_code,
        "sell": sell,
        "quantity": quantity,
        "isMarket": 1 if is_market else 0,
        "price": str(price),
    }


def build_kill_order(order_number: str | int, class_code: str) -> dict[str, Any]:
    return {
        "msgid": MSG_KILL_ORDER,
        "number": order_number,
        "ccode": class_code,
    }


def encode_message(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_message(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object from webQUIK")
    return data


def extract_msgid(message: dict[str, Any]) -> int | None:
    msgid = message.get("msgid")
    if msgid is None:
        return None
    return int(msgid)
