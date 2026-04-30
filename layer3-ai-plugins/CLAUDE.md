# Layer 3: Plugin Containers

**Base for all**: `ghcr.io/sun2admin/layer2-ai-install:claude`

## Purpose

Pre-bakes Claude Code plugins into container images so plugins are available at startup without download or auth. Eliminates plugin discovery latency at runtime.

## How Plugin Baking Works

At Docker build time:
1. `claude plugin marketplace add <source>` — registers plugin source
2. `claude plugin install <plugin>` — downloads and installs plugin
3. `CLAUDE_CODE_PLUGIN_CACHE_DIR` — points to baked plugin cache dir
4. `CLAUDE_CODE_PLUGIN_SEED_DIR` — Claude Code seeds from this dir at startup

Plugins cached at `/opt/claude-custom-plugins` inside the image.

## Plugin Containers

| Image | Contents |
|---|---|
| `claude-anthropic-base-plugins-container` | 10 base plugins (any project) |
| `claude-anthropic-coding-plugins-container` | 10 base + 22 coding plugins |
| `claude-anthropic-ext-plugins-container` | 10 base + 15 external plugins |
| `claude-anthropic-all-plugins-container` | 10 base + 22 coding + 15 external (47 total) |
| `claude-plugins-a7f3d2e8` | build-with-claude variant (18 plugins) |
| `claude-plugins-3f889e47` | base + document-skills (11 plugins) |
| `claude-plugins-34e199d2` | base + document-skills + 15 external (26 plugins) |
| `claude-plugins-54ca621f` | base + external subset |

## Marketplace Sources

- `anthropics/claude-plugins-official` — base, coding, and external_plugins/
- `anthropics/skills` — only `document-skills` available in anthropic-agent-skills namespace

## Managing Plugin Layers

Use the `/new-plugin-layer` skill (`.claude/skills/new-plugin-layer/`) to create, search, and manage plugin layer configurations.

Plugin definitions are tracked in `standards.json` (built images) and `plugin-lists.json` (plugin selections).

## Key Constraints

- All GHCR images must be private
- Source files for individual plugin containers live in their own GitHub repos, not in this subdir
- Rebuilding requires rebuilding when Layer 2 (layer2-ai-install) changes
