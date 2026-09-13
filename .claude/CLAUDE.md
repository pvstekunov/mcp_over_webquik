# webQUIK MCP

MCP server for Sberbank webQUIK (broker terminal).

## Before trading or portfolio tools

1. Call `login` with the user's broker login and password.
2. If the response is `pin_required`, call `submit_pin` with the SMS code.
3. Use `session_status` to verify the session.

Credentials are **not** stored in this repo or on the MCP server — each user passes them via `login`.

## Common tools

- `login`, `submit_pin`, `logout`, `session_status`
- `webquik_get_portfolio`, `webquik_get_orders`, `webquik_get_quotes`
- `webquik_search_securities`, `webquik_send_order`, `webquik_cancel_order`

## Remote MCP

Default project config: `.mcp.json` → `https://webquik-sber-mcp.petrstekunov.ru/mcp`
