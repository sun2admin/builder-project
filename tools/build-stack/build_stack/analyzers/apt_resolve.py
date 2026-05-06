"""apt-cache resolver with persistent tool-deps.json cache.

Resolves `inferred.tools` + `inferred.ci_tools` → apt package names via
`apt-cache search`/`apt-cache show`. Result cached in
`tools/build-stack/build_stack/data/tool-deps.json` (persistent across
runs, committed to git).

Tools that don't resolve to any apt package are cached with
`apt_package: null` to avoid re-querying.

Phase 2: read existing cache, populate `system_deps`. Live `apt-cache`
queries gated behind `BUILD_STACK_APT_LIVE=1` env (off by default during
parity test per sub-plan OQ5 = (a) — test reads cache only, no live queries).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schema import AnalysisResult, SystemDep


def _data_dir() -> Path:
    """Resolve `tools/build-stack/build_stack/data/` regardless of cwd."""
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


def resolve(repo_path: Path, result: AnalysisResult) -> None:
    """Resolve inferred tools to apt packages; populate result.system_deps.

    Reads cache; live apt-cache queries only when BUILD_STACK_APT_LIVE=1.

    Phase 2 stub — populates from cache only; resolution loop pending.
    """
    raise NotImplementedError("apt_resolve.resolve() pending — Phase 2 port work")
