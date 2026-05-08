"""Unit tests for build_stack.analyzers.report — markdown render.

Pure function module: input is the analysis-result dict, output is a
markdown string. Tests use small inline dicts to pin section formatting,
empty-state handling, and the conditional rendering rules
(e.g. System Dependencies section only emitted when sys_deps non-empty).

Doesn't snapshot full reports — too brittle. Instead each test asserts
on substrings that pin one rendering rule. Adjacent rules are isolated
into their own tests so a future formatting tweak only fails one assertion.
"""

from __future__ import annotations

import pytest

from build_stack.analyzers import report


# ─── _fmt ─────────────────────────────────────────────────────────────────────

def test_fmt_empty_returns_default_message():
    assert report._fmt([]) == "none detected"


def test_fmt_empty_with_custom_message():
    assert report._fmt([], empty="(none)") == "(none)"


def test_fmt_joins_with_comma_space():
    assert report._fmt(["a", "b", "c"]) == "a, b, c"


def test_fmt_stringifies_non_string_items():
    assert report._fmt([1, 2, 3]) == "1, 2, 3"


# ─── _fmt_creds ───────────────────────────────────────────────────────────────

def test_fmt_creds_all_empty_returns_none_detected():
    assert report._fmt_creds({}) == "  none detected"


def test_fmt_creds_api_keys_section():
    out = report._fmt_creds({"api_keys": ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]})
    assert "API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY" in out


def test_fmt_creds_tokens_section():
    out = report._fmt_creds({"tokens": ["GITHUB_TOKEN"]})
    assert "Tokens: GITHUB_TOKEN" in out


def test_fmt_creds_ssh_flag():
    """`ssh: True` produces the literal "SSH key required" line."""
    out = report._fmt_creds({"ssh": True})
    assert "SSH key required" in out


def test_fmt_creds_other_section():
    out = report._fmt_creds({"other": ["DATABASE_URL"]})
    assert "Other: DATABASE_URL" in out


def test_fmt_creds_combined_sections_each_on_own_line():
    """Multiple credential types render as bulleted markdown — newline-separated."""
    out = report._fmt_creds({
        "api_keys": ["X_KEY"],
        "tokens": ["Y_TOKEN"],
        "ssh": True,
    })
    lines = out.splitlines()
    # Each bullet starts with two spaces + dash
    assert all(line.lstrip().startswith("- ") for line in lines)
    assert len(lines) == 3


# ─── _fmt_container ───────────────────────────────────────────────────────────

def test_fmt_container_empty_returns_standard_message():
    assert report._fmt_container({}) == "  standard (no special requirements)"


def test_fmt_container_capabilities_listed():
    out = report._fmt_container({"capabilities": ["NET_ADMIN", "NET_RAW"]})
    assert "Docker caps: NET_ADMIN, NET_RAW" in out


def test_fmt_container_remote_user_section():
    out = report._fmt_container({"remote_user": "claude"})
    assert "User: claude" in out


def test_fmt_container_post_start_wrapped_in_backticks():
    """Markdown rendering: shell commands rendered as code spans."""
    out = report._fmt_container({"post_start": "init.sh && fw.sh"})
    assert "`init.sh && fw.sh`" in out


def test_fmt_container_volume_dict_form():
    out = report._fmt_container({"volumes": [{"name": "v", "target": "/t"}]})
    assert "Volume: `v` → `/t`" in out


def test_fmt_container_volume_string_form():
    """Volume entries can be raw strings; target stays empty."""
    out = report._fmt_container({"volumes": ["legacy-string-mount"]})
    assert "Volume: `legacy-string-mount`" in out


def test_fmt_container_env_keys_listed():
    """env values are sensitive; rendering only emits the KEY (no value).
    This is intentional — protects against accidental secret display."""
    out = report._fmt_container({"env": {"NODE_ENV": "production", "API_KEY": "secret123"}})
    assert "ENV: `NODE_ENV`" in out
    assert "ENV: `API_KEY`" in out
    assert "secret123" not in out


# ─── _fmt_chain ───────────────────────────────────────────────────────────────

def test_fmt_chain_empty_uses_label():
    out = report._fmt_chain([], "post_start_chain")
    assert "post_start_chain: none" in out


def test_fmt_chain_in_repo_step_marked_check():
    """In-repo scripts get ✓ marker — visually distinguishable."""
    out = report._fmt_chain([{"in_repo": True, "script": "init.sh"}], "post_start_chain")
    assert "✓ in-repo" in out
    assert "init.sh" in out


def test_fmt_chain_external_step_marked_circle():
    """Baked/external scripts (not in repo) get ○ marker."""
    out = report._fmt_chain([
        {"in_repo": False, "script": "/usr/local/bin/init-firewall.sh"},
    ], "post_start_chain")
    assert "○ baked/external" in out


