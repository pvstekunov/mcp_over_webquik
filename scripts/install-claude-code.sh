#!/usr/bin/env bash
# Register webquik MCP in Claude Code (project scope).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCOPE="${SCOPE:-project}"
MODE="${MODE:-remote}"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found. Install Claude Code: https://code.claude.com/docs" >&2
  exit 1
fi

case "$MODE" in
  remote)
    JSON='{"type":"http","url":"https://webquik-sber-mcp.petrstekunov.ru/mcp","timeout":120000}'
    claude mcp add-json webquik "$JSON" --scope "$SCOPE"
    ;;
  local)
    BIN="${WEBQUIK_MCP_BIN:-$ROOT/.venv/bin/mcp-over-quik}"
    CA="${WEBQUIK_CA_BUNDLE:-$ROOT/certs/sberca-chain.pem}"
    JSON=$(cat <<EOF
{"command":"$BIN","env":{"WEBQUIK_CA_BUNDLE":"$CA"}}
EOF
)
    claude mcp add-json webquik-local "$JSON" --scope "$SCOPE"
    ;;
  *)
    echo "MODE must be remote or local" >&2
    exit 1
    ;;
esac

echo "Installed. Check: claude mcp list"
