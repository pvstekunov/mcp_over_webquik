# webquik-mcp — Delta Spec

Change: `2026-09-13-mcpb-extension`

## ADDED Requirements

### Requirement: MCP Bundle for desktop install

The repository SHALL ship an MCP Bundle (`.mcpb`, legacy alias `.dxt`) built from `extension/manifest.json` via `scripts/pack-mcpb.sh`.

#### Scenario: Pack bundle

- GIVEN source tree with `pyproject.toml`, `src/`, and `certs/`
- WHEN `./scripts/pack-mcpb.sh` runs
- THEN `dist/mcp-over-webquik-{version}.mcpb` and `.dxt` are created

#### Scenario: Claude Desktop install

- GIVEN a user opens the `.mcpb` file in Claude Desktop
- WHEN the extension activates
- THEN a local stdio MCP server runs via UV and exposes webQUIK tools including `login`
