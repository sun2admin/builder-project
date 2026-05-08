"""Unit tests for build_stack.schema_validation.

Pins the three exit codes the CLI relies on (0=ok, 2=file/JSON error,
3=schema error). The F1 fix (commit 664f8f1) made `__main__.py`
propagate these codes — tests here protect against silent regressions
in the underlying validator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_stack import schema_validation


# ─── minimal valid build.json ────────────────────────────────────────────────

def _valid_build() -> dict:
    """Construct the smallest dict that schema validates against."""
    return {
        "schema_version": 3,
        "build_category": "test",
        "build_project": "myapp",
        "project_repo": "owner/repo",
        "ai_clis": ["claude"],
    }


# ─── exit codes ───────────────────────────────────────────────────────────────

def test_validate_returns_0_for_valid_build_json(tmp_path):
    p = tmp_path / "build.json"
    p.write_text(json.dumps(_valid_build()))
    assert schema_validation.validate_build_json(p) == 0


def test_validate_returns_2_for_missing_file(tmp_path):
    """Exit code 2 = file not found (POSIX 'misuse of shell builtin' mapping)."""
    assert schema_validation.validate_build_json(tmp_path / "nope.json") == 2


def test_validate_returns_2_for_malformed_json(tmp_path):
    p = tmp_path / "build.json"
    p.write_text("{not valid json")
    assert schema_validation.validate_build_json(p) == 2


def test_validate_returns_3_for_schema_violation(tmp_path):
    """Exit code 3 = schema validation failure (distinct from JSON parse error)."""
    p = tmp_path / "build.json"
    p.write_text(json.dumps({"schema_version": 999}))  # wrong version + missing required
    assert schema_validation.validate_build_json(p) == 3


def test_validate_returns_3_for_extra_property(tmp_path):
    """`additionalProperties: false` in the schema → unknown keys reject."""
    body = _valid_build()
    body["totally_unknown_key"] = "x"
    p = tmp_path / "build.json"
    p.write_text(json.dumps(body))
    assert schema_validation.validate_build_json(p) == 3


def test_validate_returns_3_for_bad_repo_format(tmp_path):
    """`project_repo` must match `owner/repo` or be null — bare string fails."""
    body = _valid_build()
    body["project_repo"] = "not-a-slash-format"
    p = tmp_path / "build.json"
    p.write_text(json.dumps(body))
    assert schema_validation.validate_build_json(p) == 3


def test_validate_accepts_null_project_repo_for_sandbox(tmp_path):
    """`project_repo: null` is the sandbox marker (no associated git repo)."""
    body = _valid_build()
    body["project_repo"] = None
    p = tmp_path / "build.json"
    p.write_text(json.dumps(body))
    assert schema_validation.validate_build_json(p) == 0


def test_validate_returns_3_for_missing_required_field(tmp_path):
    body = _valid_build()
    del body["ai_clis"]
    p = tmp_path / "build.json"
    p.write_text(json.dumps(body))
    assert schema_validation.validate_build_json(p) == 3


# ─── error messages ──────────────────────────────────────────────────────────

def test_validate_emits_path_in_not_found_message(tmp_path, capsys):
    """Stderr message must include the path so users find which file is missing."""
    missing = tmp_path / "nowhere.json"
    schema_validation.validate_build_json(missing)
    err = capsys.readouterr().err
    assert str(missing) in err
    assert "not found" in err


def test_validate_emits_path_in_invalid_json_message(tmp_path, capsys):
    p = tmp_path / "broken.json"
    p.write_text("garbage")
    schema_validation.validate_build_json(p)
    err = capsys.readouterr().err
    assert str(p) in err
    assert "not valid JSON" in err


def test_validate_emits_schema_message_on_violation(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": 1}))
    schema_validation.validate_build_json(p)
    err = capsys.readouterr().err
    assert "fails schema validation" in err


def test_validate_emits_ok_message_on_success(tmp_path, capsys):
    p = tmp_path / "good.json"
    p.write_text(json.dumps(_valid_build()))
    schema_validation.validate_build_json(p)
    err = capsys.readouterr().err
    assert "ok" in err


# ─── schema loader ───────────────────────────────────────────────────────────

def test_load_schema_returns_dict_with_required_keys():
    """The bundled schema must include the documented required[] list —
    if a future schema bump drops a required field, this test flags it."""
    s = schema_validation._load_schema()
    assert isinstance(s, dict)
    assert "schema_version" in s.get("required", [])
    assert "build_category" in s.get("required", [])
    assert "build_project" in s.get("required", [])
    assert "ai_clis" in s.get("required", [])


def test_load_schema_pins_schema_version_const():
    """Schema is on v3 (per F2 fix). If we bump to v4, this fails and the
    dev updates the const in sync with the pinned tests above."""
    s = schema_validation._load_schema()
    assert s["properties"]["schema_version"].get("const") == 3
