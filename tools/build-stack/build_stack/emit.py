"""Phase 6 — devcontainer.json + workspace.env writers.

Takes the composed stack decisions and emits final artifacts under
builds/<build_name>/.
"""

from __future__ import annotations

from pathlib import Path


def emit_devcontainer_json(build_dir: Path, composition: dict) -> Path:
    """Write builds/<name>/devcontainer.json from composition decisions."""
    raise NotImplementedError("emit.emit_devcontainer_json is a stub.")


def emit_workspace_env(build_dir: Path, composition: dict) -> Path:
    """Write builds/<name>/workspace.env (backward-compat with old workflow)."""
    raise NotImplementedError("emit.emit_workspace_env is a stub.")
