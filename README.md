# mcp-over-quik

MCP-сервер для торгового терминала **webQUIK** Сбербанка ([webquik.sberbank.ru](https://webquik.sberbank.ru/)).

Позволяет AI-агентам в Cursor подключаться к webQUIK по WebSocket-протоколу: смотреть портфель, котировки, заявки и выставлять ордера.

Каждый MCP-клиент (каждый пользователь Cursor) получает **отдельную сессию** webQUIK — логин и пароль передаются через tool `login`, а не хранятся в конфиге сервера.

## Требования

- Python 3.11+
- Брокерский счёт Сбербанка с доступом к webQUIK
- Логин — номер брокерского счёта (начинается с `4`)

## Установка

```bash
cd mcp_over_quik
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Настройка Cursor (локально, stdio)

```json
{
  "mcpServers": {
    "webquik": {
      "command": "/absolute/path/to/mcp_over_quik/.venv/bin/mcp-over-quik"
    }
  }
}
```

## Настройка Cursor (удалённый сервер, HTTP)

```json
{
  "mcpServers": {
    "webquik": {
      "url": "https://webquik-sber-mcp.petrstekunov.ru/mcp"
    }
  }
}
```

## Установка расширения (.mcpb / .dxt)

One-click bundle для Claude Desktop и других MCPB-клиентов ([формат MCP Bundle](https://github.com/modelcontextprotocol/mcpb)):

```bash
./scripts/pack-mcpb.sh
```

Готовые файлы:

- [`dist/mcp-over-webquik.mcpb`](dist/mcp-over-webquik.mcpb) — текущая версия
- [`dist/mcp-over-webquik.dxt`](dist/mcp-over-webquik.dxt) — то же самое (legacy-имя)

Откройте `.mcpb` в Claude Desktop (двойной клик или перетаскивание). После установки вызовите `login`, затем при необходимости `submit_pin`.

Исходники манифеста: [`extension/manifest.json`](extension/manifest.json).

## Настройка Claude Code

Скачать конфиг с сервера:

```bash
curl -fsSL https://webquik-sber-mcp.petrstekunov.ru/claude/mcp.json -o .mcp.json
curl -fsSL https://webquik-sber-mcp.petrstekunov.ru/claude/CLAUDE.md -o .claude/CLAUDE.md
```

Каталог файлов: https://webquik-sber-mcp.petrstekunov.ru/claude/

В репозитории уже есть project-scoped конфиг [`.mcp.json`](.mcp.json) — Claude Code подхватит его автоматически в этом проекте.

Или установить вручную:

```bash
claude mcp add-json webquik '{"type":"http","url":"https://webquik-sber-mcp.petrstekunov.ru/mcp","timeout":120000}' --scope project
```

Локальный stdio-сервер (без k8s):

```bash
MODE=local ./scripts/install-claude-code.sh
```

Проверка: `claude mcp list` → `/mcp` в сессии Claude Code.

Инструкции для агента: [`.claude/CLAUDE.md`](.claude/CLAUDE.md)

После подключения **обязательно** вызовите `login` с логином и паролем своего брокерского счёта.

## Инструменты (tools)

| Tool | Описание |
|------|----------|
| `login` | Вход в webQUIK (логин + пароль пользователя) |
| `submit_pin` | Ввод SMS/PIN-кода |
| `logout` | Выход и удаление сессии |
| `session_status` | Статус сессии текущего MCP-клиента |
| `webquik_list_classes` | Список классов инструментов |
| `webquik_search_securities` | Поиск бумаг |
| `webquik_get_portfolio` | Портфель |
| `webquik_get_orders` | Активные заявки |
| `webquik_get_trades` | Сделки |
| `webquik_get_limits` | Лимиты по деньгам и бумагам |
| `webquik_get_quotes` | Стакан котировок |
| `webquik_get_security_info` | Параметры инструмента |
| `webquik_send_order` | Выставить заявку |
| `webquik_cancel_order` | Снять заявку |

## Пример сценария

1. `login` login=`4XXXXXXXXXX`, password=`...` — вход (может вернуть `pin_required`)
2. `submit_pin` pin=`123456` — если нужен SMS-код
3. `webquik_search_securities` query=`SBER`
4. `webquik_get_quotes` class_code=`TQBR`, sec_code=`SBER`
5. `webquik_send_order` — лимитная или рыночная заявка
6. `logout` — завершить сессию

## Мультипользовательский режим

На одном MCP-сервере могут работать несколько пользователей одновременно. Сессии изолированы по MCP session ID (HTTP transport) или по локальному подключению (stdio). У каждого пользователя свой счёт webQUIK — credentials не хранятся в deployment/env сервера.

## Протокол

Клиент подключается к `wss://webquik.sberbank.ru/quik` с subprotocol `dumb-increment-protocol` и обменивается JSON-сообщениями с полем `msgid` (как браузерный webQUIK 7.14).

## SSL / сертификаты

webquik.sberbank.ru использует корпоративный CA. Если подключение падает с `CERTIFICATE_VERIFY_FAILED`:

1. Положите CA-цепочку в `certs/sberca-chain.pem` или задайте `WEBQUIK_CA_BUNDLE`
2. Для локальной отладки: `WEBQUIK_SSL_VERIFY=false`

## Безопасность

- Пароли передаются только в tool `login` и не сохраняются в конфиге сервера
- Торговые операции могут требовать SMS-подтверждение
- Используйте на свой риск; автор не несёт ответственности за торговые решения

## Лицензия

MIT
