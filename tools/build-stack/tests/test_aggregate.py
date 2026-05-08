"""Unit tests for build_stack.aggregate — Phase 4 multi-repo merge.

Pure-function helpers only; the orchestrator ``aggregate()`` and the two
``_load_*`` helpers touch the filesystem and are deferred to integration
coverage. These tests pin the merge contracts in
``.claude/plans/build-workflow-stack-composition.md`` §1:

  * set-union semantics for list fields
  * project-vs-non-project asymmetry in container merge
  * version compatibility (major-cross-pin raises)
  * MCP server / system_deps name-conflict raises
  * inferred confirmed/new partition recomputed from libraries+system_deps
"""

from __future__ import annotations

import io
import sys

import pytest

from build_stack.aggregate import (
    _empty_aggregate,
    _merge_container,
    _merge_credentials,
    _merge_external_services,
    _merge_inferred,
    _merge_libraries,
    _merge_mcp_servers,
    _merge_ports,
    _merge_runtime_versions,
    _merge_set_field,
    _merge_system_deps,
    _parse_version_key,
    _recompute_inferred_dedup,
    _versions_compatible,
    _volume_target,
)


# ─── version parsing ──────────────────────────────────────────────────────────

def test_parse_version_key_pinned_returns_tuple():
    assert _parse_version_key("3.11.5") == (3, 11, 5)


def test_parse_version_key_with_prefix():
    """Leading 'v' / 'python-' style prefixes — first numeric run wins."""
    assert _parse_version_key("v20.10") == (20, 10)


def test_parse_version_key_latest_returns_none():
    assert _parse_version_key("latest") is None
    assert _parse_version_key("*") is None
    assert _parse_version_key("any") is None


def test_parse_version_key_empty_returns_none():
    assert _parse_version_key("") is None
    assert _parse_version_key(None) is None


def test_versions_compatible_same_major():
    assert _versions_compatible("3.11", "3.12") is True


def test_versions_compatible_different_major():
    assert _versions_compatible("2.7", "3.11") is False


def test_versions_compatible_unpinned_is_compatible_with_anything():
    """Either side unpinned → caller intends "no constraint"; treat as ok."""
    assert _versions_compatible("latest", "3.11") is True
    assert _versions_compatible("3.11", "latest") is True
    assert _versions_compatible("latest", "latest") is True


# ─── _merge_set_field ─────────────────────────────────────────────────────────

def test_merge_set_field_unions_and_sorts():
    out = {"languages": ["python"]}
    _merge_set_field(out, {"languages": ["go", "python", "rust"]}, "languages")
    assert out["languages"] == ["go", "python", "rust"]


def test_merge_set_field_handles_missing_in_either_side():
    out = {}
    _merge_set_field(out, {"languages": ["python"]}, "languages")
    assert out["languages"] == ["python"]

    out2 = {"languages": ["python"]}
    _merge_set_field(out2, {}, "languages")
    assert out2["languages"] == ["python"]


# ─── _merge_libraries ─────────────────────────────────────────────────────────

def test_merge_libraries_per_language_union():
    out = _empty_aggregate("p")
    out["libraries"]["python"] = ["requests"]
    _merge_libraries(out, {"libraries": {"python": ["pytest"], "node": ["react"]}})
    assert out["libraries"]["python"] == ["pytest", "requests"]
    assert out["libraries"]["node"] == ["react"]


def test_merge_libraries_unknown_language_ignored():
    """Only the four known langs (node/python/go/rust) get merged."""
    out = _empty_aggregate("p")
    _merge_libraries(out, {"libraries": {"haskell": ["base"], "python": ["x"]}})
    assert "haskell" not in out["libraries"]
    assert out["libraries"]["python"] == ["x"]


# ─── _merge_credentials ───────────────────────────────────────────────────────

def test_merge_credentials_api_keys_union_sorted():
    out = _empty_aggregate("p")
    out["credentials_required"]["api_keys"] = ["OPENAI_API_KEY"]
    _merge_credentials(out, {
        "credentials_required": {"api_keys": ["ANTHROPIC_API_KEY"]},
    })
    assert out["credentials_required"]["api_keys"] == [
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    ]


def test_merge_credentials_ssh_is_or_not_overwrite():
    out = _empty_aggregate("p")
    out["credentials_required"]["ssh"] = True
    _merge_credentials(out, {"credentials_required": {"ssh": False}})
    assert out["credentials_required"]["ssh"] is True


def test_merge_credentials_ssh_promoted_when_either_true():
    out = _empty_aggregate("p")
    assert out["credentials_required"]["ssh"] is False
    _merge_credentials(out, {"credentials_required": {"ssh": True}})
    assert out["credentials_required"]["ssh"] is True


