# Proposal: MCP Bundle extension (.mcpb / .dxt)

## Why

Репозиторий содержал MCP-сервер и JSON-конфиги, но не готовый bundle для one-click установки в Claude Desktop и других MCPB-клиентах.

## What

- Добавить `extension/manifest.json` (UV runtime, stdio)
- Скрипт `scripts/pack-mcpb.sh` → `dist/*.mcpb` и legacy `*.dxt`
- Документация в README

## Impact

- **Домен:** `webquik-mcp`
- **Новые артефакты:** `extension/`, `dist/mcp-over-webquik.*`

## Out of scope

- Публикация в MCP marketplace / signing
- HTTP-only bundle (удалённый сервер по-прежнему через `mcp.json`)
