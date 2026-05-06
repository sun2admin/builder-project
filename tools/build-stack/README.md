# build-stack tool

Composition engine for the `/build-stack` skill. Reads a `build.json` describing user intent, runs `analyze-repo` on each referenced repo, aggregates dependencies, picks the minimum L1 variant covering all deps, composes L4 devcontainer features, and emits `devcontainer.json` + `workspace.env`.

See `.claude/plans/build-workflow-stack-composition.md` for the full design.

## Install

From the builder-project root:

```bash
pip install -e tools/build-stack/
```

Or invoke directly without install:

```bash
python -m build_stack <subcommand> <args>
```

## Subcommands

| Command | Description |
|---|---|
| `build-stack validate <build.json>` | JSON-schema check + reachability validation |
| `build-stack compose <build.json>`  | Full Phase 3-6 pipeline (analyze → aggregate → compose → emit) |
| `build-stack analyze [--human\|--quiet] <owner/repo>` | Standalone single-repo detection. Phase 1: shells out to `.claude/skills/analyze-repo/analyze-repo.sh`. Phase 2: Python port. |
| `build-stack diff <build-a> <build-b>` | Future: stack-diff for review |
| `build-stack stats <builds-dir>`    | Future: promotion-path metrics |
| `build-stack rebuild builds/<name>` | Future: re-emit outputs from existing build.json |

## Architecture

```
build_stack/
├── cli.py            # argparse subcommand dispatch
├── analyze.py        # Phase 3: invokes analyze-repo (skill or Python port)
├── aggregate.py      # Phase 4: multi-repo merge (per plan §1 merge rules)
├── select.py         # Phase 5a: L1 capability cover, L3 plugin layer pick
├── compose.py        # Phase 5b: L4 features, version overlays, firewall, init chain
├── emit.py           # Phase 6: devcontainer.json + workspace.env writers
├── ghcr.py           # GHCR manifest queries, OCI label reads
└── schema/
    └── build-input.schema.json
```

## Status

| Subcommand | Status |
|---|---|
| `validate` | ✅ Implemented (schema check) |
| `analyze` | ✅ Phase 1 — shells out to `analyze-repo` skill |
| `compose` | 🚧 Stub — Phases 3-6 pipeline pending |
| `diff` / `stats` / `rebuild` | 🔜 Future |

Tracking in:
- `.claude/plans/build-workflow-stack-composition.md` — full design + parent migration steps
- `.claude/plans/build-stack-absorb-analyze.md` — `analyze` skill→tool absorption sub-plan
