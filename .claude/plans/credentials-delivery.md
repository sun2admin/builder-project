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

| Task | Status | Detail |
|---|---|---|
| Detection helper | ✅ DONE | Added `_detect_redundant_passthrough(agg, env_passthrough)` to `compose.py`. Walks `agg.container.post_start_chain` (or splits `agg.container.post_start` on `&&` as fallback), basename-matches each script against `INIT_SCRIPT_CREDENTIAL_MAP`, returns sorted intersection of handled credential names with `env_passthrough`. |
| Catalog | ✅ DONE | `INIT_SCRIPT_CREDENTIAL_MAP` constant in `compose.py`: `init-gh-token.sh` → `(GITHUB_TOKEN, GH_TOKEN, GITHUB_PERSONAL_ACCESS_TOKEN)`, `init-ssh.sh` → `(SSH_AUTH_SOCK,)`. Add an entry when L4 introduces a new init-script for a new credential family. |
| Warning emission | ✅ DONE | `_compose_credentials` now calls the detection helper after building `env_passthrough` and emits one stderr line per overlap: `build-stack: warning: <NAME> already delivered by an init-script in post_start chain; containerEnv passthrough may conflict (set overrides.credentials_delivery.<NAME>="mount" to skip env passthrough).` |
| Unit tests | ✅ DONE | 23 new tests in `tools/build-stack/tests/test_compose.py` — catalog stability (3 tests), detection helper purity (12 tests covering empty inputs, dict-form chain, post_start text fallback, args-after-script, dedup, sorting, non-dict skip), warning emission (8 tests covering format, line count, no-warning paths, override interaction, alpha-sort). All 95 tests in the file pass; full build_stack suite 546 passed / 10 skipped, no regressions. |
| Smoke test | ✅ DONE | Real `python -m build_stack compose` run against builder-project's cached analysis emits exactly two warnings (`GITHUB_TOKEN`, `SSH_AUTH_SOCK`) — confirms detection fires on the motivating case. |
| Plan update | ✅ DONE | This commit. |

### Design pivot during implementation (2026-05-08)

The v1 implementation tasks above describe what *actually* shipped. The original plan-text proposed strict basename matching of credential names against mount targets (e.g. `GITHUB_TOKEN` ↔ `/run/credentials/GITHUB_TOKEN`). Discovered during implementation: the project's mount-file naming follows source-file conventions (`gh_pat`, `gh_claude_ed25519`) rather than env-var names — strict match would not have fired for builder-project (or any project derived from the L4 template). Pivoted to **init-script-catalog detection (Option C from the F8 design space)**: detect by which scripts run in the `post_start` chain, since the *script* is what actually performs the credential delivery (mount + reads file + writes `~/.profile`). Catalog is L4-template-canonical, lives next to `_compose_credentials`, starts at 2 entries.

Verified against both `sun2admin/builder-project` and `sun2admin/build-stack-with-claude` — identical credential structure across both repos confirms the L4 template owns the convention.

### v2 evidence run — 2026-05-10

Two-sample corpus run to satisfy the v2 gate ("v1 has run on at least 2 corpus projects"):

| Sample | `credentials_required.tokens` | `credentials_required.ssh` | `init-gh-token.sh` in chain | `init-ssh.sh` in chain | F8 v1 warnings emitted |
|---|---|---|---|---|---|
| `sun2admin/builder-project` (smoke test, 2026-05-08) | `["GITHUB_TOKEN"]` | `true` | yes | yes | `GITHUB_TOKEN` + `SSH_AUTH_SOCK` (2) |
| `sun2admin/build-stack-with-claude` (this run, 2026-05-10) | `[]` | `true` | yes | yes | `SSH_AUTH_SOCK` only (1) |

**Method:** minimal `build.json` (`{project_repo, build_project, ai_clis: ["claude"], use_recommended_l3: false, plugin_selections: []}`) at `/tmp/f8-test/bswc/build.json`; `python -m build_stack compose <build.json> 2>stderr.log`. Analysis cache populated via `python -m build_stack analyze sun2admin/build-stack-with-claude`.

