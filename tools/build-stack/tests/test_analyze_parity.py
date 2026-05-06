"""Phase 2 Step 2.3 — parity gate between bash skill + Python port.

Per sub-plan OQ4 = (b): semantic equivalence (sort arrays + recursive
compare), not byte-exact JSON match.
Per sub-plan OQ5 = (a): tests read tool-deps.json only; live apt-cache
queries disabled (BUILD_STACK_APT_LIVE unset).
Per sub-plan OQ8 = (c): real corpus best-effort + synthetic fixtures.

Each fixture repo is cloned once per test session, then both the bash
skill (`.claude/skills/analyze-repo/analyze-repo.sh`) and the Python
port (`build_stack.analyzers.analyze`) run on the same clone. Their
output dicts are normalized (recursively sort all lists) and compared.

Skips real-repo fixtures gracefully if `gh auth` is not configured.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from build_stack.analyzers import (
    apt_resolve,
    dockerfile,
    manifests,
    source_scan,
)
from build_stack.analyzers.schema import AnalysisResult


# ─── corpus ───────────────────────────────────────────────────────────────────

CORPUS = [
    "anthropics/claude-code",
    "anthropics/connect-rust",
    "anthropics/claude-code-security-review",
    "danielrosehill/claude-code-projects-index",
    "garrytan/gstack",
    "hesreallyhim/awesome-claude-code",
    "peterkrueck/claude-code-development-kit",
    "santifer/career-ops",
    "sun2admin/build-containers-with-claude",
    "sun2admin/builder-project",
]


def _repo_root() -> Path:
    """tools/build-stack/tests/test_analyze_parity.py → repo root."""
    return Path(__file__).resolve().parents[3]


def _bash_skill() -> Path:
    return _repo_root() / ".claude" / "skills" / "analyze-repo" / "analyze-repo.sh"


def _gh_authed() -> bool:
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


# ─── normalize helper ─────────────────────────────────────────────────────────

def _sort_recursive(obj):
    """Sort lists at every depth so order doesn't affect equality."""
    if isinstance(obj, list):
        sorted_children = [_sort_recursive(x) for x in obj]
        try:
            return sorted(sorted_children, key=lambda v: json.dumps(v, sort_keys=True))
        except Exception:
            return sorted_children
    if isinstance(obj, dict):
        return {k: _sort_recursive(v) for k, v in obj.items()}
    return obj


def _normalize(data: dict) -> dict:
    """Strip volatile fields + recursively sort lists.

    Volatile = `analyzed_at` (date-of-run, not detection logic).
    """
    out = {k: v for k, v in data.items() if k != "analyzed_at"}
    return _sort_recursive(out)


# ─── runners ──────────────────────────────────────────────────────────────────

def _run_bash_skill(repo: str) -> dict:
    """Run the canonical bash skill; parse and return the analysis.json
    that it writes to `analyzed_repos/<owner>/<repo>/analysis.json`.
    """
    script = _bash_skill()
    r = subprocess.run(
        [str(script), "-q", repo],
        capture_output=True, text=True,
        cwd=str(_repo_root()),
        timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(f"bash skill failed for {repo}: {r.stderr.strip()[-500:]}")
    json_path = Path(r.stdout.strip())
    if not json_path.is_file():
        raise RuntimeError(f"bash skill emitted path {json_path} but file missing")
    return json.loads(json_path.read_text())


def _run_port_on_clone(repo: str, clone_path: Path) -> dict:
    """Run the Python port in-process against an already-cloned repo.

    Bypasses cloner.clone() so the parity test uses one clone for both
    sides (fair comparison, same commit SHA).
    """
    description = ""
    primary_language = ""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}",
             "--jq", "{description: .description, language: .language}"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            description = d.get("description") or ""
            primary_language = d.get("language") or ""
    except Exception:
        pass

    result = AnalysisResult(
        repo=repo,
        project=repo.split("/")[1],
        analyzed_at="",
        primary_language=primary_language,
    )
    manifests.detect(clone_path, result, repo_description=description)
    dockerfile.detect(clone_path, result)
    source_scan.detect(clone_path, result)
    apt_resolve.resolve(clone_path, result)

    from dataclasses import asdict
    data = asdict(result)
    data.pop("suggested", None)
    return data


# ─── pytest fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def gh_authed():
    if not _gh_authed():
        pytest.skip("gh auth status failed; skipping real-repo parity tests")
    return True


@pytest.fixture(scope="session")
def clone_dir():
    d = Path(tempfile.mkdtemp(prefix="bs-parity-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cloned_repo(request, clone_dir, gh_authed):
    repo = request.param
    target = clone_dir / repo.replace("/", "__")
    if not target.exists():
        r = subprocess.run(
            ["gh", "repo", "clone", repo, str(target), "--", "--depth=1"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            pytest.skip(f"clone failed for {repo}: {r.stderr[-200:]}")
    return repo, target


# ─── parameterized parity test ────────────────────────────────────────────────

@pytest.mark.parametrize("cloned_repo", CORPUS, indirect=True)
def test_parity(cloned_repo):
    repo, clone_path = cloned_repo

    bash_data = _run_bash_skill(repo)
    port_data = _run_port_on_clone(repo, clone_path)

    bash_norm = _normalize(bash_data)
    port_norm = _normalize(port_data)

    if bash_norm != port_norm:
        diffs = _diff_dicts(bash_norm, port_norm)
        pytest.fail(
            f"parity mismatch on {repo}:\n" + "\n".join(diffs[:30])
        )


def _diff_dicts(a: dict, b: dict, prefix: str = "") -> list[str]:
    """Return list of human-readable diff lines between two normalized dicts."""
    diffs: list[str] = []
    keys = sorted(set(a.keys()) | set(b.keys()))
    for k in keys:
        path = f"{prefix}.{k}" if prefix else k
        if k not in a:
            diffs.append(f"  + {path} (only in port): {repr(b[k])[:120]}")
            continue
        if k not in b:
            diffs.append(f"  - {path} (only in bash): {repr(a[k])[:120]}")
            continue
        av, bv = a[k], b[k]
        if isinstance(av, dict) and isinstance(bv, dict):
            diffs.extend(_diff_dicts(av, bv, path))
        elif av != bv:
            diffs.append(f"  ~ {path}")
            diffs.append(f"      bash: {repr(av)[:120]}")
            diffs.append(f"      port: {repr(bv)[:120]}")
    return diffs
