#!/usr/bin/env bash
# Pack mcp-over-webquik as .mcpb (and legacy .dxt) for Claude Desktop / MCPB clients.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGING="$(mktemp -d)"
VERSION="$(grep '^version' "$ROOT/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')"
OUT_DIR="$ROOT/dist"
BASENAME="mcp-over-webquik-${VERSION}"

cleanup() {
  rm -rf "$STAGING"
}
trap cleanup EXIT

mkdir -p "$OUT_DIR"

echo "Staging bundle in $STAGING..."
cp "$ROOT/extension/manifest.json" "$STAGING/"
cp "$ROOT/extension/.mcpbignore" "$STAGING/"
cp "$ROOT/extension/README.md" "$STAGING/"
cp "$ROOT/pyproject.toml" "$STAGING/"
cp "$ROOT/README.md" "$STAGING/PROJECT_README.md"
cp -R "$ROOT/src" "$STAGING/"
cp -R "$ROOT/certs" "$STAGING/"

if command -v npx >/dev/null 2>&1; then
  echo "Packing with @anthropic-ai/mcpb..."
  npx --yes @anthropic-ai/mcpb@latest validate "$STAGING"
  npx --yes @anthropic-ai/mcpb@latest pack "$STAGING" "$OUT_DIR/${BASENAME}.mcpb"
else
  echo "npx not found; packing with zip..."
  (cd "$STAGING" && zip -qr "$OUT_DIR/${BASENAME}.mcpb" .)
fi

cp "$OUT_DIR/${BASENAME}.mcpb" "$OUT_DIR/${BASENAME}.dxt"
rm -f "$OUT_DIR/mcp-over-webquik.mcpb" "$OUT_DIR/mcp-over-webquik.dxt"
cp "$OUT_DIR/${BASENAME}.mcpb" "$OUT_DIR/mcp-over-webquik.mcpb"
cp "$OUT_DIR/${BASENAME}.dxt" "$OUT_DIR/mcp-over-webquik.dxt"

echo "Built:"
echo "  $OUT_DIR/${BASENAME}.mcpb"
echo "  $OUT_DIR/${BASENAME}.dxt"
echo "  $OUT_DIR/mcp-over-webquik.mcpb"
