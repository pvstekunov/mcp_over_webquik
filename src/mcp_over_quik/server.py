"""MCP server exposing webQUIK (webquik.sberbank.ru) to AI agents."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .client import ConnectionState, WebQuikClient
from .downloads import register_claude_download_routes
from .sessions import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_server: MCPServer):
    store = SessionStore()
    yield {"store": store}


mcp = MCPServer(
    "webquik",
    instructions=(
        "MCP server for Sberbank webQUIK trading terminal (webquik.sberbank.ru). "
        "Each MCP client connection has its own session. "
        "Always call login(login, password) first to open a personal webQUIK session. "
        "If login returns pin_required, call submit_pin. "
        "Use logout when finished."
    ),
    lifespan=_lifespan,
)

_STORE_KEY = "store"


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _webquik_host() -> str:
    return os.environ.get("WEBQUIK_HOST", "webquik.sberbank.ru")


def _session_key(ctx: Context) -> str:
    session = ctx.request_context.session
    connection = session._connection  # noqa: SLF001 — MCP session id lives on Connection
    if connection.session_id:
        return connection.session_id
    return "local"


def _store(ctx: Context) -> SessionStore:
    lifespan = ctx.request_context.lifespan_context
    if not isinstance(lifespan, dict) or _STORE_KEY not in lifespan:
        raise RuntimeError("Session store is not initialized")
    return lifespan[_STORE_KEY]


async def _client_for(ctx: Context) -> WebQuikClient:
    store = _store(ctx)
    key = _session_key(ctx)
    await store.touch(key)
    return await store.require(key)


def _require_auth(client: WebQuikClient) -> None:
    if client.session.state != ConnectionState.AUTHENTICATED:
        raise RuntimeError(
            "Not authenticated. Call login first "
            f"(current state: {client.session.state.value})."
        )


@mcp.tool()
async def login(
    login: str,
    password: str,
    ctx: Context,
    lang: str = "ru",
) -> str:
    """Create a personal webQUIK session for this MCP connection.

    Required before any trading or market-data tools. Each user connects with
    their own broker account (login starts with 4). Returns pin_required if
    SMS confirmation is needed — then call submit_pin.
    """
    store = _store(ctx)
    key = _session_key(ctx)
    client = await store.replace(key, _webquik_host())
    result = await client.login(login, password, lang=lang)
    result["session_key"] = key
    return _json(result)


@mcp.tool()
async def submit_pin(pin: str, ctx: Context) -> str:
    """Submit SMS/PIN code after login returned pin_required."""
    client = await _client_for(ctx)
    if client.session.state != ConnectionState.PIN_REQUIRED:
        raise RuntimeError("PIN is not required for the current session")
    result = await client.submit_pin(pin)
    result["session_key"] = _session_key(ctx)
    return _json(result)


@mcp.tool()
async def logout(ctx: Context) -> str:
    """Logout from webQUIK and remove this MCP connection's session."""
    store = _store(ctx)
    key = _session_key(ctx)
    removed = await store.remove(key)
    return _json({"status": "disconnected", "session_key": key, "had_session": removed})


@mcp.tool()
async def session_status(ctx: Context) -> str:
    """Return this MCP connection's webQUIK session state."""
    store = _store(ctx)
    key = _session_key(ctx)
    client = await store.get(key)
    snapshot: dict[str, Any] = {
        "session_key": key,
        "has_session": client is not None,
        "store": store.stats(),
    }
    if client is None:
        snapshot["state"] = "no_session"
        return _json(snapshot)

    snapshot.update(client.snapshot())
    try:
        if client.session.state == ConnectionState.AUTHENTICATED:
            snapshot["ping"] = await client.status_check()
    except Exception as exc:
        snapshot["ping_error"] = str(exc)
    return _json(snapshot)


