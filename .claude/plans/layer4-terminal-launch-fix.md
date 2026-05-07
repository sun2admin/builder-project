# Plan Note: Layer 4 Terminal Launch / Geometry Fix

**Status:** Open. Defer until current build-stack work is past.
**Repo affected:** `build-containers-with-claude` (Layer 4 devcontainer), NOT builder-project.
**Stopgap applied (2026-05-07):** `"tui": "fullscreen"` in user `~/.claude/settings.json` — alt-screen renderer handles resize cleaner than `default`.

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

## Stopgap already in place

- `~/.claude/settings.json` → `"tui": "fullscreen"` (this session). Personal display pref per CLAUDE.md exception. Renderer handles resize/reflow more robustly than `default`. May or may not fully resolve the wrap mismatch — verify after a fresh attach.

## Resume conditions

- After current build-stack tasks land (image revert ✓ done, plugin_selections install pending, BSQ3/BSQ9 deferred).
- Or when fullscreen TUI proves insufficient and user wants a permanent fix.

## Cross-references

- CLAUDE.md cross-cutting rule: settings/hooks/env go to project `.claude/`. devcontainer.json IS the Layer 4 repo's project artifact, so applying the fix there honors the rule.
- `.claude/plans/settings-placement-review.md` — open question on whether `tui: "fullscreen"` and similar should move from user settings to a Layer 2/3 image bake.
