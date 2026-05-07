# build-stack: Absorb analyze-repo into Tool

**Status:** Active — sub-plan of [`build-workflow-stack-composition.md`](./build-workflow-stack-composition.md). Scope-bounded execution recipe for the `analyze-repo` migration phases (Phase 1 → 3) defined in the parent plan.

**Sequencing decision (2026-05-06):** Sub-plan Phases 1.5 + 2 + 3 execute **NOW**, before parent plan §6 Phases 4-6 (aggregate/select/compose/emit). Rationale: clean arch upfront. Build-stack composition development against a real Python detector beats developing against a bash-shell-out wrapper that gets thrown away later. User-mandated ordering (see prior iteration of this plan and parent plan §"Recommended ordering").

**Parent plan migration step:** §6 Phase 3 ("analyze: shell out to existing analyze-repo skill"); also implements parent §"analyze-repo migration phases" Phase 1, 2, 3.

**Why this sub-plan:** The parent plan defines architecture and merge rules but treats `analyze` as one bullet. Absorbing the 1629-line bash detector into the Python tool is the first slice that gives the tool real logic — it must be planned independently or it derails the parent.

---

## Goal

End state (after all phases of this sub-plan):

1. `tools/build-stack/build_stack/analyze.py` (+ `analyzers/*.py`) is the **single source of truth** for repo detection.
2. `/analyze-repo` skill is a **thin bash wrapper** (~50 lines) that shells out to `python -m build_stack analyze --human <repo>`.
3. `tool-deps.json` cache lives at `tools/build-stack/build_stack/data/tool-deps.json` (moved from skill dir).
4. **All analyzer output lands under `analyzed_repos/<owner>/<repo>/`**, not `builds/<owner>/<repo>/`. `builds/` becomes exclusively build-stack composition output (skill+tool produces `build.json`, `aggregated.json`, `devcontainer.json`, `workspace.env` per build).
5. **Existing pre-rename `builds/<owner>/<repo>/` analysis dirs are migrated** to `analyzed_repos/<owner>/<repo>/` via `git mv` — preserves history.
6. Parity validated against migrated test corpus (now at `analyzed_repos/`) — same `analysis.json` byte output for the same input repo.

Out of scope:
- Composition logic (`select.py`, `compose.py`, `emit.py`) — belongs in parent plan §6 Phases 5-6.
- New detection fields beyond what `analyze-repo.sh` already emits — pure port, not refactor.
- Build-stack skill body (`/build-stack`) — belongs in parent plan; kicks off after this sub-plan completes.

---

## Migration Phases

Mapped to the parent plan's "analyze-repo migration phases" table (§Architecture).

### Phase 1 — Shell-out wrapper (first build-stack release) ✅ DONE

**Goal:** `build-stack analyze <repo>` works end-to-end by subprocessing the existing skill. Zero detection logic in the tool yet.

**Setup (one-time, pre-Phase 1):**
- `pip install -e tools/build-stack/` from repo root. Editable install registers the `build_stack` package via a `.pth` file and adds the `build-stack` console script to PATH. No source copy; live edits reflect immediately. Re-install only required when `pyproject.toml` dependencies or `[project.scripts]` change.

**Deliverables (implemented):**
1. ✅ `analyze.py::analyze(repo: str) -> dict` — invokes `analyze-repo.sh -q <repo>` via `subprocess`, reads emitted `analyzed_repos/<owner>/<repo>/analysis.json` from skill stdout, returns parsed dict. Used in-process by `compose.py` aggregation. (Path moved from `builds/` to `analyzed_repos/` in Phase 1.5.)
2. ✅ `analyze.py::cmd_analyze(repo: str, *, human: bool, quiet: bool) -> int` — CLI wrapper. Pure passthrough to skill: `--human` → `-v`, `--quiet` → `-q`, default = skill TTY-detect. Skill writes JSON path to stdout, markdown to stderr.
3. ✅ `cli.py` wires `analyze` subcommand with mutually-exclusive `--human/-v` and `--quiet/-q` flags. `cmd_analyze(args)` dispatches to `analyze.cmd_analyze`.
4. 🔜 `compose.py` will call `analyze.analyze()` per-repo (parent plan §6 aggregation work — not Phase 1 scope).

