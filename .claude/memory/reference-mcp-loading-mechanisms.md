---
name: MCP Server Loading Mechanisms
description: Four ways MCP servers reach a Claude Code session and which are default
type: reference
originSessionId: 15df376d-717e-44c2-80dc-2b2f2a691595
---
Stock Claude Code CLI ships **zero MCP servers**. None are default. MCP servers reach a session via four distinct mechanisms — knowing which is which matters for L3 baking strategy and devcontainer config:

| Mechanism | Location | Travels with | Notes |
|---|---|---|---|
| Project `.mcp.json` | `<repo>/.mcp.json` (committed) | git repo | Per-project, scoped to that repo only |
| User `.mcp.json` | `~/.claude/.mcp.json` | user home | Global to all projects on this machine |
| Plugin-bundled `.mcp.json` | `<plugin>/.mcp.json` (auto-discovered when plugin enabled) | plugin install | Rides along free with plugin (e.g. postman plugin → postman MCP) |
| claude.ai integrations | claude.ai web account settings (remote OAuth) | auth/account, not container | Names appear as `mcp__claude_ai_<Service>__*` (e.g. Gmail, Google_Drive) |

## Implications for L3 Baking

- Plugin-bundled MCP: free with plugin bake. If `postman` plugin baked into recommended L3, postman MCP comes along.
- Project `.mcp.json`: handled per-build by `/build-stack` (project repo provides it).
- claude.ai MCPs: ride with user's claude.ai auth, not container — present regardless of which container they connect from.
- User `.mcp.json`: not used in this stack (volume-mounted home would persist it but breaks portability).

## Reference Sample (this project)

- `github` MCP — project `.mcp.json` (custom GitHub MCP server binary at `/home/claude/.local/bin/github-mcp-server`)
- `plugin_postman_postman` — postman plugin in claude-plugins-official marketplace
- `claude_ai_Gmail`, `claude_ai_Google_Drive` — user's claude.ai account integrations