def test_fmt_chain_sudo_flag_displayed():
    out = report._fmt_chain([
        {"in_repo": False, "script": "fw.sh", "sudo": True},
    ], "post_start_chain")
    assert "(sudo)" in out


def test_fmt_chain_args_displayed_in_backticks():
    out = report._fmt_chain([
        {"in_repo": True, "script": "init.sh", "args": "--strict"},
    ], "post_start_chain")
    assert "`--strict`" in out


def test_fmt_chain_no_script_fallback():
    """Step missing a script (raw command unparseable) → "(no script)" placeholder."""
    out = report._fmt_chain([{"raw": "weird"}], "post_create_chain")
    assert "(no script)" in out


# ─── render ───────────────────────────────────────────────────────────────────

def test_render_returns_string_with_project_header():
    md = report.render({"project": "myrepo", "repo": "owner/myrepo"})
    assert "# Dependency Analysis: myrepo" in md
    assert "owner/myrepo" in md


def test_render_purpose_default_when_empty():
    """Empty purpose → "see README" placeholder, never empty markdown line."""
    md = report.render({"project": "x"})
    assert "see README" in md


def test_render_purpose_used_when_populated():
    md = report.render({"project": "x", "purpose": "An interesting tool"})
    assert "An interesting tool" in md


def test_render_runtime_versions_formatted_as_lang_ver():
    md = report.render({
        "project": "x",
        "runtime_versions": {"node": "20", "python": "3.12"},
    })
    assert "node 20" in md
    assert "python 3.12" in md


def test_render_libraries_capped_at_12_with_more_indicator():
    """Per-language preview shows first 12 + "(N more)" for the tail."""
    md = report.render({
        "project": "x",
        "libraries": {"node": [f"pkg-{i}" for i in range(20)]},
    })
    assert "pkg-0" in md
    assert "(8 more)" in md


def test_render_libraries_no_more_indicator_when_under_cap():
    md = report.render({
        "project": "x",
        "libraries": {"node": ["a", "b", "c"]},
    })
    assert "more)" not in md


def test_render_system_deps_section_only_when_present():
    """`## System Dependencies` heading is conditional — absent when sys_deps={}."""
    md_with = report.render({"project": "x", "system_deps": {
        "jq": {"apt_package": "jq", "apt_depends": ["libjq1"]},
    }})
    assert "## System Dependencies" in md_with
    assert "`jq` → `jq`" in md_with

    md_without = report.render({"project": "x"})
    assert "## System Dependencies" not in md_without


def test_render_github_api_yes_no():
    md_yes = report.render({"project": "x", "github_api_usage": True})
    md_no = report.render({"project": "x", "github_api_usage": False})
    assert "## GitHub API Usage\nYes" in md_yes
    assert "## GitHub API Usage\nNo" in md_no


def test_render_mcp_servers_dict_form_extracts_names():
    """mcp_servers can be list of dicts with `name` key — render strips to names."""
    md = report.render({
        "project": "x",
        "mcp_servers": [{"name": "github", "url": "x"}, {"name": "filesystem"}],
    })
    assert "github, filesystem" in md or ("github" in md and "filesystem" in md)


def test_render_inferred_section_handles_all_buckets():
    """The Inferred section has 7 sub-buckets — each only rendered when populated."""
    md = report.render({
        "project": "x",
        "inferred": {
            "tools_new": ["jq"],
            "tools_confirmed": ["curl"],
            "ci_tools": ["gh"],
            "py_imports_new": ["requests"],
            "py_imports_confirmed": ["pytest"],
            "ts_imports_new": ["zod"],
            "ts_imports_confirmed": ["typescript"],
        },
    })
    assert "Tools/binaries (not in Dockerfile)" in md
    assert "CI toolchain (GitHub Actions)" in md
    assert "Python imports (not in manifest)" in md


def test_render_init_scripts_section_appears_when_listed():
    md = report.render({
        "project": "x",
        "container": {"init_scripts": ["scripts/init.sh"]},
    })
    assert "init_scripts (in-repo)" in md
    assert "scripts/init.sh" in md


def test_render_empty_repo_gracefully_renders():
    """Bare-minimum dict — verify no exceptions and key headers all present."""
    md = report.render({"project": "x"})
    for header in (
        "## Languages & Runtimes",
        "## System Packages",
        "## Libraries",
        "## Ports",
        "## External Services",
        "## Environment Variables",
        "## Container Requirements",
        "## Credentials Required",
        "## MCP Servers",
        "## Claude Plugins",
        "## Browser / Test Tools",
        "## GitHub API Usage",
        "## Inferred from Source",
    ):
        assert header in md, f"missing header: {header}"