**Note on `format_human`:** original Deliverable #2 was `format_human(dict) -> str` returning markdown. Implemented differently: skill already emits markdown to stderr when `-v` flag is set, so the wrapper passes `-v` through and skill handles markdown rendering directly. No separate Python formatter needed in Phase 1. Phase 2 port will absorb markdown rendering.

**Tool side does not yet own detection.** Skill remains canonical detector. Tool is a passthrough.

**Exit criterion (verified):** `build-stack analyze --quiet sun2admin/builder-project` returns `exit=0`, stdout = path to `analysis.json`, stderr = progress traces only. In-process `analyze.analyze('sun2admin/builder-project')` returns dict with 27 keys including `schema_version=2`, `repo`, `languages`. Parity with `bash .claude/skills/analyze-repo/analyze-repo.sh` confirmed for the smoke-test repo.

### Phase 1.5 — OUT_DIR migration (NEW — sequenced before Phase 2)

**Goal:** Move analyze output from `builds/<owner>/<repo>/` → `analyzed_repos/<owner>/<repo>/`. Migrate existing artifacts. Decouples the analyze-output namespace from the build-stack-output namespace.

**Why before Phase 2 port:**
- Parity test corpus must live at the new path before the Python port runs against it.
- Smaller, atomic change. If the dir migration regresses skill output, easy to bisect without Python port noise.
- Build-stack skill (when written) needs `analyzed_repos/` to exist as the canonical analyze cache from day one.

**Deliverables:**
1. Update `analyze-repo.sh`: `OUT_DIR` constant changes from `builds/<owner>/<repo>/` to `analyzed_repos/<owner>/<repo>/`. Single constant flip; logic unchanged.
2. Update skill docs (`SKILL.md`, `DATA_SCHEMA.md`) — output paths in tables and examples.
3. `git mv builds/<owner>/<repo>/ analyzed_repos/<owner>/<repo>/` for every existing detection artifact dir. Inventory at sub-plan write time:
   - `builds/anthropics/`
   - `builds/danielrosehill/`
   - `builds/garrytan/`
   - `builds/hesreallyhim/`
   - `builds/peterkrueck/`
   - `builds/santifer/`
   - `builds/sun2admin/`
4. Update `tools/build-stack/build_stack/analyze.py` (Phase 1 wrapper): no code changes — wrapper passes through skill stdout (the path), which now points into `analyzed_repos/`. Just update doc comments.
5. Update parent plan migration step §6 Phase 3 reference to new path.
6. Delete-or-skip protection: ensure `builds/` is empty of pre-existing detection artifacts after migration. After this phase, `builds/` should be untouched until first `/build-stack` invocation creates `builds/<category>/<project>/`.

**Exit criterion:**
- `analyze-repo.sh sun2admin/builder-project` writes to `analyzed_repos/sun2admin/builder-project/analysis.json`
- `git log --follow analyzed_repos/sun2admin/builder-project/analysis.json` shows the original commit history (rename detected by git)
- `builds/` is empty of pre-existing artifacts (cleanly available for build-stack composition output)

### Phase 2 — Python port (parallel implementation)

**Goal:** Port `analyze-repo.sh`'s detection logic into Python modules under `analyze.py`. Skill remains untouched and authoritative; the port runs alongside for diff-testing.

**Deliverables:**
1. Decompose 1629-line bash into per-detector Python modules:
   ```
   build_stack/analyzers/
   ├── __init__.py
   ├── manifests.py      # package.json / pyproject.toml / Cargo.toml / go.mod / Gemfile / pom.xml / build.gradle / composer.json
   ├── dockerfile.py     # FROM, RUN apt/apk, EXPOSE, ENV, pip/npm/go installs, curl/wget extras
   ├── compose_yaml.py   # docker-compose.yml ports, environment, services
   ├── devcontainer.py   # devcontainer.json features, mounts, postStartCommand chain
   ├── envfiles.py       # .env.example variants
   ├── source_scan.py    # ripgrep-based source patterns: ports, imports, browser tools, octokit
   ├── readme.py         # README first paragraph, code-fence service URLs
   └── apt_resolve.py    # apt-cache lookup → tool-deps.json cache
   ```
