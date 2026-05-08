"""Unit tests for build_stack.analyzers.manifests.

Covers the 7 internal helpers + `detect()` orchestrator:
  * `_extract_purpose` (pure string)
  * `_detect_purpose` (README + repo description fallback)
  * `_detect_languages` + `_has_bun_shebang` + `_count_files`
  * `_detect_versions`
  * `_detect_libraries`
  * `_detect_browser_tools`

Tests build minimal fake-repo trees under `tmp_path` using inline
`.write_text()` calls. Each test sets up only the files relevant to
that test's invariant — so what's *missing* is just as informative as
what's *present*.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_stack.analyzers import manifests
from build_stack.analyzers.schema import AnalysisResult


# ─── _extract_purpose ─────────────────────────────────────────────────────────

def test_extract_purpose_first_substantive_paragraph_wins():
    text = "# Title\n\nSome short. Other.\n\nThis is a sufficiently long real paragraph about the project."
    out = manifests._extract_purpose(text)
    assert "sufficiently long real paragraph" in out


def test_extract_purpose_strips_markdown_link_syntax():
    text = "\n\nThis project uses [Anthropic Claude](https://anthropic.com) for embeddings tasks."
    out = manifests._extract_purpose(text)
    assert "Anthropic Claude" in out
    assert "https://" not in out


def test_extract_purpose_strips_emphasis_chars():
    text = "\n\nThis project does *very important* and `essential` work for production teams."
    out = manifests._extract_purpose(text)
    assert "*" not in out
    assert "`" not in out
    assert "very important" in out


def test_extract_purpose_strips_html_tags():
    text = "\n\nA <b>great</b> framework that <em>helps you</em> ship reliable code, fast."
    out = manifests._extract_purpose(text)
    assert "<" not in out
    assert ">" not in out


def test_extract_purpose_skips_heading_and_badge_lines():
    text = (
        "# Heading should be skipped\n"
        "![badge](url) should be skipped\n"
        "<img src=\"x\"> should be skipped\n"
        "| table | row | should be skipped\n"
        "[link-only line](url) should be skipped\n"
        "> blockquote should be skipped\n"
        "\n"
        "But this real paragraph is long enough to qualify as the purpose."
    )
    out = manifests._extract_purpose(text)
    assert "real paragraph" in out


def test_extract_purpose_empty_returns_empty_string():
    assert manifests._extract_purpose("") == ""


def test_extract_purpose_truncates_to_300_chars():
    long_para = "X" * 500 + " more text"
    out = manifests._extract_purpose("\n\n" + long_para)
    assert len(out) == 300


def test_extract_purpose_short_lines_skipped_below_20():
    """Lines shorter than 21 chars (after cleanup) are dropped from buf."""
    text = "\n\nshort\n\n" + "Y" * 50 + "\n"
    out = manifests._extract_purpose(text)
    assert "Y" * 50 in out


# ─── _detect_purpose (README + description fallback) ──────────────────────────

def test_detect_purpose_readme_wins_when_long_enough(tmp_path):
    (tmp_path / "README.md").write_text(
        "\n\nThis is a reasonably long README description well over the 80-char fallback threshold for purpose extraction."
    )
    out = manifests._detect_purpose(tmp_path, repo_description="github desc")
    assert "reasonably long" in out


def test_detect_purpose_falls_back_to_repo_description_when_readme_short(tmp_path):
    (tmp_path / "README.md").write_text("\n\nshort thing only sixty characters or so total here.")
    out = manifests._detect_purpose(tmp_path, repo_description="The github API description")
    assert out == "The github API description"


def test_detect_purpose_no_readme_uses_description(tmp_path):
    out = manifests._detect_purpose(tmp_path, repo_description="just a desc")
    assert out == "just a desc"


def test_detect_purpose_no_signals_returns_empty(tmp_path):
    assert manifests._detect_purpose(tmp_path, repo_description="") == ""


# ─── _detect_languages ────────────────────────────────────────────────────────

def test_detect_languages_package_json_implies_node(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "node" in langs


def test_detect_languages_pyproject_implies_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "python" in langs


def test_detect_languages_go_mod_implies_go(tmp_path):
    (tmp_path / "go.mod").write_text("module x")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "go" in langs


def test_detect_languages_cargo_toml_implies_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text("")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "rust" in langs


def test_detect_languages_shell_via_rglob(tmp_path):
    """Any .sh file anywhere in the tree → 'shell' added."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "deploy.sh").write_text("#!/bin/bash\n")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "shell" in langs


