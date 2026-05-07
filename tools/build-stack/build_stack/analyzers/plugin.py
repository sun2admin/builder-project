"""Plugin analyzer: clone+sparse-checkout one plugin from a marketplace.

Per Q1-Q5 in .claude/plans/manage-rec-plugins.md:
    Q1: full AnalysisResult (reuses the same analyzer pipeline as analyze-repo)
    Q2: cache layout keyed by marketplace owner/repo
    Q3: all 3 source shapes supported (git-subdir, url object, "./" string)
    Q5: aggregate.py orchestrates calls (per build-input.json plugin_selections)

Plugin sources can live in repos external to the marketplace. Cloning uses
plain `git clone --filter=blob:none --sparse` so arbitrary HTTPS URLs work
(unlike the analyze-repo path which uses `gh repo clone` and is restricted
to owner/repo format).
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import apt_resolve, dockerfile, manifests, source_scan
from .schema import AnalysisResult


def _marketplace_cache_path(repo_root: Path, marketplace: str) -> Path:
    owner, repo = marketplace.split("/", 1)
    return repo_root / "analyzed_repos" / "marketplaces" / owner / repo / "marketplace.json"


def _fetch_marketplace_json(marketplace: str, dest: Path) -> None:
    """Fetch and cache .claude-plugin/marketplace.json via `gh api`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["gh", "api",
         f"repos/{marketplace}/contents/.claude-plugin/marketplace.json",
         "--jq", ".content"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"failed to fetch {marketplace} marketplace.json: {r.stderr.strip()}"
        )
    content = base64.b64decode(r.stdout.strip())
    if not content.strip():
        raise RuntimeError(f"empty marketplace.json from {marketplace}")
    json.loads(content)  # validate
    dest.write_bytes(content)


def _load_marketplace_json(marketplace: str, repo_root: Path) -> dict:
    cache = _marketplace_cache_path(repo_root, marketplace)
    if not cache.is_file():
        _fetch_marketplace_json(marketplace, cache)
    return json.loads(cache.read_text())


def _find_plugin_entry(market_data: dict, plugin: str) -> dict:
    for p in market_data.get("plugins") or []:
        if isinstance(p, dict) and p.get("name") == plugin:
            return p
    raise ValueError(
        f"plugin {plugin!r} not found in marketplace "
        f"{market_data.get('name') or '(unnamed)'!r}"
    )


def _resolve_source(plugin_entry: dict, marketplace: str) -> dict:
    """Normalize the 3 source shapes into a single dict.

    Returns: {kind, url, path, ref, sha}
        kind: "git-subdir" | "url" | "self"
        path: subdir within the cloned repo (empty = use repo root)
    """
    src = plugin_entry.get("source")
    if isinstance(src, str):
        rel = src.strip()
        if rel.startswith("./"):
            rel = rel[2:]
        rel = rel.strip("/")
        path = "" if rel in ("", ".") else rel
        return {
            "kind": "self",
            "url": f"https://github.com/{marketplace}.git",
            "path": path,
            "ref": "",
            "sha": "",
        }
    if isinstance(src, dict):
        return {
            "kind": src.get("source") or "",
            "url": src.get("url") or "",
            "path": (src.get("path") or "").strip("/"),
            "ref": src.get("ref") or "",
            "sha": src.get("sha") or "",
        }
    raise ValueError(f"unrecognized plugin source shape: {src!r}")


def _clone_sparse(source: dict) -> tuple[Path, Path]:
    """Clone source.url into a fresh temp dir; sparse-checkout source.path
    when set. Returns (tmp_parent, plugin_subdir). Caller must rm tmp_parent.
    """
    if not source.get("url"):
        raise ValueError("source missing url")

    tmp_parent = Path(tempfile.mkdtemp(prefix="bs-plugin-"))
    clone_root = tmp_parent / "clone"

    cmd = ["git", "clone", "--depth=1", "--filter=blob:none", "--quiet"]
    if source["path"]:
        cmd.append("--sparse")
    if source["ref"]:
        cmd += ["--branch", source["ref"]]
    cmd += [source["url"], str(clone_root)]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(tmp_parent, ignore_errors=True)
        raise RuntimeError(f"git clone failed: {r.stderr.strip()}")

    if source["sha"]:
        # Best-effort SHA pin. Some servers refuse arbitrary-SHA fetch on
        # shallow repos; fall back to the ref-fetched HEAD silently.
        fetch = subprocess.run(
            ["git", "fetch", "--depth=1", "origin", source["sha"]],
            cwd=clone_root, capture_output=True, text=True,
        )
        if fetch.returncode == 0:
            subprocess.run(
                ["git", "checkout", source["sha"]],
                cwd=clone_root, capture_output=True, text=True,
            )

    if source["path"]:
        r3 = subprocess.run(
            ["git", "sparse-checkout", "set", source["path"]],
            cwd=clone_root, capture_output=True, text=True,
        )
        if r3.returncode != 0:
            shutil.rmtree(tmp_parent, ignore_errors=True)
            raise RuntimeError(f"sparse-checkout failed: {r3.stderr.strip()}")

    plugin_subdir = clone_root / source["path"] if source["path"] else clone_root
    if not plugin_subdir.is_dir():
        shutil.rmtree(tmp_parent, ignore_errors=True)
        raise RuntimeError(
            f"plugin subdir not found after sparse-checkout: {source['path']!r}"
        )
    return tmp_parent, plugin_subdir


def analyze_plugin(marketplace: str, plugin: str, repo_root: Path | None = None) -> dict:
    """Run the full analyzer pipeline on one plugin from a marketplace.

    Returns a dict matching analyze-repo's analysis.json shape, with three
    extra fields appended for traceability: marketplace, plugin, plugin_source.
    """
    if "/" not in marketplace or marketplace.count("/") != 1:
        raise ValueError(f"expected owner/repo for marketplace, got {marketplace!r}")
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]

    market_data = _load_marketplace_json(marketplace, repo_root)
    plugin_entry = _find_plugin_entry(market_data, plugin)
    source = _resolve_source(plugin_entry, marketplace)

    tmp_parent, plugin_dir = _clone_sparse(source)
    try:
        result = AnalysisResult(
            repo=f"{marketplace}#{plugin}",
            project=plugin,
            analyzed_at=date.today().strftime("%Y-%m-%d"),
            primary_language="",
            purpose=plugin_entry.get("description") or "",
        )
        manifests.detect(plugin_dir, result,
                         repo_description=plugin_entry.get("description") or "")
        dockerfile.detect(plugin_dir, result)
        source_scan.detect(plugin_dir, result)
        apt_resolve.resolve(plugin_dir, result)
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)

    data = asdict(result)
    data.pop("suggested", None)
    data["marketplace"] = marketplace
    data["plugin"] = plugin
    data["plugin_source"] = source
    return data


def plugin_cache_dir(repo_root: Path, marketplace: str, plugin: str) -> Path:
    """Per-Q2: analyzed_repos/plugins/<mkt_owner>/<mkt_repo>/<plugin>/."""
    owner, repo = marketplace.split("/", 1)
    return repo_root / "analyzed_repos" / "plugins" / owner / repo / plugin


def write_plugin_outputs(data: dict, repo_root: Path, marketplace: str, plugin: str) -> Path:
    out_dir = plugin_cache_dir(repo_root, marketplace, plugin)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "analysis.json"
    json_path.write_text(json.dumps(data, indent=2) + "\n")
    return json_path