@mcp.tool()
async def webquik_list_classes(ctx: Context) -> str:
    """List instrument classes available after login (e.g. TQBR for MOEX equities)."""
    client = await _client_for(ctx)
    _require_auth(client)
    classes = [
        {
            "class_code": c.get("ccode"),
            "class_name": c.get("cname"),
            "securities_count": len(c.get("secList") or []),
        }
        for c in client.list_classes()
    ]
    return _json(classes)


@mcp.tool()
async def webquik_search_securities(
    query: str,
    ctx: Context,
    class_code: str | None = None,
    limit: int = 30,
) -> str:
    """Search securities by ticker or name within loaded class lists."""
    client = await _client_for(ctx)
    _require_auth(client)
    return _json(client.search_securities(query, class_code=class_code, limit=limit))


@mcp.tool()
async def webquik_get_portfolio(ctx: Context) -> str:
    """Subscribe to and return client portfolio positions."""
    client = await _client_for(ctx)
    _require_auth(client)
    portfolio = await client.book_portfolio()
    return _json(portfolio)


@mcp.tool()
async def webquik_get_orders(
    ctx: Context,
    include_stop_orders: bool = True,
) -> str:
    """Subscribe to and return active orders."""
    client = await _client_for(ctx)
    _require_auth(client)
    orders = await client.book_orders()
    result: dict[str, Any] = {"orders": orders}
    if include_stop_orders:
        result["stop_orders"] = await client.book_stop_orders()
    return _json(result)


@mcp.tool()
async def webquik_get_trades(ctx: Context) -> str:
    """Subscribe to and return recent trades."""
    client = await _client_for(ctx)
    _require_auth(client)
    trades = await client.book_trades()
    return _json(trades)


@mcp.tool()
async def webquik_get_limits(ctx: Context) -> str:
    """Return cash and depo limits."""
    client = await _client_for(ctx)
    _require_auth(client)
    limits = await client.book_limits()
    return _json(limits)


@mcp.tool()
async def webquik_get_quotes(
    class_code: str,
    sec_code: str,
    ctx: Context,
    depth: int = 10,
) -> str:
    """Get order book quotes for an instrument (e.g. class_code=TQBR, sec_code=SBER)."""
    client = await _client_for(ctx)
    _require_auth(client)
    quotes = await client.get_quotes(class_code, sec_code, depth=depth)
    return _json(quotes)


@mcp.tool()
async def webquik_get_security_info(
    class_code: str,
    sec_code: str,
    ctx: Context,
) -> str:
    """Get static parameters for a security (lot size, price step, etc.)."""
    client = await _client_for(ctx)
    _require_auth(client)
    info = await client.get_security_info(class_code, sec_code)
    return _json(info)


@mcp.tool()
async def webquik_send_order(
    class_code: str,
    sec_code: str,
    account: str,
    client_code: str,
    quantity: float,
    ctx: Context,
    side: str = "buy",
    order_type: str = "limit",
    price: float = 0.0,
) -> str:
    """Place a new order on MOEX via webQUIK.

    side: buy | sell
    order_type: limit | market
    account: trading account (e.g. L01-00000F00)
    client_code: broker client code
    """
    client = await _client_for(ctx)
    _require_auth(client)
    sell = side.lower() in {"sell", "s", "short"}
    is_market = order_type.lower() == "market"
    result = await client.send_order(
        class_code=class_code,
        sec_code=sec_code,
        account=account,
        client_code=client_code,
        quantity=quantity,
        sell=sell,
        is_market=is_market,
        price=price,
    )
    return _json(result)


@mcp.tool()
async def webquik_cancel_order(
    order_number: str,
    class_code: str,
    ctx: Context,
) -> str:
    """Cancel an active order by order number and class code."""
    client = await _client_for(ctx)
    _require_auth(client)
    result = await client.cancel_order(order_number, class_code)
    return _json(result)


register_claude_download_routes(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> Response:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/ready", methods=["GET"])
async def ready_check(_request: Request) -> Response:
    return JSONResponse({"status": "ready"})


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "3001"))
        mcp.run(transport="streamable-http", host=host, port=port, stateless_http=False)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