def test_detect_languages_python_file_scan_fallback(tmp_path):
    """No python manifest, but >2 .py files → python detected."""
    for i in range(3):
        (tmp_path / f"f{i}.py").write_text("")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "python" in langs


def test_detect_languages_python_file_scan_skips_venv(tmp_path):
    """Files in .venv don't count toward the >2 threshold."""
    (tmp_path / ".venv").mkdir()
    for i in range(5):
        (tmp_path / ".venv" / f"f{i}.py").write_text("")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "python" not in langs


def test_detect_languages_node_file_scan_skips_node_modules(tmp_path):
    (tmp_path / "node_modules").mkdir()
    for i in range(5):
        (tmp_path / "node_modules" / f"f{i}.ts").write_text("")
    langs, _ = manifests._detect_languages(tmp_path)
    assert "node" not in langs


def test_detect_languages_bun_lockfile_adds_runtime_extra(tmp_path):
    (tmp_path / "bun.lock").write_text("")
    langs, extras = manifests._detect_languages(tmp_path)
    assert "bun" in extras
    assert "node" in langs  # bun implies node


def test_detect_languages_yarn_lockfile_adds_runtime_extra(tmp_path):
    (tmp_path / "yarn.lock").write_text("")
    _, extras = manifests._detect_languages(tmp_path)
    assert "yarn" in extras


def test_detect_languages_returns_sorted(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "go.mod").write_text("module x")
    langs, _ = manifests._detect_languages(tmp_path)
    assert langs == sorted(langs)


def test_detect_languages_empty_tree(tmp_path):
    langs, extras = manifests._detect_languages(tmp_path)
    assert langs == []
    assert extras == []


# ─── _has_bun_shebang ─────────────────────────────────────────────────────────

def test_has_bun_shebang_detects_in_ts_file(tmp_path):
    (tmp_path / "x.ts").write_text("#!/usr/bin/env bun\nconsole.log('x');\n")
    assert manifests._has_bun_shebang(tmp_path) is True


def test_has_bun_shebang_skips_git_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.ts").write_text("#!/usr/bin/env bun\n")
    assert manifests._has_bun_shebang(tmp_path) is False


def test_has_bun_shebang_no_match(tmp_path):
    (tmp_path / "x.ts").write_text("console.log('x');\n")
    assert manifests._has_bun_shebang(tmp_path) is False


# ─── _count_files ─────────────────────────────────────────────────────────────

def test_count_files_single_pattern_string(tmp_path):
    for i in range(3):
        (tmp_path / f"f{i}.py").write_text("")
    assert manifests._count_files(tmp_path, "*.py") == 3


def test_count_files_tuple_of_patterns_union(tmp_path):
    (tmp_path / "a.ts").write_text("")
    (tmp_path / "b.js").write_text("")
    assert manifests._count_files(tmp_path, ("*.ts", "*.js")) == 2


def test_count_files_excludes_filter(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("")
    (tmp_path / "kept.js").write_text("")
    assert manifests._count_files(tmp_path, "*.js", excludes=("node_modules",)) == 1


def test_count_files_skips_dot_git(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.py").write_text("")
    assert manifests._count_files(tmp_path, "*.py") == 0


# ─── _detect_versions ─────────────────────────────────────────────────────────

def test_detect_versions_node_from_package_json_engines(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"engines": {"node": "20"}}))
    out = manifests._detect_versions(tmp_path)
    assert out.get("node") == "20"