2. `analyze.py` orchestrates the analyzers, mirroring the bash flow.
3. `tool-deps.json` migrated: `tools/build-stack/build_stack/data/tool-deps.json` (committed, identical content).
4. Reference docs move + update: `DETECTION_PRINCIPLES.md`, `DATA_SCHEMA.md` migrate from `.claude/skills/analyze-repo/` → `tools/build-stack/build_stack/analyzers/` (or `tools/build-stack/docs/`); SKILL.md replaced by thin wrapper doc.

**Detection invariant** (from parent §"Composition Doctrine"): Python port must produce **only raw facts**. No `suggested.*`, no `firewall_required`. Composition stays in `compose.py` / `select.py`.

**Exit criterion:** parity matrix passes (see Parity Test below).

### Phase 3 — Cutover (after parity validated)

**Goal:** Skill is no longer a detector. Tool is the single source of truth.

**Deliverables:**
1. Replace `.claude/skills/analyze-repo/analyze-repo.sh` (1629 lines) with thin wrapper (~50 lines):
   ```bash
   #!/bin/bash
   # /analyze-repo — thin wrapper, delegates to build-stack tool
   set -euo pipefail
   exec python -m build_stack analyze "$@"
   ```
2. Delete from skill dir: `tool-deps.json` (moved), `DETECTION_PRINCIPLES.md` (moved), `DATA_SCHEMA.md` (moved), `TESTING.md` (kept or moved per file inventory below).
3. Skill `SKILL.md` updated: reflects wrapper status, points to tool docs.
4. Skill remains a slash command (`/analyze-repo`), not a sub-skill of build-stack — independent invocation is the whole point.

**Exit criterion:** `wc -l .claude/skills/analyze-repo/analyze-repo.sh` < 100; `python -m build_stack analyze` and `/analyze-repo` produce identical output.

Phase 4 (skill removal) is **explicitly not planned** — independent `/analyze-repo` invocation is a deliberate UX feature.

---

## Frontend Skill Contract

Final shape after Phase 3:

```
.claude/skills/analyze-repo/
├── SKILL.md                  # ~30 lines: triggering description + usage
└── analyze-repo.sh        # ~50 lines: arg passthrough to tool
```

**Output channels (preserved from current skill — see existing `SKILL.md`):**
- `stdout` — JSON file path (single line, always)
- `stderr` — progress + markdown report when emit enabled
- `-q` / `--quiet` → suppress markdown
- `-v` / `--verbose` → emit markdown regardless of TTY
- Default: emit when stdout is a terminal

Tool's `--human` flag mirrors `-v`; tool's `--quiet` mirrors `-q`. Wrapper translates flags 1:1.

**Why keep the skill at all:** users invoke `/analyze-repo owner/repo` directly when they want a one-shot dependency report without the full build-stack workflow. Tool's CLI is also valid (`python -m build_stack analyze`), but the skill is the discoverable Claude-session UX entry.

---

## Cache Contract: `tool-deps.json`

| Concern | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| Path | `.claude/skills/analyze-repo/tool-deps.json` (unchanged) | Both old + new path; Python port reads new, falls back to old | `tools/build-stack/build_stack/data/tool-deps.json` only |
| Writer | bash skill | bash skill (Phase 2 Python port reads-only at first) | Python port |
| Format | unchanged JSON object | unchanged | unchanged |
| Migration | none | one-time copy old → new | delete old |

Bumping format requires a schema-version field — not currently present, deferred until needed. **Out of scope** for this sub-plan.

---

## Parity Test (Phase 2 exit gate)

**Test corpus:** existing `analyzed_repos/<owner>/<repo>/analysis.json` files committed to repo (post-Phase 1.5 migration). They are the golden output of the bash detector.

