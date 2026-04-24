# builder-project

Example Layer 4 Claude project demonstrating the multi-project workspace architecture.

This is a sample project repo that can be cloned into `/workspace/claude/project-builder` within a multi-project devcontainer workspace.

## Project Structure

- `.claude/` — Claude Code configuration (settings, rules, commands, skills, agents, memory)
- `CLAUDE.md` — Project-level instructions for Claude
- `.mcp.json` — MCP server configuration

## Usage in Multi-Project Workspace

1. Clone this repo into the workspace:
   ```bash
   git clone https://github.com/sun2admin/builder-project /workspace/claude/project-builder
   ```

2. Container starts and runs `init-projects.sh`, which discovers and syncs all projects

3. In Claude Code, use `/resume` to switch to this project

4. Work on the project with full Claude Code context

## Memory Persistence

Project memory is committed to `.claude/memory/` and seeded on container startup via `init-projects.sh`.

## Documentation

See parent workspace CLAUDE.md for architecture overview and container setup details.
