# build-stack: Absorb analyze-repo into Tool

**Status:** Active — sub-plan of [`build-workflow-stack-composition.md`](./build-workflow-stack-composition.md). Scope-bounded execution recipe for the `analyze-repo` migration phases (Phase 1 → 3) defined in the parent plan.

**Parent plan migration step:** §6 Phase 3 ("analyze: shell out to existing analyze-repo skill"); also implements parent §"analyze-repo migration phases" Phase 1, 2, 3.

**Why this sub-plan:** The parent plan defines architecture and merge rules but treats `analyze` as one bullet. Absorbing the 1629-line bash detector into the Python tool is the first slice that gives the tool real logic — it must be planned independently or it derails the parent.

---

## Goal

End state (after all phases of this sub-plan):

1. `tools/build-stack/build_stack/analyze.py` is the **single source of truth** for repo detection.
2. `/analyze-repo` skill is a **thin bash wrapper** (~50 lines) that shells out to `python -m build_stack analyze --human <repo>`.
3. `tool-deps.json` cache lives at `tools/build-stack/build_stack/data/tool-deps.json` (moved from skill dir).
4. Parity validated against existing test corpus — same `analysis.json` byte output for the same input repo.

Out of scope:
- Composition logic (`select.py`, `compose.py`, `emit.py`) — belongs in parent plan §6 Phases 5-6.
- New detection fields beyond what `analyze-repo.sh` already emits — pure port, not refactor.

---

## Migration Phases

Mapped to the parent plan's "analyze-repo migration phases" table (§Architecture).

### Phase 1 — Shell-out wrapper (first build-stack release)

**Goal:** `build-stack analyze <repo>` works end-to-end by subprocessing the existing skill. Zero detection logic in the tool yet.

**Deliverables:**
1. `analyze.py::analyze(repo: str) -> dict` — invokes `analyze-repo.sh <repo>` via `subprocess`, reads emitted `builds/<owner>/<repo>/analysis.json`, returns parsed dict.
2. `analyze.py::format_human(result: dict) -> str` — STUB. Returns existing `analysis.md` contents (skill already writes it). No re-rendering.
3. `cli.py` wires `analyze` subcommand: `--human` flag prints markdown to stderr; JSON path always to stdout.
4. `compose.py` calls `analyze.analyze()` per-repo (used by parent plan §6 aggregation).

**Tool side does not yet own detection.** Skill remains canonical detector. Tool is a passthrough.

**Exit criterion:** `python -m build_stack analyze --human sun2admin/builder-project` produces identical stdout/stderr to `bash .claude/skills/analyze-repo/analyze-repo.sh -v sun2admin/builder-project` (modulo trace-line ordering, which is non-load-bearing).

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

**Test corpus:** existing `builds/<owner>/<repo>/analysis.json` files committed to repo. They are the golden output of the bash detector.

**Test driver** (lives at `tools/build-stack/tests/test_analyze_parity.py`):
```python
import json, subprocess
from pathlib import Path

CORPUS = Path("builds")  # iterate every existing analysis.json

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

**Required commit:** Phase 2 cannot land unless parity test is green on every analysis.json in `builds/`.

---

## File Inventory

### New files (Phase 1)
- `tools/build-stack/build_stack/analyze.py` — replaces stub (currently raises NotImplementedError)

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

This sub-plan unblocks parent plan migration step §6 Phase 3 ("analyze: shell out to existing analyze-repo skill"). Specifically:

- Sub-plan Phase 1 = parent plan Phase 1 (shell-out wrapper present)
- Sub-plan Phase 2-3 happen after parent plan migration steps §6 Phases 4-6 (aggregate/select/compose/emit) are at least skeletally done — no point porting detection until the consumer exists and can drive integration tests.

**Recommended ordering:** sub-plan Phase 1 → parent plan §6 Phase 4-6 (skeleton compose pipeline) → sub-plan Phase 2 (port + parity test) → sub-plan Phase 3 (cutover).

---

## Open Questions

- **Tool entry mode for analyze:** `python -m build_stack analyze <repo>` (current cli.py shape) vs `python -m build_stack.analyze <repo>` (module main)? Pick first — keeps subcommand surface uniform.
- **`--json-only` flag:** add for parity test convenience (suppress all stderr), or test driver passes `--quiet` and parses stdout only? Pick `--quiet` if existing flag covers it.
- **Reference doc location post-cutover:** skill dir vs tool dir? Lean tool dir — single source of truth.
- **Test corpus growth:** parity test runs on whatever lands in `builds/`. Should the corpus include explicitly synthetic fixtures (plugin repos, sandbox-only scenarios), or rely on real repo runs accumulating naturally? Lean synthetic — reproducibility.
- **Apt-cache cache during CI:** does CI environment have `apt-cache` available for `apt_resolve.py`? If not, parity test must mock or use `tool-deps.json` as authoritative. Pick: read-only from cache during tests, no live `apt-cache` queries.
