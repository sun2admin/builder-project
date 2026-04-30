---
name: /build-project Skill Design - Key Architectural Decisions
description: Design rationale, key assumptions, and architectural patterns that should inform /build-project skill
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
## Core Architectural Insights

### 1. Claude Code Project State is Ephemeral by Default
- Claude stores project state in `~/.claude/projects/<cwd-path>/`
- NOT in the project repo, NOT version controlled, NOT portable
- Without explicit persistence: memory/session data is lost on rebuild
- **Solution:** Commit project memory to git and seed on startup via load-projects.sh

### 2. Memory Persistence Improves Project Understanding Over Time
- Claude's auto-memory accumulates learned patterns across sessions
- Without persistence: Claude restarts fresh after each rebuild, loses context
- **Benefit:** Project-specific knowledge becomes embedded in memory

### 3. Four-Layer Container Architecture Supports Multiple Project Types
- Layer 1 (layer1-ai-depends): System packages, dev tools, Python, graphics
- Layer 2 (layer2-ai-install): Claude/Gemini CLI + user setup
- Layer 3 (plugin containers): Pre-baked Claude Code plugins
- Layer 4 (layer4-devcontainer repos): devcontainer.json + init scripts
- **Pattern:** Project repos don't define base environment; they reference pre-built Layer 3 images

### 4. Named Volumes for Config Persistence, Bind Mounts for Project Code
- `~/.claude/` in named volume (persists across restarts, fresh on rebuild)
- Project repo in bind mount (survives everything)
- Credentials in `/run/credentials/` via init scripts
- **Result:** Container can be rebuilt without losing project memory (seeded from git)

### 5. Working Directory Determines Project Context
- Claude uses cwd when started to identify the project
- Memory stored under `~/.claude/projects/<cwd-canonicalized>/`
- **Pattern:** One cwd per Claude session = one project entry = no collision

## What builder-project Demonstrates

### Successful Patterns
1. **load-projects.sh** — seed project memory from git on postStartCommand
2. **settings.json** — project-specific permissions and config
3. **CLAUDE.md** — team-shared project instructions
4. **/sync-prj-repos-memory skill** — manual sync of memory back to git
5. **Named volume + bind mount separation** — ephemeral state + persistent code
6. **init-*.sh scripts** — SSH, credentials, firewall setup at startup

## Assumptions for /build-project Skill

1. **Memory persistence is valuable** — improves Claude's project understanding
2. **All projects should support it** — not just builder-project
3. **Overhead is minimal** — load-projects.sh + sync skill + directory
4. **Pattern is reusable** — same approach works for all project types

## Open Questions for /build-project Design

1. **Should memory persistence be mandatory or optional?**
2. **What project types should /build-project support?**
   - Minimal / Standard / Full / Custom
3. **What addons should be available?**
   - Browser (Playwright), GitHub MCP, SSH/Credentials, Test Suite, CI/CD, Memory, Custom Skills
4. **Single project or multi-project workspace support?**
5. **How should the sync skill be named?**

## Relationship to Container Layers

- **Layer 3 (plugin image)** — /build-project targets these images (e.g., claude-plugins-3f889e47)
- **Project repos** — /build-project scaffolds these
- **Project selection decides:** which Layer 3 image to reference
- **AI tool selection decides:** Claude or Gemini (future gemini-plugins)
- **Addon selection decides:** what gets scaffolded in the project repo

## Next Steps

1. Define project types and addons
2. Decide memory persistence strategy
3. Design skill workflow (prompts, menus, validation)
4. Create template project structures
5. Implement /build-project skill
6. Test with multiple project types
