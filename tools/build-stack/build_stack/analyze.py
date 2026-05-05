"""Phase 3 — invoke analyze-project per repo.

Phase 1 (now): shells out to the existing `.claude/skills/analyze-project/analyze-project.sh`
Phase 2 (future): Python port of detection logic
Phase 3 (future): cutover — analyze-project skill becomes thin wrapper for `build-stack analyze`

See plan §"analyze-project migration phases".
"""

from __future__ import annotations


def analyze_repo(repo: str) -> int:
    """Run analyze-project for `owner/repo`. Phase 1 shells out to skill."""
    raise NotImplementedError(
        "analyze.analyze_repo is a stub. Phase 1 implementation: "
        "subprocess.run([analyze-project.sh, repo]) and return its exit code."
    )
