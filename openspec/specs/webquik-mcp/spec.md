# webquik-mcp — Specification

## Purpose

MCP-сервер для программного доступа к торговому терминалу webQUIK Сбербанка (webquik.sberbank.ru) через WebSocket-протокол web2QUIK. Несколько пользователей могут подключаться к одному deployment; у каждого своя сессия webQUIK через tool `login`.

Локальные файлы с секретами и персональными endpoint (`registry.selectel`, `ingress_host`, `.env`, `.mcp.json`) в git не входят.

## Requirements

### Requirement: WebSocket connection to webQUIK

The system SHALL connect to `wss://{host}/quik` using WebSocket subprotocol `dumb-increment-protocol`, default host `webquik.sberbank.ru`. Binary frames SHALL be decoded as zlib-compressed JSON (wbits=15) with fallback to raw deflate.

#### Scenario: Successful connection

- GIVEN the webQUIK server is reachable
- WHEN the client calls connect
- THEN a WebSocket session is established
- AND the client waits for profile gateway message (msgid 26000)

#### Scenario: Login response decompression

- GIVEN webQUIK sends a compressed login response (msgid 20000 or 20006)
- WHEN the client receives a binary WebSocket frame with a zlib header
- THEN the payload is decompressed and parsed as JSON
- AND login completes or returns serverMessage without timeout

### Requirement: Per-MCP-session webQUIK client

The system SHALL maintain a separate webQUIK WebSocket client for each MCP client connection, keyed by MCP session ID (HTTP) or a local key (stdio).

#### Scenario: Two users on one server

- GIVEN two MCP clients connected to the same deployment
- WHEN user A calls login with account A credentials
- AND user B calls login with account B credentials
- THEN each user gets an isolated webQUIK session
- AND portfolio/trading tools for user A use account A only

#### Scenario: Tool without login

- GIVEN an MCP client without a prior login
- WHEN webquik_get_portfolio is called
- THEN the tool fails with a message to call login first

### Requirement: Login tool with user credentials

The system SHALL expose MCP tool `login` with required `login` and `password` arguments. Broker credentials SHALL NOT be read from server environment variables.

#### Scenario: Login success

- GIVEN valid broker credentials passed to login
- WHEN login is called
- THEN the server responds with msgid 20000 and resultCode 0
- AND session state becomes authenticated for this MCP connection

#### Scenario: PIN required

- GIVEN credentials that require SMS confirmation
- WHEN login is called
- THEN the tool returns status pin_required
- AND submit_pin accepts the SMS code via msgid 10001

#### Scenario: Logout

- GIVEN an authenticated MCP session
- WHEN logout is called
- THEN the webQUIK WebSocket is closed
- AND the session entry is removed from SessionStore

### Requirement: Market data and portfolio tools

The system SHALL expose MCP tools to read portfolio, orders, trades, limits, and quotes via book/subscribe msgids. Book/subscribe response msgids SHALL be dispatched without crashing the WebSocket read loop.

#### Scenario: Get portfolio

- GIVEN an authenticated session
- WHEN webquik_get_portfolio is called
- THEN msgid 11013 is sent
- AND portfolio data from msgid 21013 is returned

#### Scenario: Get quotes

- GIVEN an authenticated session
- WHEN webquik_get_quotes is called with class_code and sec_code
- THEN msgid 11014 is sent with depth parameter
- AND quote data is returned

#### Scenario: Portfolio after login

- GIVEN an authenticated webQUIK session
- WHEN the server sends msgid 21001 (orders) or 21013 (portfolio) updates
- THEN the client dispatches messages without NameError
- AND webquik_get_portfolio returns data

### Requirement: Trading operations

The system SHALL expose MCP tools to send and cancel orders via msgid 12000 and 12100.

#### Scenario: Send limit order

- GIVEN an authenticated session
- WHEN webquik_send_order is called with side=buy and order_type=limit
- THEN msgid 12000 is sent with order parameters
- AND result from msgid 22000 is returned

#### Scenario: Cancel order

