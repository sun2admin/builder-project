# claude-user-env — Container User Environment Plan

**Status:** Active. Sub-plan of `build-workflow-stack-composition.md`. Consolidates open design questions and decisions about the `claude` user's environment inside Layer 4 devcontainers — shell init, aliases, terminal behavior, editor config — and the layer at which each piece should live.

## Scope

Everything that shapes the `claude` user's per-session experience after container start:

- Shell startup files (`~/.bashrc`, `~/.profile`, custom rcfiles)
- Aliases (`myclaude` and future companions)
- Terminal config (TTY caps, TERM/COLORTERM, integrated terminal profiles, tasks.json auto-open)
- Editor keybindings (VS Code Server: Shift+Enter for newlines, etc.)
- Init scripts that write to home directory (`init-ssh.sh`, `init-gh-token.sh`, …)

**Out of scope:**
- Claude Code settings.json placement → `settings-placement-review.md`
- AI CLI selection / install → `build-workflow-stack-composition.md`
- Container-level networking, firewalls, capabilities

## Cross-cutting placement framework

Every item below has the same shape: **which layer owns it?** Reference table for reasoning about each:

| Layer | Mechanism | Pros | Cons |
|---|---|---|---|
| L1 image | `/etc/bash.bashrc`, `/etc/profile.d/*.sh` | Universal cascade, immutable | Generic base; AI-specific items leak abstraction |
| L2 image | Same paths, AI-CLI-aware bake | AI CLI tier; cascade to all L2 stacks | Image rebuild for changes |
| L3 image | Plugin layer baked-in | Plugin-specific needs | Not generally applicable to env |
| L4 init script | `layer4-devcontainer/scripts/init-*.sh` writes to `/home/claude/.*` on attach | No image rebuild; declarative; easy to iterate; idempotent re-write each attach | Per-attach overhead (small) |
| Devcontainer mount | Persistent named volume | One-time setup persists | Volume bloat; VS Code Server version mismatch risk for `.vscode-server`-class paths |
| User-interactive | One-shot prompt during session | Zero infra | Lossy across rebuilds; silent broken-state risk if Claude Code's "done" flag persists separately |

## Items

### 1. `myclaude` alias

**Current state (2026-05-07):** L4 — `layer4-devcontainer/scripts/claude-rc.sh` sourced via `terminal.integrated.profiles.linux.claude-bash` default profile + `.vscode/tasks.json` `runOn: folderOpen` task. Both reference the same rcfile path. Defines:

```bash
alias myclaude='cd $(cat ~/live-project 2>/dev/null || echo ~) && claude --dangerously-skip-permissions'
```

**Long-term consideration:** Move to L2 image bake at `/etc/bash.bashrc.d/claude-aliases.sh` or similar. Reason: alias is "AI CLI launch ergonomic" — belongs with the AI CLI install, not with devcontainer config. Cascades to all stacks using L2 without per-L4-template duplication.

**Decision deferred:** until L2 image-bake-vs-devcontainer-feature question resolves (separate Open Question in parent plan: "AI CLIs as devcontainer features"). Migrate together.

**Cross-reference:** TTY fix recipe — `layer4-terminal-launch-fix.md`.

### 2. `myclaude` ↔ `~/live-project` coupling

**Current state:** Alias resolves `cd $(cat ~/live-project 2>/dev/null || echo ~)`. `~/live-project` is written by `load-projects.sh -live <repo>`. Falls back to `cd ~` when file missing.

**Open question:** Sandbox / no-`project_repo` builds skip the `-live` flag (no `~/live-project` written) → alias falls back to `cd ~` (no project context). Two paths:

- **(a)** Require a default "template project" repo for sandbox builds so the alias has a meaningful destination. Adds a per-build dependency, but matches the "every stack has a project" mental model.
- **(b)** Make alias smarter — fall back to `/workspace` (workspace root) when `~/live-project` missing instead of `~`. Simpler; sandbox lands user inside the build itself.

**Decide before:** sandbox-mode build path is wired in `/build-stack` (parent plan §"Skill UX Design" — sandbox case currently theoretical).

### 3. VS Code Server keybindings (Shift+Enter for newlines)

**Triggered by:** Claude Code's `/terminal-setup` prompt on first run inside an integrated terminal:

```
Use Claude Code's terminal setup?
For the optimal coding experience, enable the recommended settings
for your terminal: Shift+Enter for newlines
  1. Yes, use recommended settings
  2. No, maybe later with /terminal-setup
```

