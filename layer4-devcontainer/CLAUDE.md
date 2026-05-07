# Layer 4: layer4-devcontainer

**Role**: devcontainer config and init scripts. Sets up the container environment and loads AI project repos.
**Image referenced**: `ghcr.io/sun2admin/claude-plugins-a7f3d2e8:latest` (Layer 3)

This subdir is the reference template for standalone Layer 4 devcontainer repos (e.g. `build-containers-with-claude`).

## devcontainer.json

Key settings:
- `runArgs`: `--cap-add=NET_ADMIN --cap-add=NET_RAW` — required for init-firewall.sh
- `remoteUser`: `claude`
- `containerEnv.TERM=xterm-256color`, `COLORTERM=truecolor` — gives integrated terminal full color/capability set; fixes claude TUI geometry
- **No `postAttachCommand`** — claude is NOT auto-launched. Reason: `postAttachCommand` runs in a raw PTY managed by the remote-container daemon, with no VS Code shell-integration injection — column/resize/Ctrl-L behavior breaks. See `.claude/plans/layer4-terminal-launch-fix.md`.
- Terminal auto-opens via `.vscode/tasks.json` `runOn: folderOpen` instead. Tasks run in the integrated terminal panel (full shell-integration). User types `myclaude` to launch claude.
- `terminal.integrated.profiles.linux.claude-bash` uses `--rcfile /workspace/.devcontainer/scripts/claude-rc.sh` and is set as default profile — every `Ctrl+\`` terminal also gets the `myclaude` alias.

**Named volumes**:
- `claude-code-bashhistory-${devcontainerId}` → `/commandhistory`
- `claude-code-config-${devcontainerId}` → `/home/claude/.claude` (persists Claude state across restarts)

**Bind mounts** (from host `~/Downloads/ClaudeFiles/`):
- `SharedFiles/` → `/home/claude/data`
- `Config/gh_claude_ed25519` → `/run/credentials/gh_claude_ed25519` (readonly)
- `Config/gh_pat` → `/run/credentials/gh_pat` (readonly)

## Init Script Sequence

Run via `postStartCommand` in order:

```
1. sudo /usr/local/bin/init-firewall.sh   ← baked into base image (Layer 1), runs as sudo
2. init-ssh.sh                             ← loads SSH key from /run/credentials/
3. init-gh-token.sh                        ← reads PAT, writes to ~/.profile (chmod 600)
4. init-github-mcp.sh                      ← copies arch-appropriate MCP binary to ~/.local/bin/
5. load-projects.sh -live sun2admin/builder-project  ← clones project repo, seeds memory
```

## Init Scripts

**`init-ssh.sh`**: Copies SSH key from `/run/credentials/gh_claude_ed25519`, starts ssh-agent at fixed socket `/home/claude/.ssh/agent.sock`, loads key, adds github.com to known_hosts.

**`init-gh-token.sh`**: Reads PAT from `/run/credentials/gh_pat`, writes `GH_TOKEN` and `GITHUB_PERSONAL_ACCESS_TOKEN` to `~/.profile` (chmod 600). NOT written to `/etc/environment` (world-readable) or `.bashrc` (not sourced by subprocesses).

**`init-github-mcp.sh`**: Detects arch (x86_64/aarch64), copies the appropriate binary from `scripts/opt/` to `/home/claude/.local/bin/github-mcp-server`.

**`load-projects.sh`**: Clones project repos into `/workspace/claude/<repo-name>`. The `-live` flag designates the primary project — seeds memory from `.claude/memory/` into the named volume, writes path to `~/live-project`.

**`claude-rc.sh`**: Custom rcfile sourced by the integrated terminal (both auto-open task and any `Ctrl+\`` shells). Sources `~/.bashrc` + `~/.profile`, then defines:
```bash
alias myclaude='cd $(cat ~/live-project 2>/dev/null || echo ~) && claude --dangerously-skip-permissions'
```
User types `myclaude` to launch claude pinned to the live project.

## MCP Binary

`scripts/opt/` contains pre-built GitHub MCP server binaries:
- `github-mcp-server-linux-amd64`
- `github-mcp-server-linux-arm64`
- `VERSION` — tracks current binary version

Updated weekly via `update-github-mcp.yml` GitHub Actions workflow.

## Project Repos

Project repos (e.g. `builder-project`) are separate standalone repos cloned by `load-projects.sh` at container start into `/workspace/claude/<name>`. They contain only Claude/AI project files and have no role in the container architecture.
