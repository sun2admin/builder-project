"""Phase 3 — invoke analyze-repo per repo.

Phase 1 (now): shells out to `.claude/skills/analyze-repo/analyze-repo.sh`
Phase 2 (future): Python port of detection logic
Phase 3 (future): cutover — analyze-repo skill becomes thin wrapper for `build-stack analyze`

See `.claude/plans/build-stack-absorb-analyze.md`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    """builder-project repo root.

    Path layout: tools/build-stack/build_stack/analyze.py.
    parents[0]=build_stack, [1]=build-stack, [2]=tools, [3]=repo root.
    """
    return Path(__file__).resolve().parents[3]


def _skill_script() -> Path:
    script = _repo_root() / ".claude" / "skills" / "analyze-repo" / "analyze-repo.sh"
    if not script.exists():
        raise FileNotFoundError(f"analyze-repo.sh not found at {script}")
    return script


def analyze(repo: str) -> dict:
    """In-process API: run analyze-repo skill and return parsed analysis.json.

    Used by `compose.py` aggregation. Always quiet (no markdown emit on stderr)
    since callers consume the returned dict, not stderr output.
    """
    script = _skill_script()
    result = subprocess.run(
        [str(script), "-q", repo],
        capture_output=True,
        text=True,
        check=True,
    )
    path = Path(result.stdout.strip())
    if not path.exists():
        raise RuntimeError(
            f"analyze-repo emitted path {path} but file does not exist"
        )
    return json.loads(path.read_text())


def cmd_analyze(repo: str, *, human: bool = False, quiet: bool = False) -> int:
    """CLI wrapper: passthrough to skill, preserve stdout/stderr channels.

    Skill writes JSON path to stdout, markdown to stderr when emit enabled.
    --human → -v (force markdown emit on stderr)
    --quiet → -q (suppress markdown emit)
    Default: skill TTY-detects.
    """
    script = _skill_script()
    args: list[str] = [str(script)]
    if human:
        args.append("-v")
    elif quiet:
        args.append("-q")
    args.append(repo)
    return subprocess.run(args).returncode
