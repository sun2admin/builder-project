"""apt-cache resolver with persistent tool-deps.json cache.

Resolves `inferred.tools` + `inferred.ci_tools` → apt package names via
`apt-cache show <tool>` (then `dpkg -S */bin/<tool>` fallback). Result
cached in `tools/build-stack/build_stack/data/tool-deps.json`.

Tools with no apt package resolve to `apt_package: null` and are cached
to avoid re-querying. Only tools with a non-null apt_package land in
`result.system_deps`.

Live apt-cache queries gated behind `BUILD_STACK_APT_LIVE=1` env var
(off by default during parity tests per sub-plan OQ5 = (a)).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .schema import AnalysisResult, SystemDep


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def cache_path() -> Path:
    return _data_dir() / "tool-deps.json"


def load_cache() -> dict[str, dict]:
    p = cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_cache(cache: dict[str, dict]) -> None:
    cache_path().write_text(
        json.dumps(cache, indent=2, sort_keys=True) + "\n"
    )


def _live_resolve(tool: str) -> dict:
    """Live apt-cache lookup. Returns {apt_package, apt_depends}."""
    try:
        r = subprocess.run(
            ["apt-cache", "show", tool],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            deps: list[str] = []
            for line in r.stdout.splitlines():
                if line.startswith("Depends:"):
                    for dep in line[len("Depends:"):].strip().split(","):
                        name = dep.strip().split()[0].rstrip(",") if dep.strip() else ""
                        if name and not name.startswith("$") and "|" not in name:
                            deps.append(name)
            return {"apt_package": tool, "apt_depends": deps}
        r2 = subprocess.run(
            ["dpkg", "-S", f"*/bin/{tool}"],
            capture_output=True, text=True, timeout=5,
        )
        if r2.returncode == 0:
            pkg = r2.stdout.split(":")[0].strip()
            return {"apt_package": pkg, "apt_depends": []}
    except Exception:
        pass
    return {"apt_package": None, "apt_depends": []}


def resolve(repo_path: Path, result: AnalysisResult) -> None:
    """Populate `result.system_deps` from `inferred.tools + ci_tools`.

    Reads tool-deps.json cache; live `apt-cache` queries only when
    `BUILD_STACK_APT_LIVE=1` is set in the env. Cache is rewritten if
    new entries were resolved during this run.
    """
    cache = load_cache()
    all_tools = sorted(set(result.inferred.tools) | set(result.inferred.ci_tools))
    live = os.environ.get("BUILD_STACK_APT_LIVE") == "1"

    cache_updated = False
    for tool in all_tools:
        if tool not in cache:
            cache[tool] = _live_resolve(tool) if live else {"apt_package": None, "apt_depends": []}
            cache_updated = True

    if cache_updated and live:
        save_cache(cache)

    for tool in all_tools:
        entry = cache.get(tool, {})
        pkg = entry.get("apt_package")
        if pkg:
            result.system_deps[tool] = SystemDep(
                apt_package=pkg,
                apt_depends=list(entry.get("apt_depends", [])),
            )
