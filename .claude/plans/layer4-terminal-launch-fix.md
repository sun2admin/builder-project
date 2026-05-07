# Plan Note: Layer 4 Terminal Launch / Geometry Fix

**Status:** Fix applied to `layer4-devcontainer/` template 2026-05-07. Awaits validation in test repo `sun2admin/build-stack-with-claude` (newly created — `build-containers-with-claude` deliberately untouched until validation passes).
**Repo affected (template):** `builder-project/layer4-devcontainer/` — single source of truth.
**Repo affected (test consumer):** `sun2admin/build-stack-with-claude` (private, created 2026-05-07 alongside this fix).
**Repo affected (production consumer, deferred):** `build-containers-with-claude` — patch only after `build-stack-with-claude` confirms TTY behavior is correct.
**Stopgap attempted (2026-05-07, REVERTED same day):** `"tui": "fullscreen"` in user `~/.claude/settings.json`. Outcome: worse than default — wrap/resize behavior degraded further. Removed.

## Applied fix (2026-05-07)

Implementation = Required #1 + tasks.json variant of Option 2c (auto-launch terminal, manual claude launch via alias).

| Change | File | Notes |
|---|---|---|
| `containerEnv.TERM=xterm-256color`, `COLORTERM=truecolor` | `layer4-devcontainer/devcontainer.json` | Required #1 |
| Removed `postAttachCommand` (auto-launched claude in raw PTY) | `layer4-devcontainer/devcontainer.json` | Option 2a action |
| `terminal.integrated.profiles.linux.claude-bash` profile + set as default | `layer4-devcontainer/devcontainer.json` | Every Ctrl+\` terminal sources `claude-rc.sh` |
| Auto-open shell on attach | `layer4-devcontainer/.vscode/tasks.json` | `runOn: folderOpen` task launches `bash --rcfile claude-rc.sh` |
| `myclaude` alias = `cd $(cat ~/live-project) && claude --dangerously-skip-permissions` | `layer4-devcontainer/scripts/claude-rc.sh` (NEW) | One alias, single source. User types `myclaude` to launch. |
| Updated CLAUDE.md docs | `layer4-devcontainer/CLAUDE.md` | Documents new mechanism, removes stale `bash --login` postAttachCommand reference |

**Open follow-ups tracked in `build-workflow-stack-composition.md` "Open Questions — remaining":**
- Long-term: move alias from L4 template into L2 image bake (AI CLI layer concern).
- `myclaude` ↔ `load-projects.sh` coupling: fallback behavior for sandbox / no-project_repo builds.

## Symptom

VS Code integrated terminal column/row alignment is wrong vs Claude Code's TUI output. Drag-resize and Ctrl-L make it worse, not better.

## Root cause (verified 2026-05-07)

Inspection of running processes + env in this session:

```
PID 660: /bin/sh -c "bash --login -c 'cd $(cat ~/live-project) && claude --dangerously-skip-permissions'"
PID 667: claude --dangerously-skip-permissions   (running on pts/0)
```

Env in claude's process tree:
- `TERM=xterm` (bare — VS Code normally sets `xterm-256color` for integrated terminals)
- `COLORTERM=unset`
- `VSCODE_INJECTION=unset`

Three structural issues:

1. **`postAttachCommand` launches claude.** VS Code's shell-integration injection only runs for terminals opened via the integrated-terminal UI. `postAttachCommand` children get a raw PTY — no injection.
2. **`bash --login -c '...'` is non-interactive.** `.bashrc` line 23's `shopt -s checkwinsize` only fires on prompt return in *interactive* shells. Never runs here, so PTY size is never re-queried after VS Code window resize.
3. **No `containerEnv`/`remoteEnv` overrides for TERM/COLORTERM.** Container processes inherit minimal terminal capabilities.

## Fix plan (apply in `build-containers-with-claude/.devcontainer/devcontainer.json`)

### Required

1. Add `containerEnv` (or `remoteEnv` if it should override host):
   ```json
   "containerEnv": {
     "TERM": "xterm-256color",
     "COLORTERM": "truecolor"
   }
   ```

### Choose one

| Option | Change | Trade-off |
|---|---|---|
| **2a (recommended)** | **Remove `postAttachCommand`** that auto-launches `claude`. User opens VS Code integrated terminal manually after attach and runs `claude` themselves. | + Full shell integration, proper geometry, prompt tracking. − Extra manual step on every container attach. |
| **2b** | Keep `postAttachCommand`. Add `bash -i -c '...'` (interactive flag) so `checkwinsize` engages. | + Auto-launch preserved. − Interactive-mode `-c` is semi-supported; some shell init paths behave differently; injection still missing. |
| **2c** | Replace `postAttachCommand` with a VS Code task (`tasks.json`) keyed to the workspace, prompted on attach. | + Cleaner separation. − More plumbing; still skips shell-injection unless task runs in integrated terminal. |

Recommend **1 + 2a**.

## Stopgap result

- `~/.claude/settings.json` → `"tui": "fullscreen"` was tried, made the problem worse (resize/reflow degraded further), and has been removed. Do **not** re-apply. Default renderer is the current baseline.

## Resume conditions

- ~~Next session: permanent fix in `build-containers-with-claude/.devcontainer/devcontainer.json` (Required #1 + Option 2a)~~ — applied to L4 template instead 2026-05-07; testing via `build-stack-with-claude`.
- After test repo validates fix: sync template → `build-containers-with-claude` (production L4 consumer). Owned by `/deploy-stack` once that skill exists; manual sync until then.

## Cross-references

- CLAUDE.md cross-cutting rule: settings/hooks/env go to project `.claude/`. devcontainer.json IS the Layer 4 repo's project artifact, so applying the fix there honors the rule.
- `.claude/plans/settings-placement-review.md` — open question on whether `tui: "fullscreen"` and similar should move from user settings to a Layer 2/3 image bake.
