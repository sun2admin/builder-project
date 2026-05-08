# credentials-delivery — Sub-plan

**Status:** Active. Sub-plan of `build-workflow-stack-composition.md`. Tracks how credentials and auth state for **non-Claude tools** (git/gh, ssh, future DB / 3rd-party API keys) are delivered into the container, and how the compose tool decides between delivery mechanisms.

Claude Code's own auth (OAuth, named-volume `.credentials.json` / `.claude.json`, `CLAUDE_CODE_OAUTH_TOKEN`, etc.) is **out of scope here** — see `authentication-strategy.md`. The two plans are siblings: the credentials they cover are different, but the underlying delivery toolbox (host env passthrough, bind-mounted file, init-script reads-file-then-writes-`~/.profile`) is shared. Solutions adopted in one plan often apply in the other; cross-reference before reinventing.

## Scope

- Credential **delivery mechanisms** at the stack composition layer (compose tool + L4 init scripts)
- Per-credential decision rules: which mechanism for which credential
- The `/build-stack` skill UX surface for credential decisions (currently: none)
- Inventory of every credential the stack handles today, with delivery method

## Out of scope

- Claude Code auth precedence chain (Bedrock/Vertex/Foundry env vars, `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, subscription OAuth) — `authentication-strategy.md`
- SSH agent socket mechanics inside the container — `claude-user-env.md` §5
- Project-application-level secret management (e.g. how a project's runtime reads `DATABASE_URL` once it's in the container env) — out-of-stack concern

## Inventory of known external credentials

Snapshot as of 2026-05-08. Add a row before introducing a new credential to the stack.

| Credential | Source on host | Container delivery (today) | Consumed by | Notes |
|---|---|---|---|---|
| **`gh_pat`** (PAT, contents become `GH_TOKEN` / `GITHUB_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN`) | `~/Downloads/ClaudeFiles/Config/gh_pat` (host file) | Bind-mount `→ /run/credentials/gh_pat` (readonly) | `init-gh-token.sh` reads file → writes `export GH_TOKEN=...` to `~/.profile` (chmod 600) | Pattern 3 (mount + init-script). Compose tool currently *also* adds `GITHUB_TOKEN: ${localEnv:GITHUB_TOKEN}` to `containerEnv` — F8. |
| **`gh_claude_ed25519`** (SSH private key) | `~/Downloads/ClaudeFiles/Config/gh_claude_ed25519` (host file) | Bind-mount `→ /run/credentials/gh_claude_ed25519` (readonly) | `init-ssh.sh` copies to `~/.ssh/`, starts agent at `/home/claude/.ssh/agent.sock`, loads key | Pattern 3. Compose tool currently overrides via `SSH_AUTH_SOCK: ${localEnv:SSH_AUTH_SOCK}` — F8. |
| **`SSH_AUTH_SOCK`** (env var) | (set by `init-ssh.sh` to internal-agent socket) | `containerEnv` from `init-ssh.sh` write (after run) | All ssh subprocesses | Reference project: container-internal agent. Compose default would forward host agent — incompatible. |
| **(future) `DATABASE_URL` / 3rd-party API keys** | (TBD) | (TBD — unhandled at stack layer today) | Project runtime | Flag here when first project needs one; pick delivery pattern per "Decision rules" below. |

## The three delivery patterns

| Pattern | Mechanism | Compose-layer representation | Used today by |
|---|---|---|---|
| **1. Host env passthrough** | `containerEnv: { NAME: "${localEnv:NAME}" }` in devcontainer.json | Default of `_compose_credentials` for every entry in `agg.credentials_required.*` | (would-be default for all if no override) |
| **2. Bind-mounted file** | Mount `/run/host-credentials/<name>` → `/run/credentials/<name>` (readonly) | `build_json.overrides.credentials_delivery[<name>] = "mount"` triggers this branch in `_compose_credentials` (compose.py:156-161) | (mechanism wired but never invoked — the `/build-stack` skill never sets the override) |
| **3. Mount + init-script reads-file-writes-profile** | Pattern 2's mount + an L4 init script (`init-gh-token.sh` etc.) reads the file and writes `export NAME=...` to `~/.profile` (chmod 600) | Compose tool has **no awareness** of this pattern today — it sees mounts via `agg.container.volumes` and credentials via `agg.credentials_required` as independent surfaces | All 3 credentials in the inventory above |

The compose tool today only knows patterns 1 and 2. Pattern 3 is an emergent property of the project's mount list + init-script chain that the compose layer is blind to. F8 is fundamentally about giving compose enough awareness of pattern 3 to stop layering pattern 1 on top of it.

## Active item: F8 — compose default conflicts with pattern 3

**Discovered:** 2026-05-08, parent plan §"Migration steps from current state" #12 (commit `4c9dbe2`).

**Symptom:** When `analyze` reports `credentials_required.{tokens, ssh}` for a project that *also* mounts those credentials at `/run/credentials/<name>` and runs init-scripts that consume them, compose's default `containerEnv` passthrough adds env vars on top:

- `GITHUB_TOKEN: ${localEnv:GITHUB_TOKEN}` — redundant; competes with `init-gh-token.sh` writing to `~/.profile`
- `SSH_AUTH_SOCK: ${localEnv:SSH_AUTH_SOCK}` — overriding; replaces internal-agent socket set up by `init-ssh.sh`

**Decision (2026-05-08, v1 path = Option B from F8 design space):**

Keep the current `containerEnv` passthrough default. Add a **warning** when redundant delivery is detected. **No behavior change** in the generated devcontainer.json for v1. The warning surfaces the conflict so users can choose to set `overrides.credentials_delivery=mount` explicitly.

Rationale: an auto-detect default that suppresses passthrough when "wrong" silently breaks credentials in the container — strictly worse than the current redundancy. The warning is a stepping stone: it builds an empirical record of how often the conflict fires across real builds, which informs the v2 design (auto-detect rule, default flip, or skill UX prompt).

### v1 implementation tasks

| Task | File | Detail |
|---|---|---|
| Detection helper | `tools/build-stack/build_stack/compose.py` | Add `_detect_redundant_passthrough(agg, env_passthrough)` that scans `agg.container.volumes` for mount targets matching `/run/credentials/<name>` where `<name>` is in `env_passthrough`. Returns the overlapping names. |
| Warning emission | `_compose_credentials` (same file) | When detection returns non-empty, emit one stderr line per credential: `compose: warning: <NAME> already mounted at /run/credentials/<NAME> by project; containerEnv passthrough may conflict (set overrides.credentials_delivery.<NAME>="mount" to use file delivery only).` |
| Unit test | `tools/build-stack/tests/test_compose.py` (new file) | Pin: (a) detection returns expected names for builder-project-shaped agg; (b) detection returns empty when no overlap; (c) `_compose_credentials` still produces same `env_passthrough` list (warning only, no behavior change); (d) stderr contains expected warning text. |
| Plan update | this file | Mark v1 tasks done; record commit hashes |

### v2 considerations (deferred)

Out of v1 scope; revisit when v1's warning data shows whether the redundancy is universal or project-specific:

- **Auto-detect** (Option A from F8 design space) — when redundancy detected, skip the env-passthrough entry (and the SSH_AUTH_SOCK addition for `ssh: true`). Risk: silent breakage if detection is wrong.
- **Flip default** (Option D) — only emit env-passthrough when the user opts in via `overrides.credentials_delivery.<NAME>="env"` (new override value). More aggressive; affects all projects.
- **Skill UX prompt** (Option C) — `/build-stack` adds a per-credential "delivery: env / mount / project handles it" prompt. Cost: another step in an already 8-step interactive flow.
- **Detection rule refinement** — current proposal matches mount-target-suffix only. Could also match by inspecting the post_start chain for known init-script signatures (`init-gh-token.sh` → handles `GITHUB_TOKEN`-class). More robust, more brittle.

## Open external-credential tasks (cross-plan)

Tasks that touch external-credential delivery, gathered from sibling plans and code:

- [ ] **`claude-user-env.md` §5 (SSH agent) reopened by F8** — that plan currently marks SSH agent as "no open question." F8 surfaced the question of whether the compose-tool default `SSH_AUTH_SOCK: ${localEnv:SSH_AUTH_SOCK}` should silently override the internal-agent socket that `init-ssh.sh` sets up. Resolution: handled by F8 v1 (warning); if v2 chooses Option A (auto-detect), this question closes automatically.
- [ ] **Test coverage for `overrides.credentials_delivery="mount"` path** — `compose.py:156-161` implements the file-mount branch but no unit test exercises it. Add to `tools/build-stack/tests/test_compose.py` alongside the F8 v1 tests.
- [ ] **CLAUDE.md cross-cutting rule audit** — the rule says "credentials write to `~/.profile` (chmod 600), never `/etc/environment`." `init-gh-token.sh` follows this. Audit: is any credential currently written elsewhere? Is the rule still applied if a project adopts `overrides.credentials_delivery="mount"` only (no init-script)?
- [ ] **Inventory completeness** — when a project introduces a new credential (e.g. first project needing `DATABASE_URL`), add a row to the inventory table *before* writing init-script logic. Forces the delivery decision into the open instead of inferring from code.
- [ ] **Skill UX integration** — even with v1's warning, the `/build-stack` skill still has no way for the user to set `overrides.credentials_delivery`. The override mechanism is dead code unless we expose it. Resolution depends on F8 v2 outcome.

For Claude Code auth open tasks (init-claude-config.sh not written, `CLAUDE_CODE_OAUTH_TOKEN` not provisioned, backup auto-restore not implemented), see `authentication-strategy.md` §Status. Those are tracked independently because the credential and the consumer are both Claude-specific, but the delivery mechanism (bind-mounted file at `/run/credentials/claude_oauth_token` + init-script reads + writes `~/.profile`) is **pattern 3 from this plan** — solutions are interchangeable across the two surfaces.

## Decision rules (when adding a new external credential)

For any new credential the stack must deliver, capture in the inventory table and pick a delivery pattern:

| Question | If yes → suggests |
|---|---|
| Does the credential need to be **available to all subprocesses** (not just Claude/the AI CLI)? | Pattern 3 (mount + `~/.profile`) — login shells inherit `~/.profile` via `bash --login` |
| Does it **rotate frequently** (token expiry < 1 day)? | Pattern 1 (env passthrough) — host env follows host rotation; no init-script restart needed |
| Is it **structured / multi-line** (SSH key, JSON cert)? | Pattern 2 or 3 (file mount) — env vars are scalar |
| Is it **sensitive enough that env-pasthrough leaks via `ps`/`env` are unacceptable**? | Pattern 2 or 3 |
| Does the project's existing init-script chain already handle it? | Pattern 3 (don't duplicate); compose should NOT add env-passthrough — F8 v1 will warn, v2 may auto-suppress |

## Cross-references

- **`authentication-strategy.md`** — Claude Code's own auth precedence chain. Solutions overlap heavily: file-mount + init-script (pattern 3) is the recommended approach for both `gh_pat` (this plan) and `claude_oauth_token` (auth-strategy.md Option A). When implementing one, check the other for an existing recipe before designing fresh.
- **`claude-user-env.md` §5** — SSH agent socket details (`init-ssh.sh`, fixed-path agent socket). F8 surfaces a tension between that plan's stated "no open question" and compose-layer behavior; resolution flows back to this plan.
- **Parent: `build-workflow-stack-composition.md`** — §"Migration steps from current state" #12 records F8's discovery context and links here.
- **Memory entries (auto-loaded context):**
  - `devcontainer-credential-files.md` — pattern for injecting secrets via bind-mounted credential files
  - `devcontainer-ssh-and-keys.md` — SSH agent forwarding behavior in dev containers
  - `feedback-credentials-shell-env.md` — convention to use `~/.profile` (chmod 600), never `/etc/environment`
  - `devcontainer-claude-code-auth.md` — Claude Code auth state files inside named volume
- **Code:**
  - `tools/build-stack/build_stack/compose.py:143-169` — `_compose_credentials` (compose-layer credential decisions; default + override mechanism)
  - `tools/build-stack/build_stack/emit.py:82` — `_compose_container_env` (lifts compose decision into devcontainer.json)
  - `layer4-devcontainer/scripts/init-{ssh,gh-token,github-mcp}.sh` — pattern-3 init-script consumers

## Resume conditions

- **F8 v1 work** — implementable now; queue tasks via TaskCreate when ready to start. The warning is purely additive (no behavior change) so it can ship independently of any v2 decision.
- **F8 v2 (auto-detect / flip default / skill UX)** — wait until v1 has run on at least 2 corpus projects (builder-project + one sandbox build, or builder-project + a non-trivial second project). The data point is "does redundancy fire universally or only for projects with init-scripts?"
- **New credential added to a project** — inventory table updated *before* implementation; delivery pattern decided per "Decision rules" section above.
- **Skill UX expansion** — defer until F8 v2 outcome (option C explicitly adds a prompt step; options A/D may obviate the need).
