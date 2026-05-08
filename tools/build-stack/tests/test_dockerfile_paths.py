"""Unit tests for devcontainer.json path discovery (F3 fix).

Background: detector previously hardcoded ``.devcontainer/devcontainer.json``
and missed project-convention layouts like builder-project's
``layer4-devcontainer/``. These tests pin the priority order documented
on ``_find_devcontainer_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

from build_stack.analyzers.dockerfile import _find_devcontainer_path


def _write_dc(p: Path, image: str = "ghcr.io/test/base") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"image": image}))


def test_canonical_path(tmp_path):
    target = tmp_path / ".devcontainer" / "devcontainer.json"
    _write_dc(target)
    assert _find_devcontainer_path(tmp_path) == target


def test_root_alternative(tmp_path):
    target = tmp_path / ".devcontainer.json"
    _write_dc(target)
    assert _find_devcontainer_path(tmp_path) == target


def test_named_config(tmp_path):
    target = tmp_path / ".devcontainer" / "node" / "devcontainer.json"
    _write_dc(target)
    assert _find_devcontainer_path(tmp_path) == target


def test_project_convention_layer4(tmp_path):
    """builder-project layout: layer4-devcontainer/devcontainer.json."""
    target = tmp_path / "layer4-devcontainer" / "devcontainer.json"
    _write_dc(target)
    assert _find_devcontainer_path(tmp_path) == target


def test_priority_canonical_wins_over_root_alt(tmp_path):
    canonical = tmp_path / ".devcontainer" / "devcontainer.json"
    root_alt = tmp_path / ".devcontainer.json"
    _write_dc(canonical, "canonical")
    _write_dc(root_alt, "root-alt")
    assert _find_devcontainer_path(tmp_path) == canonical


def test_priority_canonical_wins_over_project_convention(tmp_path):
    canonical = tmp_path / ".devcontainer" / "devcontainer.json"
    project = tmp_path / "layer4-devcontainer" / "devcontainer.json"
    _write_dc(canonical, "canonical")
    _write_dc(project, "project")
    assert _find_devcontainer_path(tmp_path) == canonical


def test_priority_root_alt_wins_over_named(tmp_path):
    root_alt = tmp_path / ".devcontainer.json"
    named = tmp_path / ".devcontainer" / "node" / "devcontainer.json"
    _write_dc(root_alt, "root-alt")
    _write_dc(named, "named")
    assert _find_devcontainer_path(tmp_path) == root_alt


def test_named_config_alphabetical_first(tmp_path):
    """When multiple named configs exist, alpha-first wins (deterministic)."""
    _write_dc(tmp_path / ".devcontainer" / "zulu" / "devcontainer.json", "zulu")
    target = tmp_path / ".devcontainer" / "alpha" / "devcontainer.json"
    _write_dc(target, "alpha")
    assert _find_devcontainer_path(tmp_path) == target


def test_project_convention_alphabetical_first(tmp_path):
    _write_dc(tmp_path / "z-devcontainer" / "devcontainer.json", "z")
    target = tmp_path / "a-devcontainer" / "devcontainer.json"
    _write_dc(target, "a")
    assert _find_devcontainer_path(tmp_path) == target


def test_no_match(tmp_path):
    assert _find_devcontainer_path(tmp_path) is None


def test_ignores_non_matching_dirname(tmp_path):
    """``somedir/devcontainer.json`` (no -devcontainer suffix) must NOT match."""
    _write_dc(tmp_path / "somedir" / "devcontainer.json")
    assert _find_devcontainer_path(tmp_path) is None