Accepting writes a Shift+Enter binding to `~/.vscode-server/data/Machine/keybindings.json`. Lets multi-line prompts be entered without submitting on Enter.

**Persistence problem:** `~/.vscode-server/` is NOT on a named volume in current L4 mounts. Binding lost every container rebuild.

**Worse silent state:** Claude Code's "user already ran terminal-setup" flag lives in `~/.claude.json` (which IS on the named volume `claude-code-config-${devcontainerId}`). After rebuild: flag persists, binding does not → Claude Code stops re-prompting while the binding is missing.

**Options:**

| Option | Mechanism | Persists? | Risk |
|---|---|---|---|
| **A** | Accept "Yes" each rebuild interactively | One container lifetime | Annoying re-prompt; silent broken-state if flag persists past binding loss |
| **B** | Add `~/.vscode-server` to named volume mount | Persistent | VS Code Server version mismatch on host upgrade → install loops, startup hangs (known dev container footgun) |
| **C** | Idempotent init script `init-vscode-keybindings.sh` writes binding on every attach | Persistent | Drift if Claude Code upstream adds new recommended bindings — mitigated by tracking minimal binding set + plan note |
| **D** | Skip — never enable Shift+Enter | N/A | Multi-line prompt input limited to paste |

**Current state (2026-05-07):** **Option A.** Accepted "Yes" interactively in test session of `build-stack-with-claude`. Chosen because:
- Test repo session is short-lived; loss-on-rebuild not yet a real cost
- Want to validate TTY fix end-to-end before adding more L4 plumbing
- Option C is the long-term recommendation (no volume risk, idempotent, same pattern as existing init scripts)

**Long-term:** Migrate to Option C (init script). If recommended-bindings list grows or upstream churn becomes regular, reassess Option B. Track this migration alongside §1 alias migration when revisiting L4 init scripts collectively.

### 4. Shell rcfile sourcing chain (existing, no open question)

Documented for env-inventory completeness. Order on integrated-terminal start:

1. Custom rcfile via `bash --rcfile <path>` arg → `/workspace/.devcontainer/scripts/claude-rc.sh`
2. `claude-rc.sh` sources `~/.bashrc` (system defaults, prompt, completions)
3. `claude-rc.sh` sources `~/.profile` (credentials — PAT written by `init-gh-token.sh`)
4. `claude-rc.sh` defines `myclaude` alias

Future env additions land in `claude-rc.sh` between steps 3 and 4 unless a stronger reason places them upstream.

### 5. SSH agent setup (existing, no open question)

`init-ssh.sh` creates agent at fixed socket `/home/claude/.ssh/agent.sock`, loads key from `/run/credentials/gh_claude_ed25519`. `containerEnv.SSH_AUTH_SOCK` exposes the socket to all subprocesses via env.

Documented for inventory; no open question.

### 6. TTY / geometry config (existing, applied 2026-05-07)

Env: `TERM=xterm-256color`, `COLORTERM=truecolor` set in `containerEnv`. Integrated terminal auto-opens via tasks.json (correct shell-integration injection vs raw PTY of removed `postAttachCommand`). Documented in detail in `layer4-terminal-launch-fix.md`.

No open question — fix applied. Cross-link kept here so future TTY-tier env changes have a single home.

## Decision matrix template

For any new env addition, capture:

| Field | Value |
|---|---|
| Item | (e.g. `mygemini` alias, new init script) |
| Layer chosen | L4 / L2 / L1 / mount / interactive |
| Rationale | (UX scope, persistence cost, blast radius) |
| Migration path if "wrong" | (how to relocate later) |
| Cross-references (existing plans, init scripts, image tags) | |

## Cross-references

- TTY fix recipe (resolved 2026-05-07): `layer4-terminal-launch-fix.md`
- Claude Code settings.json placement (separate concern): `settings-placement-review.md`
- Parent plan: `build-workflow-stack-composition.md` "Open Questions — remaining"
- Layer 4 architecture: `layer4-design.md`

## Resume conditions

- Item §1 (alias L2 migration) and §3 (keybindings init script): wait until L2 image-bake-vs-devcontainer-feature decision lands. Migrate batches together to avoid serial L4 churn.
- Item §2 (sandbox `~/live-project` fallback): decide before sandbox-mode build path is wired in `/build-stack`.
- New env additions: use the decision-matrix template above and append a new §N item here before implementing.