**Test driver** (lives at `tools/build-stack/tests/test_analyze_parity.py`):
```python
import json, subprocess
from pathlib import Path

CORPUS = Path("analyzed_repos")  # iterate every existing analysis.json

def test_parity():
    for analysis in CORPUS.rglob("analysis.json"):
        repo = f"{analysis.parent.parent.name}/{analysis.parent.name}"
        # Run Python port (Phase 2)
        new = json.loads(subprocess.check_output(
            ["python", "-m", "build_stack", "analyze", "--json-only", repo]
        ))
        old = json.loads(analysis.read_text())
        # Drop volatile fields before compare
        for d in (new, old):
            d.pop("analyzed_at", None)
        assert new == old, f"parity mismatch on {repo}"
```

**Diff failures handled how:** treat as port bugs in the Python detector, not as schema bumps. The bash detector is the spec until Phase 3 cutover; only after cutover can the Python port be the spec.

**Required commit:** Phase 2 cannot land unless parity test is green on every analysis.json in `analyzed_repos/`.

---

## File Inventory

### New files (Phase 1)
- `tools/build-stack/build_stack/analyze.py` — replaces stub (currently raises NotImplementedError) ✅ DONE

### Modified files (Phase 1.5 — OUT_DIR migration)
- `.claude/skills/analyze-repo/analyze-repo.sh` — flip `OUT_DIR` constant
- `.claude/skills/analyze-repo/SKILL.md` — output path table updates
- `.claude/skills/analyze-repo/DATA_SCHEMA.md` — output path examples
- `.claude/plans/build-workflow-stack-composition.md` — parent plan §6 Phase 3 path references
- `tools/build-stack/build_stack/analyze.py` — doc comment updates (no logic change)

### Renamed files (Phase 1.5 — `git mv`)
- `builds/anthropics/` → `analyzed_repos/anthropics/`
- `builds/danielrosehill/` → `analyzed_repos/danielrosehill/`
- `builds/garrytan/` → `analyzed_repos/garrytan/`
- `builds/hesreallyhim/` → `analyzed_repos/hesreallyhim/`
- `builds/peterkrueck/` → `analyzed_repos/peterkrueck/`
- `builds/santifer/` → `analyzed_repos/santifer/`
- `builds/sun2admin/` → `analyzed_repos/sun2admin/`

### New files (Phase 2)
- `tools/build-stack/build_stack/analyzers/__init__.py`
- `tools/build-stack/build_stack/analyzers/manifests.py`
- `tools/build-stack/build_stack/analyzers/dockerfile.py`
- `tools/build-stack/build_stack/analyzers/compose_yaml.py`
- `tools/build-stack/build_stack/analyzers/devcontainer.py`
- `tools/build-stack/build_stack/analyzers/envfiles.py`
- `tools/build-stack/build_stack/analyzers/source_scan.py`
- `tools/build-stack/build_stack/analyzers/readme.py`
- `tools/build-stack/build_stack/analyzers/apt_resolve.py`
- `tools/build-stack/build_stack/data/tool-deps.json` — moved
- `tools/build-stack/tests/test_analyze_parity.py`
- `tools/build-stack/tests/fixtures/` — repo snapshots if parity needs reproducible inputs

### Modified files (Phase 1)
- `tools/build-stack/build_stack/cli.py` — wire `analyze` subcommand handler

### Modified files (Phase 3)
- `.claude/skills/analyze-repo/analyze-repo.sh` — replaced with ~50-line wrapper
- `.claude/skills/analyze-repo/SKILL.md` — note wrapper status

### Deleted files (Phase 3)
- `.claude/skills/analyze-repo/tool-deps.json` — moved
- `.claude/skills/analyze-repo/DETECTION_PRINCIPLES.md` — moved (or kept if reference doc lives in skill dir for discoverability)
- `.claude/skills/analyze-repo/DATA_SCHEMA.md` — moved
- `.claude/skills/analyze-repo/TESTING.md` — moved or replaced with parity test pointer

**Open question:** keep reference docs co-located with skill (discoverability) or with tool (single source of truth)? Lean toward tool-side; skill `SKILL.md` adds a cross-link.

---

## Cutover Criteria (Phase 2 → 3)