# ─── _merge_mcp_servers ───────────────────────────────────────────────────────

def test_merge_mcp_servers_str_form_treated_as_name_only():
    out = _empty_aggregate("p")
    _merge_mcp_servers(out, {"mcp_servers": ["github"]}, "src")
    assert out["mcp_servers"] == ["github"]


def test_merge_mcp_servers_dedup_by_name_when_identical():
    out = _empty_aggregate("p")
    _merge_mcp_servers(out, {"mcp_servers": ["github"]}, "a")
    _merge_mcp_servers(out, {"mcp_servers": ["github"]}, "b")
    assert out["mcp_servers"] == ["github"]


def test_merge_mcp_servers_conflict_str_vs_dict_same_name_raises():
    """Different shapes for same name = real config divergence → raise."""
    out = _empty_aggregate("p")
    _merge_mcp_servers(out, {"mcp_servers": ["github"]}, "a")
    with pytest.raises(ValueError, match="MCP server name conflict"):
        _merge_mcp_servers(
            out,
            {"mcp_servers": [{"name": "github", "command": "different"}]},
            "b",
        )


def test_merge_mcp_servers_unnamed_entry_skipped():
    out = _empty_aggregate("p")
    _merge_mcp_servers(out, {"mcp_servers": [{"command": "no-name"}]}, "src")
    assert out["mcp_servers"] == []


# ─── _merge_runtime_versions ──────────────────────────────────────────────────

def test_merge_runtime_versions_first_value_wins_when_no_conflict():
    out = _empty_aggregate("p")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.11"}}, "a")
    assert out["runtime_versions"] == {"python": "3.11"}


def test_merge_runtime_versions_pinned_upgrades_unpinned():
    """Project says 'latest' → plugin specifies '3.12' should upgrade to 3.12."""
    out = _empty_aggregate("p")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "latest"}}, "a")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.12"}}, "b")
    assert out["runtime_versions"]["python"] == "3.12"


def test_merge_runtime_versions_unpinned_does_not_downgrade_pinned():
    out = _empty_aggregate("p")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.11"}}, "a")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "latest"}}, "b")
    assert out["runtime_versions"]["python"] == "3.11"


def test_merge_runtime_versions_newer_pin_wins_within_major():
    out = _empty_aggregate("p")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.11"}}, "a")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.12"}}, "b")
    assert out["runtime_versions"]["python"] == "3.12"


def test_merge_runtime_versions_older_pin_does_not_downgrade():
    out = _empty_aggregate("p")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.12"}}, "a")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "3.11"}}, "b")
    assert out["runtime_versions"]["python"] == "3.12"


def test_merge_runtime_versions_major_cross_pin_raises():
    out = _empty_aggregate("p")
    _merge_runtime_versions(out, {"runtime_versions": {"python": "2.7"}}, "a")
    with pytest.raises(ValueError, match="cross-pin conflict"):
        _merge_runtime_versions(
            out, {"runtime_versions": {"python": "3.11"}}, "src-b",
        )


# ─── _merge_ports ─────────────────────────────────────────────────────────────

def test_merge_ports_inbound_union_and_dedup():
    out = _empty_aggregate("p")
    out["ports"]["inbound"] = [3000, 8080]
    _merge_ports(out, {"ports": {"inbound": [8080, 9000]}})
    assert out["ports"]["inbound"] == [3000, 8080, 9000]


# ─── _merge_external_services ─────────────────────────────────────────────────

def test_merge_external_services_first_source_preserved():
    out = _empty_aggregate("p")
    _merge_external_services(out, {
        "external_services": {"domains": ["api.x.com"], "source": "manifest"},
    })
    assert out["external_services"]["source"] == "manifest"


def test_merge_external_services_two_distinct_sources_marked_multi():
    out = _empty_aggregate("p")
    _merge_external_services(out, {
        "external_services": {"domains": ["a"], "source": "manifest"},
    })
    _merge_external_services(out, {
        "external_services": {"domains": ["b"], "source": "source_scan"},
    })
    assert out["external_services"]["source"] == "multi"
    assert out["external_services"]["domains"] == ["a", "b"]


def test_merge_external_services_same_source_repeated_keeps_label():
    out = _empty_aggregate("p")
    _merge_external_services(out, {
        "external_services": {"domains": ["a"], "source": "manifest"},
    })
    _merge_external_services(out, {
        "external_services": {"domains": ["b"], "source": "manifest"},
    })
    assert out["external_services"]["source"] == "manifest"