def test_detect_versions_node_from_nvmrc_fallback(tmp_path):
    """No package.json engines.node → .nvmrc wins. 'v' prefix stripped."""
    (tmp_path / ".nvmrc").write_text("v20.10.0\n")
    out = manifests._detect_versions(tmp_path)
    assert out.get("node") == "20.10.0"


def test_detect_versions_engines_wins_over_nvmrc(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"engines": {"node": "22"}}))
    (tmp_path / ".nvmrc").write_text("18\n")
    out = manifests._detect_versions(tmp_path)
    assert out.get("node") == "22"


def test_detect_versions_node_version_file_fallback(tmp_path):
    (tmp_path / ".node-version").write_text("18.17.0\n")
    out = manifests._detect_versions(tmp_path)
    assert out.get("node") == "18.17.0"


def test_detect_versions_go_from_go_mod(tmp_path):
    (tmp_path / "go.mod").write_text("module github.com/x/y\n\ngo 1.21\n\nrequire ...\n")
    out = manifests._detect_versions(tmp_path)
    assert out.get("go") == "1.21"


def test_detect_versions_empty_tree_returns_empty(tmp_path):
    assert manifests._detect_versions(tmp_path) == {}


def test_detect_versions_malformed_package_json_silently_skipped(tmp_path):
    """Crash-tolerance: a broken manifest must not break the rest of the run."""
    (tmp_path / "package.json").write_text("{not valid")
    (tmp_path / ".nvmrc").write_text("18\n")
    out = manifests._detect_versions(tmp_path)
    assert out.get("node") == "18"


# ─── _detect_libraries ────────────────────────────────────────────────────────

def test_detect_libraries_node_combines_deps_and_devdeps(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies":    {"react": "^18", "lodash": "^4"},
        "devDependencies": {"jest":  "^29"},
    }))
    libs, _ = manifests._detect_libraries(tmp_path)
    assert set(libs["node"]) == {"react", "lodash", "jest"}


def test_detect_libraries_node_capped_at_60(tmp_path):
    deps = {f"pkg-{i}": "^1" for i in range(80)}
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": deps}))
    libs, _ = manifests._detect_libraries(tmp_path)
    assert len(libs["node"]) == 60


def test_detect_libraries_python_strips_version_specs(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "requests>=2.31\n"
        "pytest==7.4.3\n"
        "numpy<2.0\n"
        "# comment line\n"
        "-e .\n"
    )
    libs, _ = manifests._detect_libraries(tmp_path)
    assert set(libs["python"]) == {"requests", "pytest", "numpy"}


def test_detect_libraries_python_strips_extras_marker(tmp_path):
    """`pkg[extra]; python_version > "3.10"` → just `pkg`."""
    (tmp_path / "requirements.txt").write_text("requests[security];python_version>'3.9'\n")
    libs, _ = manifests._detect_libraries(tmp_path)
    assert libs["python"] == ["requests"]


def test_detect_libraries_go_indented_lines_only(tmp_path):
    """`require (` block: indented lines with `/` are deps. The `module`
    line and the `require (` line itself must NOT be picked up."""
    (tmp_path / "go.mod").write_text(
        "module github.com/x/y\n"
        "\n"
        "go 1.21\n"
        "\n"
        "require (\n"
        "    github.com/spf13/cobra v1.0\n"
        "    github.com/stretchr/testify v1.0\n"
        ")\n"
    )
    libs, _ = manifests._detect_libraries(tmp_path)
    assert "github.com/spf13/cobra" in libs["go"]
    assert "github.com/x/y" not in libs["go"]


def test_detect_libraries_rust_skips_section_keys(tmp_path):
    """`[workspace]`, `[package]`, `[lib]` etc. shouldn't appear as crate names."""
    (tmp_path / "Cargo.toml").write_text(
        '[package]\n'
        'name = "myapp"\n'
        'version = "0.1.0"\n'
        '[dependencies]\n'
        'serde = "1.0"\n'
        'tokio = { version = "1", features = ["full"] }\n'
    )
    libs, _ = manifests._detect_libraries(tmp_path)
    assert "serde" in libs["rust"]
    assert "tokio" in libs["rust"]
    for keyword in ("package", "workspace", "dependencies", "lib", "bin"):
        assert keyword not in libs["rust"]


