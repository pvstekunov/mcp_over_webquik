# mcp-over-webquik MCP Bundle

One-click install for Claude Desktop and other [MCP Bundle](https://github.com/modelcontextprotocol/mcpb) (`.mcpb` / legacy `.dxt`) clients.

## Build

From repository root:

```bash
./scripts/pack-mcpb.sh
```

Output:

- `dist/mcp-over-webquik.mcpb`
- `dist/mcp-over-webquik.dxt` (same archive, legacy extension)

## Install

1. Open `dist/mcp-over-webquik.mcpb` in Claude Desktop (double-click or drag-and-drop).
2. After install, call tool `login` with broker account (`4…`) and password.
3. If needed, call `submit_pin` with the SMS code.

## Remote HTTP (no bundle)

For Cursor / Claude Code against a hosted server, use HTTP config instead of the bundle — see the main [README](../README.md).