# ─── _merge_inferred ──────────────────────────────────────────────────────────

def test_merge_inferred_lists_unioned_and_sorted():
    out = _empty_aggregate("p")
    out["inferred"]["tools"] = ["docker"]
    _merge_inferred(out, {"inferred": {"tools": ["git", "make"], "py_imports": ["json"]}})
    assert out["inferred"]["tools"] == ["docker", "git", "make"]
    assert out["inferred"]["py_imports"] == ["json"]


# ─── _merge_system_deps ───────────────────────────────────────────────────────

def test_merge_system_deps_first_entry_recorded():
    out = _empty_aggregate("p")
    _merge_system_deps(out, {
        "system_deps": {"git": {"apt_package": "git", "apt_depends": ["libc6"]}},
    }, "a")
    assert out["system_deps"]["git"]["apt_package"] == "git"
    assert out["system_deps"]["git"]["apt_depends"] == ["libc6"]


def test_merge_system_deps_apt_package_conflict_raises():
    """Different apt_package for same logical tool = composition is broken."""
    out = _empty_aggregate("p")
    _merge_system_deps(out, {"system_deps": {"git": {"apt_package": "git"}}}, "a")
    with pytest.raises(ValueError, match="system_deps apt_package conflict"):
        _merge_system_deps(
            out,
            {"system_deps": {"git": {"apt_package": "git-core"}}},
            "src-b",
        )


def test_merge_system_deps_depends_unioned_when_package_matches():
    out = _empty_aggregate("p")
    _merge_system_deps(out, {
        "system_deps": {"git": {"apt_package": "git", "apt_depends": ["libc6"]}},
    }, "a")
    _merge_system_deps(out, {
        "system_deps": {"git": {"apt_package": "git", "apt_depends": ["zlib1g"]}},
    }, "b")
    assert out["system_deps"]["git"]["apt_depends"] == ["libc6", "zlib1g"]


# ─── _volume_target ───────────────────────────────────────────────────────────

def test_volume_target_extracts_target_segment():
    assert _volume_target("/host/path:/container/path") == "/container/path"


def test_volume_target_extracts_target_with_options():
    assert _volume_target("named-vol:/data:ro") == "/data"


def test_volume_target_no_colon_returns_input():
    assert _volume_target("/just/a/path") == "/just/a/path"


# ─── _merge_container — capabilities + volumes + init_scripts + chains ────────

def test_merge_container_capabilities_unioned():
    out = _empty_aggregate("p")
    out["container"]["capabilities"] = ["NET_ADMIN"]
    _merge_container(
        out, {"container": {"capabilities": ["NET_RAW", "NET_ADMIN"]}},
        "src", is_project=True,
    )
    assert out["container"]["capabilities"] == ["NET_ADMIN", "NET_RAW"]


def test_merge_container_volumes_dedup_by_target():
    """Same target, different source → first-write wins (not a conflict)."""
    out = _empty_aggregate("p")
    out["container"]["volumes"] = ["named-A:/data"]
    _merge_container(
        out, {"container": {"volumes": ["named-B:/data", "named-C:/other"]}},
        "src", is_project=True,
    )
    targets = sorted(_volume_target(v) for v in out["container"]["volumes"])
    assert targets == ["/data", "/other"]
    by_target = {_volume_target(v): v for v in out["container"]["volumes"]}
    assert by_target["/data"] == "named-A:/data"


def test_merge_container_init_scripts_order_preserved_and_dedup():
    """init_scripts must run in arrival order (deterministic), with no dups."""
    out = _empty_aggregate("p")
    out["container"]["init_scripts"] = ["one.sh", "two.sh"]
    _merge_container(
        out,
        {"container": {"init_scripts": ["two.sh", "three.sh"]}},
        "src", is_project=True,
    )
    assert out["container"]["init_scripts"] == ["one.sh", "two.sh", "three.sh"]


def test_merge_container_post_chains_concatenated_not_set_unioned():
    """post_start_chain is a sequence, not a set — concat preserves order/dups."""
    out = _empty_aggregate("p")
    out["container"]["post_start_chain"] = ["a"]
    _merge_container(
        out,
        {"container": {"post_start_chain": ["a", "b"]}},
        "src", is_project=True,
    )
    assert out["container"]["post_start_chain"] == ["a", "a", "b"]


# ─── _merge_container — env + project-vs-non-project asymmetry ────────────────

def test_merge_container_env_first_write_no_conflict():
    out = _empty_aggregate("p")
    _merge_container(
        out, {"container": {"env": {"FOO": "bar"}}},
        "src", is_project=True,
    )
    assert out["container"]["env"]["FOO"] == "bar"