def test_detect_libraries_rust_version_extracted(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[package]\n'
        'rust-version = "1.75"\n'
    )
    _, rust_ver = manifests._detect_libraries(tmp_path)
    assert rust_ver == "1.75"


def test_detect_libraries_rust_capped_at_80(tmp_path):
    deps_block = "[dependencies]\n" + "\n".join(f"crate{i} = \"1\"" for i in range(120))
    (tmp_path / "Cargo.toml").write_text(deps_block)
    libs, _ = manifests._detect_libraries(tmp_path)
    assert len(libs["rust"]) == 80


def test_detect_libraries_rust_aggregates_workspace_members(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[workspace]\nmembers = [\"a\"]\n")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "Cargo.toml").write_text("[dependencies]\nfoo = \"1\"\n")
    libs, _ = manifests._detect_libraries(tmp_path)
    assert "foo" in libs["rust"]


def test_detect_libraries_empty_tree(tmp_path):
    libs, rust_ver = manifests._detect_libraries(tmp_path)
    assert libs == {"node": [], "python": [], "go": [], "rust": []}
    assert rust_ver == ""


def test_detect_libraries_malformed_manifests_dont_crash(tmp_path):
    (tmp_path / "package.json").write_text("not json")
    (tmp_path / "requirements.txt").write_text("ok-pkg\n")
    libs, _ = manifests._detect_libraries(tmp_path)
    # broken package.json → empty node, but python still works
    assert libs["node"] == []
    assert libs["python"] == ["ok-pkg"]


# ─── _detect_browser_tools ────────────────────────────────────────────────────

def test_detect_browser_tools_playwright_in_package_json(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "devDependencies": {"playwright": "^1.40"},
    }))
    assert "playwright" in manifests._detect_browser_tools(tmp_path)


def test_detect_browser_tools_substring_match_lowercase(tmp_path):
    """Lowercase substring match — 'PLAYWRIGHT' in any case is detected."""
    (tmp_path / "package.json").write_text('{"x": "PLAYWRIGHT"}')
    assert "playwright" in manifests._detect_browser_tools(tmp_path)


def test_detect_browser_tools_multiple_detected(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"playwright": "1", "puppeteer": "1"},
    }))
    out = manifests._detect_browser_tools(tmp_path)
    assert "playwright" in out
    assert "puppeteer" in out


def test_detect_browser_tools_empty_tree(tmp_path):
    assert manifests._detect_browser_tools(tmp_path) == []


# ─── detect() orchestrator ────────────────────────────────────────────────────

def test_detect_populates_all_manifest_fields(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "engines": {"node": "20"},
        "dependencies": {"react": "^18", "playwright": "^1.40"},
    }))
    (tmp_path / "go.mod").write_text("module x\n\ngo 1.21\n")
    result = AnalysisResult()
    manifests.detect(tmp_path, result, repo_description="A test project")
    assert "node" in result.languages
    assert "go" in result.languages
    assert result.runtime_versions["node"] == "20"
    assert result.runtime_versions["go"] == "1.21"
    assert "react" in result.libraries.node
    assert "playwright" in result.browser_tools
    assert result.purpose == "A test project"


def test_detect_rust_version_lands_in_runtime_versions(tmp_path):
    """rust-version is extracted by _detect_libraries but routed to
    runtime_versions, not the libraries list — pin this routing."""
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nrust-version = "1.75"\n[dependencies]\nfoo = "1"\n'
    )
    result = AnalysisResult()
    manifests.detect(tmp_path, result)
    assert result.runtime_versions.get("rust") == "1.75"
    assert "foo" in result.libraries.rust
