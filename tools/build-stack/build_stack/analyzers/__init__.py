"""Phase 2 Python port of the analyze-repo skill (parity-gated).

Public API:
    analyze(repo: str) -> dict          # full analysis pipeline, returns analysis dict
    write_outputs(data, out_dir)        # write analysis.json + analysis.md alongside

Module split mirrors detector boundaries in analyze-repo.sh:
    cloner       — gh repo clone <owner>/<repo> <tmp>
    manifests    — language manifest parsers (package.json, requirements.txt, etc.)
    dockerfile   — Dockerfile RUN/EXPOSE/ENV/etc. scanners
    source_scan  — source-tree inference (tool calls, imports)
    apt_resolve  — tool-deps.json cache + apt-cache fallback
    report       — markdown report emit
    schema       — dataclasses for analysis result shape

Phase 2 contract: skill is canonical; this port runs alongside under
`build-stack analyze-port` for parity validation. Phase 3 cutover swaps
the skill body to a thin wrapper around this package.

See `.claude/plans/build-stack-absorb-analyze.md`.
"""

from __future__ import annotations

from pathlib import Path


def analyze(repo: str) -> dict:
    """Full pipeline: clone repo, run all detectors, return analysis dict.

    Phase 2 stub — raises NotImplementedError until detectors land.
    """
    raise NotImplementedError(
        "analyzers.analyze() is Phase 2 work-in-progress. "
        "See .claude/plans/build-stack-absorb-analyze.md Phase 2 deliverables."
    )


def write_outputs(data: dict, out_dir: Path) -> None:
    """Write analysis.json + analysis.md to `out_dir`.

    Creates `out_dir` if missing. JSON is sorted-keys, indent=2; markdown
    is rendered via `report.render(data)`.

    Phase 2 stub — implementation lands with `report.py`.
    """
    raise NotImplementedError(
        "analyzers.write_outputs() pending — depends on report.render()."
    )
