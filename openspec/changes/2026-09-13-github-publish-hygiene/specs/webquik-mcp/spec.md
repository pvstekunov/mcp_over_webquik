# webquik-mcp — Delta Spec

Change: `2026-09-13-github-publish-hygiene`

## ADDED Requirements

### Requirement: Secrets are not published

The repository SHALL ignore local credential and personal-endpoint files so they are not published with the source.

#### Scenario: GitHub publish

- GIVEN a clean working tree prepared for GitHub
- WHEN git status is inspected
- THEN `registry.selectel`, `ingress_host`, `.env`, and `.mcp.json` are untracked
- AND example templates (`registry.selectel.example`, `ingress_host.example`, `.env.example`, `.mcp.json.example`) remain tracked

## MODIFIED Requirements

### Requirement: Kubernetes deployment

The repository SHALL include Kubernetes manifests for Deployment `webquik-mcp` and a ClusterIP Service on port 3001. Image registry, kube context, and namespace SHALL be supplied at deploy time (defaults in `scripts/deploy-k8s.sh`). Registry login credentials SHALL live only in a local file ignored by git.

#### Scenario: In-cluster MCP endpoint

- GIVEN deployment is applied
- WHEN a client calls `http://webquik-mcp.<namespace>.svc.cluster.local:3001/mcp`
- THEN streamable HTTP MCP transport is available

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

### Requirement: WebSocket connection to webQUIK

The system SHALL connect to `wss://{host}/quik` using WebSocket subprotocol `dumb-increment-protocol`, default host `webquik.sberbank.ru`. Binary frames SHALL be decoded as zlib-compressed JSON (wbits=15) with fallback to raw deflate.

#### Scenario: Login response decompression

- GIVEN webQUIK sends a compressed login response (msgid 20000 or 20006)
- WHEN the client receives a binary WebSocket frame with a zlib header
- THEN the payload is decompressed and parsed as JSON
- AND login completes or returns serverMessage without timeout

### Requirement: Market data and portfolio tools

The system SHALL expose MCP tools to read portfolio, orders, trades, limits, and quotes via book/subscribe msgids. Book/subscribe response msgids SHALL be dispatched without crashing the WebSocket read loop.

#### Scenario: Portfolio after login

- GIVEN an authenticated webQUIK session
- WHEN the server sends msgid 21001 (orders) or 21013 (portfolio) updates
- THEN the client dispatches messages without NameError
- AND webquik_get_portfolio returns data
