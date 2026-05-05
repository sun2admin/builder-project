"""Phase 3 — invoke analyze-repo per repo.

Phase 1 (now): shells out to the existing `.claude/skills/analyze-repo/analyze-repo.sh`
Phase 2 (future): Python port of detection logic
Phase 3 (future): cutover — analyze-repo skill becomes thin wrapper for `build-stack analyze`

See plan §"analyze-repo migration phases".
"""

from __future__ import annotations


def analyze_repo(repo: str) -> int:
    """Run analyze-repo for `owner/repo`. Phase 1 shells out to skill."""
    raise NotImplementedError(
        "analyze.analyze_repo is a stub. Phase 1 implementation: "
        "subprocess.run([analyze-repo.sh, repo]) and return its exit code."
    )