**Catalog verification (intact):** both samples' `post_start_chain` contains `init-ssh.sh` and `init-gh-token.sh` (basename match against `INIT_SCRIPT_CREDENTIAL_MAP`). No drift between the v1 catalog and the current L4 template.

**Source of asymmetry:** analyzer's `credentials_required.tokens` is sourced from in-repo env-var scans (`source_scan._route_source_env`, `_TOKEN$` regex) and GHA-secret scans (`_route_gha_secrets`, literal `GITHUB_TOKEN`). `build-stack-with-claude` is the L4-template mirror — devcontainer.json + init-scripts + vscode configs only, no application source or GHA workflows referencing `GITHUB_TOKEN` — so `tokens: []`. Compose then doesn't add the env-passthrough, so there's no redundancy for v1 to flag. **This is correct analyzer + compose behavior, not a v1 false-negative.**

**Structural observation (informs but does not decide v2):** the two redundancy modes v1 detects are not equivalent —

- **`SSH_AUTH_SOCK` redundancy** is a *behavior conflict*. `init-ssh.sh` sets up an internal ssh-agent at `/home/claude/.ssh/agent.sock` and writes that path to `SSH_AUTH_SOCK`. Compose's default env-passthrough adds `SSH_AUTH_SOCK: ${localEnv:SSH_AUTH_SOCK}` to `containerEnv`, which **overrides** the internal-agent socket with the host's socket. Wrong outcome guaranteed every container start where `init-ssh.sh` runs.
- **`GITHUB_TOKEN` (and other token) redundancy** is *parallel delivery*. `init-gh-token.sh` writes `export GH_TOKEN=...` to `~/.profile`; env-passthrough adds `GITHUB_TOKEN` to `containerEnv`. Both delivery paths succeed independently. A real conflict only arises if the host env-var value and the file-mount value differ.

This suggests a v2 design *could* treat the two cases asymmetrically (e.g. `SSH_AUTH_SOCK` → auto-suppress; tokens → keep warn-only). **No decision taken.** Token-redundancy needs at least one corpus sample where a project intentionally relies on both delivery mechanisms before the asymmetric remedy is on firm empirical ground.

### v2 ship — 2026-05-10 (asymmetric remedy)

**Decision:** apply Option A (auto-suppress) only to `SSH_AUTH_SOCK`; keep token-class credentials on warn-only. Picked from the design space surfaced by the evidence run because the two redundancy modes are structurally different (behavior conflict vs parallel delivery — see "v2 evidence run" above).

**Code change:** `_compose_credentials` (`compose.py`), single asymmetric branch inside the redundancy loop. When `_detect_redundant_passthrough` returns `SSH_AUTH_SOCK`, it's removed from `env_passthrough` and no warning is emitted. For every other returned name, the v1 warning fires unchanged.

**Mechanism downstream:** `_compose_container_env` (`emit.py:82–89`) fills `containerEnv` from `env_passthrough` first (each name → `${localEnv:NAME}`), then layers `agg.container.env` entries only for unset keys. Removing `SSH_AUTH_SOCK` from `env_passthrough` lets the project's own `agg.container.env["SSH_AUTH_SOCK"]` (`/home/claude/.ssh/agent.sock`) surface instead of being shadowed. No emit-layer change required.

**End-to-end verification (2026-05-10):**

| Sample | Pre-v2 emitted `SSH_AUTH_SOCK` | Post-v2 emitted `SSH_AUTH_SOCK` | Stderr warnings |
|---|---|---|---|
| `sun2admin/builder-project` | `${localEnv:SSH_AUTH_SOCK}` (host socket; overrides `init-ssh.sh` setup) | `/home/claude/.ssh/agent.sock` (internal agent; matches `init-ssh.sh`) | 1 (token: `GITHUB_TOKEN`) |
| `sun2admin/build-stack-with-claude` | `${localEnv:SSH_AUTH_SOCK}` | `/home/claude/.ssh/agent.sock` | 0 (no tokens, SSH suppressed silently) |