- GIVEN an active order number
- WHEN webquik_cancel_order is called
- THEN msgid 12100 is sent
- AND result from msgid 22100 is returned

### Requirement: MCP stdio transport

The system SHALL run as an MCP server over stdio for Cursor integration.

#### Scenario: Cursor configuration

- GIVEN pip install -e .
- WHEN Cursor MCP config points to mcp-over-quik command
- THEN tools are discoverable by the agent

### Requirement: MCP streamable HTTP transport

The system SHALL support streamable HTTP transport with stateful sessions (`stateless_http=False`) for remote multi-user access.

#### Scenario: Remote MCP endpoint

- GIVEN deployment exposes port 3001
- WHEN a client connects to `/mcp` over HTTPS
- THEN MCP session ID binds webQUIK SessionStore entries per client

### Requirement: Container image with embedded CA

The Docker image SHALL include Sber CA certificates at `/app/certs/sberca-chain.pem` and set `WEBQUIK_CA_BUNDLE` accordingly.

#### Scenario: TLS to webquik.sberbank.ru from pod

- GIVEN the container runs with the embedded CA bundle
- WHEN the client connects to webquik.sberbank.ru
- THEN SSL verification uses the embedded CA bundle

### Requirement: Kubernetes deployment

The repository SHALL include Kubernetes manifests for Deployment `webquik-mcp` and a ClusterIP Service on port 3001. Image registry, kube context, and namespace SHALL be supplied at deploy time (defaults in `scripts/deploy-k8s.sh`). Registry login credentials SHALL live only in a local file ignored by git (`registry.selectel` with separate `push` and `pull` tokens). Deployment SHALL use imagePullSecret `mcp-over-quik-pull` synced from the `pull` credentials.

#### Scenario: In-cluster MCP endpoint

- GIVEN deployment is applied
- WHEN a client calls `http://webquik-mcp.<namespace>.svc.cluster.local:3001/mcp`
- THEN streamable HTTP MCP transport is available

#### Scenario: Health checks

- GIVEN the pod is running
- WHEN kubelet probes GET /health and /ready
- THEN both return HTTP 200

### Requirement: Public ingress host

The system SHALL be exposable over HTTPS via Ingress class `nginx` with a TLS certificate from cert-manager. The concrete hostname SHALL come from a local `ingress_host` file that is not committed.

#### Scenario: External MCP URL

- GIVEN ingress is applied
- WHEN a client connects to `https://<ingress_host>/mcp`
- THEN streamable HTTP MCP transport is available

### Requirement: Claude Code project MCP config

The repository SHALL include `.mcp.json.example` (and `mcp.json.example`) for Claude Code / Cursor. A local `.mcp.json` MAY exist for the operator and SHALL be gitignored.

#### Scenario: Claude Code opens this repo

- GIVEN Claude Code with project-scoped MCP enabled
- WHEN the user copies `.mcp.json.example` to `.mcp.json` (or downloads config from `/claude/mcp.json`)
- THEN server `webquik` is configured to the chosen MCP endpoint
- AND tools are available after `login`

### Requirement: Claude setup files over HTTP

The Docker image SHALL include static Claude/Cursor config files and expose them at `/claude/*`.

#### Scenario: Download Claude Code config

- GIVEN the deployed MCP service is reachable
- WHEN a client GETs `/claude/mcp.json`
- THEN a valid Claude Code MCP JSON config is returned
- AND the config points to the public `/mcp` endpoint

#### Scenario: File index

- GIVEN the deployed MCP service is reachable
- WHEN a client GETs `/claude/` or `/claude/index.json`
- THEN a manifest lists available setup files and install curl commands

### Requirement: Secrets are not published

The repository SHALL ignore local credential and personal-endpoint files so they are not published with the source.

#### Scenario: GitHub publish

- GIVEN a clean working tree prepared for GitHub
- WHEN git status is inspected
- THEN `registry.selectel`, `ingress_host`, `.env`, and `.mcp.json` are untracked
- AND example templates (`registry.selectel.example`, `ingress_host.example`, `.env.example`, `.mcp.json.example`) remain tracked