def test_merge_container_env_project_conflict_overwrites():
    """is_project=True merge wins on env conflicts (project is authoritative)."""
    out = _empty_aggregate("p")
    out["container"]["env"]["FOO"] = "old"
    _merge_container(
        out, {"container": {"env": {"FOO": "new"}}},
        "project-src", is_project=True,
    )
    assert out["container"]["env"]["FOO"] == "new"


def test_merge_container_env_non_project_conflict_warns_and_keeps_existing(capsys):
    """Plugin can't override project env — warning to stderr, no overwrite."""
    out = _empty_aggregate("p")
    out["container"]["env"]["FOO"] = "project-value"
    _merge_container(
        out, {"container": {"env": {"FOO": "plugin-value"}}},
        "marketplace#plugin", is_project=False,
    )
    assert out["container"]["env"]["FOO"] == "project-value"
    captured = capsys.readouterr()
    assert "FOO" in captured.err
    assert "plugin-value" in captured.err
    assert "marketplace#plugin" in captured.err


def test_merge_container_project_only_fields_set_only_when_project():
    """remote_user/post_start/etc. are project-authority — non-project no-op."""
    out = _empty_aggregate("p")
    _merge_container(
        out, {"container": {"remote_user": "ignored", "post_start": "ignored"}},
        "plugin-src", is_project=False,
    )
    assert out["container"]["remote_user"] == ""
    assert out["container"]["post_start"] == ""


def test_merge_container_project_remote_user_set_only_first_time():
    """First non-empty project value sticks (later project merges don't clobber)."""
    out = _empty_aggregate("p")
    _merge_container(
        out, {"container": {"remote_user": "claude"}},
        "p1", is_project=True,
    )
    _merge_container(
        out, {"container": {"remote_user": "other"}},
        "p2", is_project=True,
    )
    assert out["container"]["remote_user"] == "claude"


def test_merge_container_vscode_settings_only_project_contributes():
    out = _empty_aggregate("p")
    _merge_container(
        out, {"container": {"vscode_settings": {"editor.fontSize": 14}}},
        "plugin-src", is_project=False,
    )
    assert out["container"]["vscode_settings"] == {}

    _merge_container(
        out, {"container": {"vscode_settings": {"editor.fontSize": 14}}},
        "project-src", is_project=True,
    )
    assert out["container"]["vscode_settings"] == {"editor.fontSize": 14}


# ─── _recompute_inferred_dedup ────────────────────────────────────────────────

def test_recompute_inferred_dedup_partitions_tools_by_system_deps():
    out = _empty_aggregate("p")
    out["system_packages"] = ["git"]
    out["system_deps"] = {"make": {"apt_package": "build-essential"}}
    out["inferred"]["tools"] = ["git", "make", "novel-tool"]
    _recompute_inferred_dedup(out)
    assert out["inferred"]["tools_confirmed"] == ["git"]
    # 'make' has apt_package=build-essential, but the tool name 'make'
    # is not in confirmed_tools (only 'build-essential' is).
    assert "make" in out["inferred"]["tools_new"]
    assert "novel-tool" in out["inferred"]["tools_new"]


def test_recompute_inferred_dedup_partitions_py_imports_case_insensitive():
    out = _empty_aggregate("p")
    out["libraries"]["python"] = ["Requests"]
    out["inferred"]["py_imports"] = ["requests", "unknown_pkg"]
    _recompute_inferred_dedup(out)
    assert out["inferred"]["py_imports_confirmed"] == ["requests"]
    assert out["inferred"]["py_imports_new"] == ["unknown_pkg"]


def test_recompute_inferred_dedup_partitions_ts_imports_case_insensitive():
    out = _empty_aggregate("p")
    out["libraries"]["node"] = ["React"]
    out["inferred"]["ts_imports"] = ["react", "novel-mod"]
    _recompute_inferred_dedup(out)
    assert out["inferred"]["ts_imports_confirmed"] == ["react"]
    assert out["inferred"]["ts_imports_new"] == ["novel-mod"]


def test_recompute_inferred_dedup_idempotent():
    """Running twice yields the same partition (no accumulation bug)."""
    out = _empty_aggregate("p")
    out["system_packages"] = ["git"]
    out["inferred"]["tools"] = ["git", "novel"]
    _recompute_inferred_dedup(out)
    snap_confirmed = list(out["inferred"]["tools_confirmed"])
    snap_new = list(out["inferred"]["tools_new"])
    _recompute_inferred_dedup(out)
    assert out["inferred"]["tools_confirmed"] == snap_confirmed
    assert out["inferred"]["tools_new"] == snap_new