All must be true before Phase 3 lands:

1. ✅ Parity test green on full `builds/` corpus
2. ✅ At least 3 different repo shapes covered in corpus (Python-only, Node-only, polyglot+Docker, devcontainer-using)
3. ✅ `python -m build_stack analyze` works without Claude session present
4. ✅ Tool consumed by parent plan's `compose` flow (Phase 3 of parent plan migration step §6) — i.e. the new analyze.py is exercised by `build-stack compose`, not just standalone
5. ✅ `tool-deps.json` migration verified: no detector queries the old path

---

## Dependencies on Parent Plan

This sub-plan now **blocks** parent plan migration step §6 Phases 4-6 (aggregate/select/compose/emit). Sequencing reversal from earlier draft.

- Sub-plan Phase 1 ✅ DONE — shell-out wrapper present
- Sub-plan Phase 1.5 (OUT_DIR + dir migration) — runs **before** any composition work
- Sub-plan Phase 2 (Python port + parity test) — runs **before** parent plan §6 Phases 4-6
- Sub-plan Phase 3 (cutover) — runs **before** parent plan §6 Phases 4-6
- Parent plan composition phases consume the **post-cutover** Python detector directly (no shell-out)

**Recommended ordering (revised 2026-05-06):**
sub-plan Phase 1 ✅ →
sub-plan Phase 1.5 (OUT_DIR + migrate) →
sub-plan Phase 2 (Python port) →
sub-plan Phase 3 (cutover) →
parent plan §6 Phases 4-6 (compose pipeline) →
parent plan: write `/build-stack` skill body.

Rationale: clean architecture upfront. Composition logic developed against real Python detector, not throwaway bash-shell-out wrapper.

---

## Resolved Decisions (2026-05-06)

| # | Question | Decision |
|---|---|---|
| OQ1 | PR boundary | **(b)** 3 commits in 1 PR — atomic per-phase, single review boundary |
| OQ2 | Phase 1.5 commit shape | **(a)** code change + git mv in single atomic commit |
| OQ3 | Port scope | **(b)** idiomatic Python — modules, dataclasses, type hints |
| OQ4 | Parity test mode | **(b)** semantic equivalence; driver normalizes (sort arrays + recursive compare) |
| OQ5 | Apt-cache during tests | **(a)** read tool-deps.json only; no live `apt-cache` queries |
| OQ6 | Reference docs location | **(b)** `tools/build-stack/docs/` |
| OQ7 | `--json-only` flag | **(b)** reuse existing `--quiet` flag; no new surface |
| OQ8 | Corpus growth | **(c)** both — synthetic required, real best-effort (skip if no `gh auth`) |
| OQ9 | Python deps | **(a)** `pyyaml` PyPI dep allowed; `tomllib` from stdlib |
| OQ10 | Self-analysis special case | **(a)** out of scope; defer to skill body work |

---

## Original Open Questions (preserved for context)

### OQ1 — Phase boundaries: one PR or three?

(a) Single mega-commit — Phase 1.5 + 2 + 3 land together
(b) Three commits in one PR — atomic per-phase, easier review
(c) Three PRs — small atomic landings

Lean (b): atomic per-phase commits, single PR boundary, parity test gates Phase 2→3 cleanly.

### OQ2 — Phase 1.5 OUT_DIR: code + git mv same commit, or separate?

(a) Single commit: bump `OUT_DIR` constant + `git mv builds/* analyzed_repos/*`
(b) Two commits: code change, then dir migration
(c) Reverse two: dir migration, then code change (but skill broken between commits)

Lean (a): atomic. Skill never broken. Re-running skill against same repo just rewrites.

### OQ3 — Python port scope: pure bash translation, or refactor while porting?

(a) **Pure translation** — line-for-line equivalent. Easy parity test pass. Ugly Python.
(b) **Idiomatic Python** — restructure for clarity (modules per detector, dataclass schemas, type hints). Higher regression risk; requires more careful parity test.

Lean (b) — given user mandate "clean arch upfront". Add idiomatic structure. Pay parity-test cost.

