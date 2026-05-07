"""Phase 2 Python port of the analyze-repo skill (parity-gated).

Public API:
    analyze(repo: str) -> dict          # full pipeline, returns analysis dict
    write_outputs(data, out_dir)        # write analysis.json + analysis.md

Pipeline order (must run in sequence — later modules read earlier output):
    1. cloner.clone(repo)              → tmp clone path
    2. manifests.detect()              → languages, libraries, etc.
    3. dockerfile.detect()             → system_packages, container, env_vars
    4. source_scan.detect()            → inferred.*, services, mcp, plugins
    5. apt_resolve.resolve()           → system_deps
    6. orchestrator pops suggested,
       computes _new/_confirmed dedup,
       sets analyzed_at + primary_language

Phase 2 contract: skill is canonical; this port runs alongside under
`build-stack analyze-port` for parity validation. Phase 3 cutover swaps
the skill body to a thin wrapper around this package.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import apt_resolve, cloner, dockerfile, manifests, source_scan
from .schema import AnalysisResult


def _repo_metadata(repo: str) -> tuple[str, str]:
    """Fetch (description, primary_language) via `gh api repos/<repo>`."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}",
             "--jq", "{description: .description, language: .language}"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            return d.get("description") or "", d.get("language") or ""
    except Exception:
        pass
    return "", ""


def analyze(repo: str) -> dict:
    """Full pipeline: clone repo, run all detectors, return analysis dict.

    Output dict matches the bash skill's analysis.json shape exactly
    (`schema_version: 2`). Caller writes it via `write_outputs(data, out_dir)`
    or serializes directly with `json.dump(data, f, indent=2)`.
    """
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError(f"expected owner/repo format, got {repo!r}")

    description, primary_language = _repo_metadata(repo)

    repo_path = cloner.clone(repo)
    try:
        result = AnalysisResult(
            repo=repo,
            project=repo.split("/")[1],
            analyzed_at=date.today().strftime("%Y-%m-%d"),
            primary_language=primary_language,
        )

        marketplace_path = repo_path / ".claude-plugin" / "marketplace.json"
        if marketplace_path.is_file():
            _populate_marketplace_summary(marketplace_path, result)
        else:
            manifests.detect(repo_path, result, repo_description=description)
            dockerfile.detect(repo_path, result)
            source_scan.detect(repo_path, result)
            apt_resolve.resolve(repo_path, result)
    finally:
        cloner.cleanup(repo_path)

    data = asdict(result)
    # Match bash skill: do not emit `suggested` field. Schema keeps the
    # dataclass for future use; the field is filtered at serialization.
    data.pop("suggested", None)
    return data


def _populate_marketplace_summary(marketplace_path: Path, result: AnalysisResult) -> None:
    """Mark the result as a marketplace and extract its plugin registry.

    Marketplace repos are skipped from normal detector flow (their deps
    describe a registry, not application code). Per-plugin analysis runs
    separately via `analyze_plugin()` for the plugins the user selects.
    """
    try:
        data = json.loads(marketplace_path.read_text())
    except (OSError, json.JSONDecodeError):
        return
    result.is_marketplace = True
    result.marketplace_name = data.get("name") or ""
    plugins = data.get("plugins") or []
    result.marketplace_plugins = [
        {
            "name": p.get("name", ""),
            "category": p.get("category"),
            "description": p.get("description", ""),
            "source": p.get("source"),
        }
        for p in plugins
        if isinstance(p, dict) and p.get("name")
    ]


def write_outputs(data: dict, out_dir: Path) -> Path:
    """Write analysis.json (+ analysis.md when report.render is implemented)
    to `out_dir`. Returns path to analysis.json.

    Creates `out_dir` if missing.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "analysis.json"
    json_path.write_text(json.dumps(data, indent=2) + "\n")

    md_path = out_dir / "analysis.md"
    try:
        from . import report
        md_path.write_text(report.render(data))
    except NotImplementedError:
        # Phase 2 in-progress: report renderer pending. JSON is the
        # canonical artifact; MD is human-readable companion.
        pass

    return json_path
