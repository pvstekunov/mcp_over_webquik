"""Async WebSocket client for webQUIK."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import ssl
import uuid
import zlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import certifi
import websockets
from websockets.client import WebSocketClientProtocol

from .protocol import (
    BOOK_TO_RESPONSE,
    MSG_BOOK_CASH_LIMITS,
    MSG_BOOK_DEPO_LIMITS,
    MSG_BOOK_ORDERS,
    MSG_BOOK_PORTFOLIO,
    MSG_BOOK_QUOTES,
    MSG_BOOK_SECURITY_INFO,
    MSG_BOOK_STOP_ORDERS,
    MSG_BOOK_TRADES,
    MSG_LOGOUT,
    MSG_PIN,
    MSG_STATUS_CHECK,
    RSP_CASH_LIMITS,
    RSP_CLASS_UPDATE,
    RSP_DEPO_LIMITS,
    RSP_KILL_ORDER,
    RSP_LOGIN,
    RSP_ORDERS,
    RSP_PIN,
    RSP_PORTFOLIO,
    RSP_PROFILE_GATEWAY,
    RSP_QUOTES,
    RSP_SECURITY_INFO,
    RSP_SEND_ORDER,
    RSP_STATUS,
    RSP_STOP_ORDERS,
    RSP_TRADES,
    RSP_TRAN_REPLY,
    WS_SUBPROTOCOL,
    build_book,
    build_kill_order,
    build_login,
    build_order,
    build_pin,
    build_quotes,
    build_security_info,
    encode_message,
    extract_msgid,
    parse_message,
)

logger = logging.getLogger(__name__)


def build_ssl_context() -> ssl.SSLContext | None:
    verify = os.environ.get("WEBQUIK_SSL_VERIFY", "true").lower() not in {"0", "false", "no"}
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    ctx = ssl.create_default_context(cafile=certifi.where())
    for extra_ca in _extra_ca_paths():
        ctx.load_verify_locations(cafile=str(extra_ca))
    return ctx


def _extra_ca_paths() -> list[Path]:
    paths: list[Path] = []
    env_ca = os.environ.get("WEBQUIK_CA_BUNDLE")
    if env_ca:
        paths.append(Path(env_ca).expanduser())
    for base in (Path("/app/certs"), Path(__file__).resolve().parents[2] / "certs"):
        for name in ("sberca-chain.pem", "russian-trusted-ca.pem"):
            paths.append(base / name)
    return [p for p in dict.fromkeys(paths) if p.is_file()]

UINT64_FIELDS: dict[int, list[str]] = {
    21002: ["number", "stopnumber", "co_order_num"],
    21003: ["number", "n_order"],
    21009: ["ordernum"],
    21081: ["seq_number", "orderNum", "stopOrderNum"],
}


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    PIN_REQUIRED = "pin_required"


@dataclass
class WebQuikSession:
    host: str = "webquik.sberbank.ru"
    login: str = ""
    sid: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: ConnectionState = ConnectionState.DISCONNECTED
    login_response: dict[str, Any] | None = None
    class_list: list[dict[str, Any]] = field(default_factory=list)
    securities: dict[str, dict[str, Any]] = field(default_factory=dict)
    orders: list[dict[str, Any]] = field(default_factory=list)
    stop_orders: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    cash_limits: list[dict[str, Any]] = field(default_factory=list)
    depo_limits: list[dict[str, Any]] = field(default_factory=list)
    portfolio: list[dict[str, Any]] = field(default_factory=list)
    quotes: dict[str, Any] = field(default_factory=dict)
    security_info: dict[str, Any] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None


class WebQuikClient:
    def __init__(self, host: str = "webquik.sberbank.ru") -> None:
        self.host = host
        self.session = WebQuikSession(host=host)
        self._ws: WebSocketClientProtocol | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._profile_ready = asyncio.Event()
        self._login_event = asyncio.Event()
        self._pin_event = asyncio.Event()
        self._waiters: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    @property
    def ws_url(self) -> str:
        return f"wss://{self.host}/quik"

    async def connect(self) -> None:
        if self._ws and self.session.state not in {
            ConnectionState.DISCONNECTED,
        }:
            return
        self.session.state = ConnectionState.CONNECTING
        self._profile_ready.clear()
        self._login_event.clear()
        self._pin_event.clear()
        self._ws = await websockets.connect(
            self.ws_url,
            subprotocols=[WS_SUBPROTOCOL],
            ping_interval=20,
            ping_timeout=20,
            max_size=16 * 1024 * 1024,
            ssl=build_ssl_context(),
            origin=f"https://{self.host}",
            user_agent_header=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.session.state = ConnectionState.CONNECTED
        self._reader_task = asyncio.create_task(self._read_loop())
        try:
            await asyncio.wait_for(self._profile_ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("Profile gateway message (26000) not received within timeout")

    async def login(self, login: str, password: str, *, lang: str = "ru") -> dict[str, Any]:
        await self.connect()
        assert self._ws is not None
        self.session.login = login
        self._login_event.clear()
        self._pin_event.clear()
        payload = build_login(login, password, sid=self.session.sid, lang=lang)
        await self._send(payload)
        try:
            await asyncio.wait_for(self._login_event.wait(), timeout=60)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Login timed out waiting for server response") from exc

        if self.session.state == ConnectionState.PIN_REQUIRED:
            return {
                "status": "pin_required",
                "message": "SMS/PIN confirmation required. Call submit_pin with the code.",
            }
        if self.session.login_response is None:
            raise RuntimeError(self.session.last_error or "Login failed without response")
        return self._format_login_result(self.session.login_response)

    async def submit_pin(self, pin: str) -> dict[str, Any]:
        if self.session.state != ConnectionState.PIN_REQUIRED:
            raise RuntimeError("PIN is not required in the current session")
        self._pin_event.clear()
        await self._send(build_pin(pin))
        try:
            await asyncio.wait_for(self._pin_event.wait(), timeout=120)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("PIN confirmation timed out") from exc
        if self.session.login_response is None:
            raise RuntimeError(self.session.last_error or "PIN login failed")
        return self._format_login_result(self.session.login_response)

    async def disconnect(self) -> None:
        if self._ws and self.session.state != ConnectionState.DISCONNECTED:
            try:
                await self._send({"msgid": MSG_LOGOUT})
            except Exception:
                logger.debug("Logout send failed", exc_info=True)
        await self._close()

    async def status_check(self) -> dict[str, Any]:
        return await self.request_response(MSG_STATUS_CHECK, {"msgid": MSG_STATUS_CHECK}, RSP_STATUS, timeout=10)

    async def book_orders(self) -> list[dict[str, Any]]:
        await self._send(build_book(MSG_BOOK_ORDERS))
        await asyncio.sleep(0.5)
        return list(self.session.orders)

    async def book_stop_orders(self) -> list[dict[str, Any]]:
        await self._send(build_book(MSG_BOOK_STOP_ORDERS))
        await asyncio.sleep(0.5)
        return list(self.session.stop_orders)

    async def book_trades(self) -> list[dict[str, Any]]:
        await self._send(build_book(MSG_BOOK_TRADES))
        await asyncio.sleep(0.5)
        return list(self.session.trades)

    async def book_portfolio(self) -> list[dict[str, Any]]:
        await self._send(build_book(MSG_BOOK_PORTFOLIO))
        try:
            msg = await self.wait_for_msgid(RSP_PORTFOLIO, timeout=10)
            self._store_portfolio(msg)
        except TimeoutError:
            await asyncio.sleep(0.5)
        return list(self.session.portfolio)

    async def book_limits(self) -> dict[str, list[dict[str, Any]]]:
        await self._send(build_book(MSG_BOOK_CASH_LIMITS))
        await self._send(build_book(MSG_BOOK_DEPO_LIMITS))
        await asyncio.sleep(1.0)
        return {
            "cash": list(self.session.cash_limits),
            "depo": list(self.session.depo_limits),
        }

    async def get_quotes(self, class_code: str, sec_code: str, depth: int = 10) -> dict[str, Any]:
        await self._send(build_quotes(class_code, sec_code, depth))
        msg = await self.wait_for_msgid(RSP_QUOTES, timeout=10)
        key = f"{class_code}|{sec_code}"
        quotes = msg.get("quotes") or msg
        self.session.quotes[key] = quotes
        return quotes if isinstance(quotes, dict) else msg

    async def get_security_info(self, class_code: str, sec_code: str) -> dict[str, Any]:
        await self._send(build_security_info(class_code, sec_code))
        msg = await self.wait_for_msgid(RSP_SECURITY_INFO, timeout=10)
        key = f"{class_code}|{sec_code}"
        self.session.security_info[key] = msg
        return msg

    async def send_order(
        self,
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
        payload = build_order(
            class_code=class_code,
            sec_code=sec_code,
            account=account,
            client_code=client_code,
            quantity=quantity,
            sell=sell,
            is_market=is_market,
            price=price,
        )
        await self._send(payload)
        result_code = await self.wait_for_msgid(RSP_SEND_ORDER, timeout=30)
        return result_code

    async def cancel_order(self, order_number: str | int, class_code: str) -> dict[str, Any]:
        await self._send(build_kill_order(order_number, class_code))
        return await self.wait_for_msgid(RSP_KILL_ORDER, timeout=30)

    async def wait_for_msgid(self, msgid: int, timeout: float = 15.0) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._waiters[msgid] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._waiters.pop(msgid, None)

    async def request_response(
        self,
        request_msgid: int,
        payload: dict[str, Any],
        response_msgid: int,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        await self._send(payload)
        return await self.wait_for_msgid(response_msgid, timeout=timeout)

    def list_classes(self) -> list[dict[str, Any]]:
        return list(self.session.class_list)

    def search_securities(self, query: str, *, class_code: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        q = query.lower()
        results: list[dict[str, Any]] = []
        for cls in self.session.class_list:
            if class_code and cls.get("ccode") != class_code:
                continue
            for sec in cls.get("secList") or []:
                scode = str(sec.get("scode", ""))
                sname = str(sec.get("sname", ""))
                if q in scode.lower() or q in sname.lower():
                    results.append(
                        {
                            "class_code": cls.get("ccode"),
                            "class_name": cls.get("cname"),
                            "sec_code": scode,
                            "sec_name": sname,
                            "lot_size": sec.get("lotsize"),
                            "price_step": sec.get("price_step"),
                        }
                    )
                    if len(results) >= limit:
                        return results
        return results

    def snapshot(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "state": self.session.state.value,
            "login": self.session.login,
            "classes": len(self.session.class_list),
            "orders": len(self.session.orders),
            "trades": len(self.session.trades),
            "portfolio_positions": len(self.session.portfolio),
            "last_error": self.session.last_error,
        }

    async def _send(self, payload: dict[str, Any]) -> None:
        if not self._ws:
            raise RuntimeError("Not connected to webQUIK")
        raw = encode_message(payload)
        async with self._lock:
            await self._ws.send(raw)

    async def _close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
        self.session.state = ConnectionState.DISCONNECTED

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                await self._handle_raw_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.session.last_error = str(exc)
            logger.exception("WebSocket read loop failed")
        finally:
            self.session.state = ConnectionState.DISCONNECTED

    async def _handle_raw_message(self, message: str | bytes) -> None:
        if isinstance(message, bytes):
            text = self._decode_payload(message)
        else:
            text = message
        text = self._fix_uint64_json(text)
        try:
            data = parse_message(text)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to decode webQUIK message: %s", exc)
            return
        await self._dispatch(data)

    def _decode_payload(self, payload: bytes) -> str:
        if payload[:1] == b"{":
            return payload.decode("utf-8", errors="replace")
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                return zlib.decompress(payload, wbits).decode("utf-8", errors="replace")
            except zlib.error:
                continue
        return payload.decode("utf-8", errors="replace")

    def _fix_uint64_json(self, text: str) -> str:
        match = re.search(r'"msgid"\:(\d+)', text)
        if not match:
            return text
        msgid = int(match.group(1))
        fields = UINT64_FIELDS.get(msgid)
        if not fields:
            return text
        pattern = re.compile(rf'((?:{"|".join(fields)})"\:)(\d+)', re.MULTILINE)
        return pattern.sub(r'\1"\2"', text)

    async def _dispatch(self, message: dict[str, Any]) -> None:
        msgid = extract_msgid(message)
        if msgid is None:
            return
        body = {k: v for k, v in message.items() if k != "msgid"}

        if msgid == RSP_PROFILE_GATEWAY:
            self._profile_ready.set()
            return

        if msgid in {RSP_LOGIN, 20006}:
            await self._handle_login(body)
            return

        if msgid == RSP_PIN:
            await self._handle_pin(body)
            return

        if msgid == RSP_CLASS_UPDATE:
            self._store_class_update(body)
            return

        if msgid == RSP_ORDERS:
            self._store_orders(body)
        elif msgid == RSP_STOP_ORDERS:
            self._store_stop_orders(body)
        elif msgid == RSP_TRADES:
            self._store_trades(body)
        elif msgid == RSP_CASH_LIMITS:
            self._store_cash_limits(body)
        elif msgid == RSP_DEPO_LIMITS:
            self._store_depo_limits(body)
        elif msgid == RSP_PORTFOLIO:
            self._store_portfolio(body)
        elif msgid == RSP_QUOTES:
            self._store_quote_update(body)
        elif msgid == RSP_SECURITY_INFO:
            self.session.security_info["_last"] = body
        elif msgid == RSP_TRAN_REPLY:
            self.session.messages.append({"type": "tran_reply", **body})

        future = self._waiters.get(msgid)
        if future and not future.done():
            future.set_result(message)

    async def _handle_login(self, body: dict[str, Any]) -> None:
        result_code = body.get("resultCode")
        auth_mode = body.get("authMode")
        if result_code == 0:
            self.session.login_response = body
            self.session.state = ConnectionState.AUTHENTICATED
            self._store_login_classes(body)
            self._login_event.set()
            self._pin_event.set()
            return
        if auth_mode is not None and result_code not in {2, 3, 4, 5}:
            self.session.state = ConnectionState.PIN_REQUIRED
            self.session.last_error = body.get("serverMessage") or "PIN required"
            self._login_event.set()
            return
        self.session.last_error = body.get("serverMessage") or f"Login failed with resultCode={result_code}"
        self.session.state = ConnectionState.CONNECTED
        self._login_event.set()

    async def _handle_pin(self, body: dict[str, Any]) -> None:
        if body.get("resultCode") == 0:
            self.session.login_response = body
            self.session.state = ConnectionState.AUTHENTICATED
            self._store_login_classes(body)
        else:
            self.session.last_error = body.get("serverMessage") or "PIN rejected"
        self._pin_event.set()

    def _store_login_classes(self, body: dict[str, Any]) -> None:
        classes = body.get("classList") or []
        if classes:
            self.session.class_list = classes
            for cls in classes:
                self._store_class_update({"classList": [cls]})

    def _store_class_update(self, body: dict[str, Any]) -> None:
        for cls in body.get("classList") or []:
            ccode = cls.get("ccode")
            if not ccode:
                continue
            existing = next((c for c in self.session.class_list if c.get("ccode") == ccode), None)
            if existing:
                existing.update(cls)
            else:
                self.session.class_list.append(cls)
            for sec in cls.get("secList") or []:
                scode = sec.get("scode")
                if scode:
                    self.session.securities[f"{ccode}|{scode}"] = sec

    def _store_orders(self, body: dict[str, Any]) -> None:
        rows = body.get("data") or body.get("orders") or [body]
        if isinstance(rows, dict):
            rows = [rows]
        self.session.orders = list(rows)

    def _store_stop_orders(self, body: dict[str, Any]) -> None:
        rows = body.get("data") or body.get("orders") or [body]
        if isinstance(rows, dict):
            rows = [rows]
        self.session.stop_orders = list(rows)

    def _store_trades(self, body: dict[str, Any]) -> None:
        rows = body.get("data") or body.get("trades") or [body]
        if isinstance(rows, dict):
            rows = [rows]
        self.session.trades = list(rows)

    def _store_cash_limits(self, body: dict[str, Any]) -> None:
        rows = body.get("data") or [body]
        if isinstance(rows, dict):
            rows = [rows]
        self.session.cash_limits = list(rows)

    def _store_depo_limits(self, body: dict[str, Any]) -> None:
        rows = body.get("data") or [body]
        if isinstance(rows, dict):
            rows = [rows]
        self.session.depo_limits = list(rows)

    def _store_portfolio(self, body: dict[str, Any]) -> None:
        rows = body.get("data") or body.get("portfolio") or [body]
        if isinstance(rows, dict):
            rows = [rows]
        self.session.portfolio = list(rows)

    def _store_quote_update(self, body: dict[str, Any]) -> None:
        quotes = body.get("quotes")
        if isinstance(quotes, dict):
            self.session.quotes.update(quotes)
        else:
            self.session.quotes["_last"] = body

    def _format_login_result(self, body: dict[str, Any]) -> dict[str, Any]:
        accounts = body.get("trdAccList") or []
        client_codes = body.get("clientCodesList") or []
        return {
            "status": "authenticated",
            "result_code": body.get("resultCode"),
            "trade_session": body.get("tradeSession"),
            "days_before_password_change": body.get("daysBeforePassChange"),
            "classes_count": len(body.get("classList") or self.session.class_list),
            "trading_accounts": accounts,
            "client_codes": client_codes,
            "server_message": body.get("serverMessage"),
        }