### OQ4 — Parity test: byte-exact JSON match, or semantic equivalence?

Detection emits sets in JSON arrays. Bash output may have undefined order; Python output may differ in ordering. Options:

(a) Byte-exact — sort all arrays before output in both bash AND Python (modify bash skill to add sort step pre-Phase 2)
(b) Semantic — test driver normalizes (sort arrays + recursive dict compare)
(c) Hybrid — Python emits sorted; bash either sorts now or test driver pre-sorts old output

Lean (b): semantic comparison in driver. Cleanest, no bash modifications.

### OQ5 — Apt-cache during parity test (CI)?

Container build CI may not have `apt-cache` populated for the same packages as dev environment. `apt_resolve.py` results could differ across envs.

(a) Mock `apt_resolve` in test — read from committed `tool-deps.json` only, no live queries
(b) Skip `system_deps` field comparison in parity test
(c) Require CI to seed apt cache before tests

Lean (a): tool-deps.json is the cache anyway; tests should use it as authoritative.

### OQ6 — Reference docs post-cutover?

`DETECTION_PRINCIPLES.md`, `DATA_SCHEMA.md`, `TESTING.md` currently in skill dir. After cutover skill is thin wrapper — these docs describe tool internals. Move where?

(a) `tools/build-stack/build_stack/analyzers/docs/` — co-located with implementation
(b) `tools/build-stack/docs/` — top-level tool docs
(c) Stay at `.claude/skills/analyze-repo/` — discoverable via skill reference reading
(d) `.claude/plans/analyze-repo/` — alongside other architecture docs

Lean (b): one tool docs dir, easy to find.

### OQ7 — `--json-only` flag for parity tests?

Bash skill emits markdown to stderr by default (TTY-detected). Tests need clean stdout. Options:

(a) Add `--json-only` flag (suppresses everything except JSON path on stdout, no markdown to stderr)
(b) Test driver passes existing `--quiet` flag (suppresses markdown only, progress traces still on stderr)

Lean (b): existing flag covers test need. No new surface.

### OQ8 — Test corpus growth strategy?

(a) Synthetic fixtures committed to `tools/build-stack/tests/fixtures/` — reproducible, deterministic
(b) Real-repo corpus at `analyzed_repos/` — grows naturally with usage
(c) Both — synthetic for edge cases, real for breadth

Lean (c).

### OQ9 — Python deps allowed?

Port may need: `pyyaml` (compose_yaml), `tomli`/`tomllib` (pyproject.toml). Standard-lib parsers prefer to keep `pyproject.toml` deps minimal.

(a) Allow `pyyaml` (PyPI dep)
(b) Shell out to `yq`/`python3 -c "import yaml"`
(c) Parse YAML by hand (regex)

Lean (a): pyyaml is universal, well-maintained. tomllib is stdlib in Python ≥ 3.11.

### OQ10 — Builder-project's own analysis migration

`builds/sun2admin/builder-project/` contains analysis of THIS repo. After migration: `analyzed_repos/sun2admin/builder-project/`. Does build-stack skill (later) treat self-analysis specially? Out of scope for this sub-plan (skill body work). Just flagging.

---

## Old Open Questions (resolved or absorbed)

- ~~Tool entry mode for analyze~~ → resolved: `python -m build_stack analyze <repo>`

---

## Follow-up Sub-Plans (post-2026-05-06)

This plan is complete (Phase 1.5 + 2 + 3 + aggregate/select/compose/emit + /build-stack skill body all shipped). Subsequent work split into focused sub-plans:

- **`./manage-rec-plugins.md`** — `/manage-rec-plugins` + `/manage-known-marketplaces` skill pair, shared selector lib, hybrid plugin delivery model (recommended L3 image + devcontainer features), per-plugin sparse-checkout analyze. Locked SPQ1–12 + MKMQ1–6. MCP server handling deferred to MCPQ1–7 thread within.
- **`./deploy-stack.md`** — *(not yet written)* `/deploy-stack` skill: image build/rebuild, GHCR push, devcontainer rebuild trigger. Bookmarked from /build-stack handoff (deploy y/N prompt).
