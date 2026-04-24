---
name: /build-project Skill Design - Key Architectural Decisions
description: Design rationale, key assumptions, and architectural patterns from build-with-claude that should inform /build-project skill. Memory persistence, project structure, multi-project support, containerization patterns.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Core Architectural Insights

### 1. Claude Code Project State is Ephemeral by Default
- Claude stores project state in `~/.claude/projects/<cwd-path>/`
- This location is NOT in the project repo, NOT version controlled, NOT portable
- Without explicit persistence strategy: memory/session data is lost on rebuild or machine switch
- **Solution:** Commit project memory to git and seed on startup via init-memory.sh

### 2. Memory Persistence Improves Project Understanding Over Time
- Claude's auto-memory accumulates learned patterns across sessions
- Compound learning: corrections in session N inform decisions in session N+1
- Without persistence: Claude restarts fresh after each rebuild, loses context
- **Benefit:** Project-specific knowledge becomes embedded in memory, reduces context waste

### 3. Four-Layer Container Architecture Supports Multiple Project Types
- Layer 1 (base-ai-layer): System packages, dev tools, Python, graphics
- Layer 2 (ai-install-layer): Claude/Gemini CLI + user setup
- Layer 3 (plugin containers): Pre-baked Claude Code plugins
- Layer 4 (project repos): Individual projects using Layer 3 images
- **Pattern:** Projects don't define base environment; they reference pre-built images

### 4. Named Volumes for Config Persistence, Bind Mounts for Project Code
- `~/.claude/` in named volume (ephemeral on rebuild, persistent across restarts)
- Project repo in bind mount (survives everything, shared across team)
- Credentials in `/run/credentials/` via init scripts
- init-memory.sh bridges the gap: seeds named volume from git on startup
- **Result:** Container can be rebuilt without losing project memory

### 5. Working Directory (cwd) Determines Project Context
- Claude uses cwd when started to identify the project
- Project config is loaded from cwd and walked up the tree
- Memory is stored under `~/.claude/projects/<cwd-canonicalized>/`
- For multi-project workspaces: each project needs separate cwd and separate postAttachCommand
- **Pattern:** One cwd per Claude session = one project entry = no collision

## What build-with-claude Demonstrates

### Successful Patterns
1. **init-memory.sh** — seed project memory from git on postStartCommand
2. **settings.local.json** — project-specific permissions and config
3. **CLAUDE.md** — team-shared project instructions
4. **/update-build-with-claude skill** — manual sync of memory back to git
5. **Named volume + bind mount separation** — ephemeral state + persistent code
6. **init-*.sh scripts** — SSH, credentials, firewall setup at startup
7. **Test suite + CI/CD** — reproducibility and validation
8. **30+ memory files** — accumulated project knowledge over time

### Why build-with-claude Works
- Memory persists across restarts (named volume)
- Memory survives rebuilds (seeded from git)
- Memory is shared with team (committed to git)
- Project is reproducible (everything in devcontainer.json and init scripts)
- Claude's understanding grows over time (auto-memory + committed learnings)

## Assumptions for /build-project Skill

1. **Memory persistence is valuable** — improves Claude's project understanding
2. **All projects should support it** — not just build-with-claude
3. **Users can opt-out** — if truly don't need memory
4. **Overhead is minimal** — init-memory.sh + sync skill + directory
5. **Pattern is reusable** — same approach works for all project types
6. **Team benefits** — shared learnings across developers

## Open Questions for /build-project Design

1. **Should memory persistence be mandatory or optional?**
   - Current thinking: standard for all project types, but can skip for minimal
   - Alternative: optional addon (Memory/Knowledge addon)

2. **What project types should /build-project support?**
   - Minimal (no extra features)
   - Standard (GitHub MCP, basic setup)
   - Full (all addons: test suite, CI/CD, memory, credentials, etc.)
   - Custom (user picks addons)

3. **What addons should be available?**
   - Browser (Playwright)
   - GitHub MCP
   - SSH/Credentials
   - Test Suite
   - CI/CD Pipeline
   - Memory/Knowledge
   - Documentation
   - Custom Skills

4. **Should /build-project create one project or support scaffolding multiple projects under /workspace/?**
   - Current assumption: one project per scaffold (like /workspace/claude)
   - Alternative: multi-project workspace support (/workspace/project-a, /workspace/project-b)

5. **How should the sync skill be named and implemented?**
   - build-with-claude uses: /update-build-with-claude
   - /build-project could: /update-<project-name> or generic /sync-memory

## Relationship to Container Layers

- **Layer 3 (plugin image)** — /build-project targets these images (e.g., claude-plugins-e47)
- **Layer 4 (project repo)** — /build-project scaffolds these
- **Project selection decides:** which Layer 3 image to use (base, coding, ext, all plugins, custom)
- **AI tool selection decides:** Claude or Gemini (future gemini-plugins)
- **Addon selection decides:** what gets scaffolded in Layer 4

## Next Steps

1. Define project types and addons
2. Decide memory persistence strategy (mandatory vs optional)
3. Design skill workflow (prompts, menus, validation)
4. Create template project structures
5. Implement /build-project skill
6. Test with multiple project types