**Tests:** 4 added, 1 removed (alpha-sort test was a 2-warning ordering pin; v2 emits 1 warning so the property is moot). Renamed 2 tests to drop the implicit "two-warning" framing of v1: `_warns_on_overlap` → `_warns_on_token_overlap`, `_warning_one_line_per_overlap` → `_warning_one_line_for_token_overlap`. New tests pin: SSH suppressed-from-env_passthrough behaviour, SSH kept when `init-ssh.sh` not in chain (negative case), SSH-only minimal fixture (no token interaction), token kept in env_passthrough when warned (parallel-delivery contract). Suite: 555 passed (was 553; net +2).

### Out of v2 scope (deferred)

Held for later — not blocked, just not justified by current evidence:

- **Token auto-suppress** (Option A applied to tokens too) — needs a corpus sample where the parallel delivery actually breaks (host env value disagrees with the file-mount value). Until then, warn-only is the right cost/risk tradeoff.
- **`="env"` override** (opt back into env-passthrough for SSH) — no project needs it today. Add when a project legitimately wants host SSH agent forwarded *despite* running `init-ssh.sh`.
- **Informational log on suppression** — useful for debuggability ("build-stack: info: suppressed SSH_AUTH_SOCK passthrough; init-ssh.sh handles delivery"); deferred to keep v2 ship minimal.
- **Flip default for env-passthrough generally** (Option D from original design space) — much more aggressive; affects every credential. Not on the table given asymmetric ship resolved the actual bug.
- **Skill UX prompt** (Option C/UX from original design space) — would add a step to the already 8-step interactive flow. Not justified when the auto-suppress + warn split handles every observed case.
- **Catalog refinement** — current 2 entries cover the L4 template today. If a project introduces an init-script outside the template (e.g. project-specific `init-stripe-key.sh`), the catalog needs an extension mechanism (per-project map in `build.json`?). Track when first encountered.

## Open external-credential tasks (cross-plan)

Tasks that touch external-credential delivery, gathered from sibling plans and code:

- [x] **`claude-user-env.md` §5 (SSH agent) reopened by F8** — F8 surfaced the question of whether the compose-tool default `SSH_AUTH_SOCK: ${localEnv:SSH_AUTH_SOCK}` should silently override the internal-agent socket that `init-ssh.sh` sets up. Closed 2026-05-10 by F8 v2: SSH_AUTH_SOCK is now auto-suppressed from env-passthrough when `init-ssh.sh` is detected, letting the project's internal-agent path surface in `containerEnv` instead.
- [x] **Test coverage for `overrides.credentials_delivery="mount"` path** — covered by `test_compose_credentials_override_routes_to_mount` (pre-existing) plus F8 v1's `test_compose_credentials_mount_override_suppresses_warning_for_that_cred` which pins the override+detection interaction.
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

- **F8 v1 work** — ✅ shipped (commit `c5c2a3d`). Detection helper + warning emission live in `compose.py`; verified to fire on `sun2admin/builder-project` for both `GITHUB_TOKEN` and `SSH_AUTH_SOCK`.
- **F8 v2 evidence-gathering** — ✅ done 2026-05-10. Two corpus samples (`builder-project`, `build-stack-with-claude`) confirm catalog intact. See "v2 evidence run" subsection above for full table + analysis.
- **F8 v2 design + ship** — ✅ done 2026-05-10 (asymmetric remedy). SSH_AUTH_SOCK auto-suppressed when `init-ssh.sh` in chain; tokens unchanged from v1. End-to-end smoke test confirms emitted `containerEnv.SSH_AUTH_SOCK` flips from host-passthrough to internal-agent path on both samples. See "v2 ship" subsection above.
- **F8 v3 (token auto-suppress)** — open. Resume when a corpus project surfaces that token redundancy actually breaks (host env value vs init-script value diverge). Until then, warn-only is the right tradeoff.
- **New credential added to a project** — inventory table updated *before* implementation; delivery pattern decided per "Decision rules" section above.
- **Skill UX expansion** — defer until F8 v2 outcome (option C explicitly adds a prompt step; options A/D may obviate the need).
