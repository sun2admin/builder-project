---
name: build-stack
description: Compose a complete container stack (L1 base image + L2 AI CLI + L3 plugin layer + L4 devcontainer features) for a project. Walks the user through choosing AI CLI, project repo (or sandbox), 0+ plugin repos. Aggregates dependencies via analyze-repo per repo. Picks the minimum L1 variant covering all deps + offers user override. Generates devcontainer.json + workspace.env. Use when the user wants to scaffold, redesign, or rebuild a Claude/Gemini development workspace stack from a repo's actual dependencies.
shortcut: bs
usage: |
  /build-stack [--dry-run]

  Walks Phase 1 (gather intent) interactively, writes builds/<name>/build.json,
  invokes the build-stack tool to compose the stack, and shows the summary.

  Options:
    --dry-run    Skip tool invocation; print the build.json that would be written.
---

# /build-stack

Front-facing skill for the **build-stack** workflow. Collects user intent, validates, writes `builds/<name>/build.json`, then invokes the **build-stack tool** (Python, in `tools/build-stack/`) which performs all heavy lifting.

## Architecture

This skill is the UX layer. All composition logic lives in the tool:

| Layer | Lives in | Role |
|---|---|---|
| **Skill** (`/build-stack`) | `.claude/skills/build-stack/` | Phases 1-2: gather intent, write JSON, invoke tool |
| **Tool** (`build-stack` CLI) | `tools/build-stack/` | Phases 3-6: analyze, aggregate, compose, emit |
| **Contract** | `builds/<name>/build.json` | Versioned JSON between skill and tool |

See `.claude/plans/build-workflow-stack-composition.md` for full design.

## Workflow

```
/build-stack
   ↓
Phase 1: Gather (this skill)
   ─ Choose AI CLI (claude / gemini)
   ─ Choose project repo (owner/repo) OR sandbox (no repo)
   ─ Choose 0+ plugin repos to include
   ─ Optional: override base image, additional L4 features, credential delivery
   ↓
Phase 2: Validate + invoke tool (this skill)
   ─ Write builds/<name>/build.json
   ─ Run: build-stack validate <build.json>
   ─ Run: build-stack compose <build.json>
   ↓
Phase 3-6: Tool work (Python)
   ─ Analyze project + each plugin via analyze-repo
   ─ Aggregate analyses
   ─ Pick minimum L1 variant covering deps (user can override upward)
   ─ Compose L4 features, version overlays, firewall, init chain
   ─ Emit devcontainer.json + workspace.env
   ↓
Display summary to user
```

## Tool dependency

The tool must be installed where this skill runs:

```bash
pip install -e tools/build-stack/
```

Or invoked directly via `python -m build_stack`.

The skill calls `build-stack validate` before `compose` — refuses to invoke compose if build.json fails schema check.

## Output

| File | Written by |
|---|---|
| `builds/<name>/build.json` | Skill (Phase 2) |
| `builds/<name>/aggregated.json` | Tool (Phase 4) |
| `analyzed_repos/<owner>/<repo>/analysis.json` (per repo) | analyze-repo skill (invoked by /build-stack skill, read by tool) |
| `builds/<name>/devcontainer.json` | Tool (Phase 6) |
| `builds/<name>/workspace.env` | Tool (Phase 6, for backward-compat with old workflow) |
