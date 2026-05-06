"""Clone a GitHub repo into a temp dir via `gh repo clone`.

Mirrors the bash skill's clone behavior so private-repo + auth handling
matches identically (sub-plan Phase 2 Q2 → option (a) "shell out to gh").
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def clone(repo: str) -> Path:
    """Shallow-clone `<owner>/<repo>` into a fresh tmp dir, return path.

    Caller owns the returned dir and must `shutil.rmtree` when done
    (or use `cleanup()` helper).
    """
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError(f"expected owner/repo format, got {repo!r}")

    tmp = Path(tempfile.mkdtemp(prefix="bs-analyze-"))
    target = tmp / repo.split("/")[1]

    result = subprocess.run(
        ["gh", "repo", "clone", repo, str(target), "--", "--depth=1"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(
            f"gh repo clone {repo} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return target


def cleanup(repo_path: Path) -> None:
    """Remove the temp dir created by `clone()`."""
    if repo_path.parent.name.startswith("bs-analyze-"):
        shutil.rmtree(repo_path.parent, ignore_errors=True)
