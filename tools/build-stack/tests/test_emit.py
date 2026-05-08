"""Unit tests for build_stack.emit — Phase 6 devcontainer.json + workspace.env writers.

Covers:
  * pure helpers: `_resolve_image`, `_devcontainer_name`,
    `_volume_to_mount_string`, `_compose_run_args`, `_compose_container_env`,
    `_compose_mounts`, `_apply_version_overlays`
  * file writers: `write_aggregated`, `write_devcontainer`, `write_workspace_env`
    (tmp_path fixtures, JSON shape assertions)

The dominant invariant in `write_devcontainer` is *conditional field placement* —
every field is added only when its source data is truthy. These tests pin that
behavior so empty `[]` / `{}` / `""` inputs never start leaking into emitted
devcontainer.json files.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from build_stack.emit import (
    _apply_version_overlays,
    _compose_container_env,
    _compose_mounts,
    _compose_run_args,
    _devcontainer_name,
    _resolve_image,
    _volume_to_mount_string,
    write_aggregated,
    write_devcontainer,
    write_workspace_env,
)


# ─── _resolve_image ───────────────────────────────────────────────────────────

def test_resolve_image_l3_present_wins():
    """L3 image already inherits L1+L2 → take it as-is."""
    out = _resolve_image("latest", "claude", "ghcr.io/sun2admin/claude-plugins-base")
    assert out == "ghcr.io/sun2admin/claude-plugins-base"


def test_resolve_image_l3_none_falls_through_to_l2():
    out = _resolve_image("latest", "claude", None)
    assert out == "ghcr.io/sun2admin/layer2-ai-install:claude"


def test_resolve_image_l3_empty_string_treated_as_falsy():
    """Empty string is falsy → fall through to L2 (defensive)."""
    out = _resolve_image("latest", "gemini", "")
    assert out == "ghcr.io/sun2admin/layer2-ai-install:gemini"


def test_resolve_image_l2_cli_interpolated_into_tag():
    out = _resolve_image("latest", "gemini", None)
    assert out.endswith(":gemini")


# ─── _devcontainer_name ───────────────────────────────────────────────────────

def test_devcontainer_name_uses_build_project_first():
    assert _devcontainer_name({"build_project": "myapp", "project": "fallback"}) == "myapp (build-stack)"


def test_devcontainer_name_falls_back_to_project():
    assert _devcontainer_name({"project": "fallback"}) == "fallback (build-stack)"


def test_devcontainer_name_default_when_both_missing():
    assert _devcontainer_name({}) == "build (build-stack)"


def test_devcontainer_name_suffix_always_appended():
    """Even with a populated name, the suffix marks this as a build-stack-emitted container."""
    assert _devcontainer_name({"build_project": "x"}).endswith(" (build-stack)")


# ─── _volume_to_mount_string ──────────────────────────────────────────────────

def test_volume_to_mount_string_plain_string_passthrough():
    s = "source=foo,target=/foo,type=volume"
    assert _volume_to_mount_string(s) == s


def test_volume_to_mount_string_empty_string_returns_none():
    assert _volume_to_mount_string("") is None


def test_volume_to_mount_string_unsupported_shape_returns_none():
    """Lists / numbers / None don't match either branch → None."""
    assert _volume_to_mount_string(None) is None
    assert _volume_to_mount_string(["a", "b"]) is None
    assert _volume_to_mount_string(42) is None


def test_volume_to_mount_string_dict_missing_target_returns_none():
    assert _volume_to_mount_string({"source": "vol", "type": "volume"}) is None


def test_volume_to_mount_string_dict_volume_default_for_non_path_source():
    out = _volume_to_mount_string({"source": "claude-vol", "target": "/home/claude"})
    assert "type=volume" in out
    assert "source=claude-vol" in out
    assert "target=/home/claude" in out


def test_volume_to_mount_string_dict_bind_inferred_for_absolute_path():
    """Source starting with '/' implies a bind mount (auto-detection)."""
    out = _volume_to_mount_string({"source": "/host/path", "target": "/in/container"})
    assert "type=bind" in out


def test_volume_to_mount_string_dict_bind_inferred_for_dollar_var():
    """Source like '${localWorkspaceFolder}' is a bind reference."""
    out = _volume_to_mount_string({"source": "${localWorkspaceFolder}", "target": "/ws"})
    assert "type=bind" in out


def test_volume_to_mount_string_dict_bind_inferred_for_tilde():
    out = _volume_to_mount_string({"source": "~/host/dir", "target": "/in"})
    assert "type=bind" in out


def test_volume_to_mount_string_explicit_type_overrides_inference():
    """If user specifies type=volume even with absolute-path source → keep their choice."""
    out = _volume_to_mount_string({
        "source": "/host/path", "target": "/in", "type": "volume",
    })
    assert "type=volume" in out
    assert "type=bind" not in out


def test_volume_to_mount_string_uses_name_as_source_fallback():
    """When `source` is missing, `name` is the docker-compose-style alias."""
    out = _volume_to_mount_string({"name": "my-vol", "target": "/data"})
    assert "source=my-vol" in out


def test_volume_to_mount_string_readonly_flag_appended():
    out = _volume_to_mount_string({
        "source": "/host", "target": "/ro", "readonly": True,
    })
    assert out.endswith(",readonly")


def test_volume_to_mount_string_consistency_appended():
    """consistency=cached is a macOS Docker Desktop perf hint."""
    out = _volume_to_mount_string({
        "source": "/host", "target": "/x", "consistency": "cached",
    })
    assert "consistency=cached" in out


# ─── _compose_run_args ────────────────────────────────────────────────────────

def test_compose_run_args_firewall_adds_net_caps():
    """Firewall composition signals NET_ADMIN+NET_RAW are required."""
    out = _compose_run_args({}, {"firewall": {"cap_add": ["NET_ADMIN", "NET_RAW"]}})
    assert "--cap-add=NET_ADMIN" in out
    assert "--cap-add=NET_RAW" in out


def test_compose_run_args_no_firewall_no_net_caps():
    out = _compose_run_args({}, {})
    assert "--cap-add=NET_ADMIN" not in out
    assert "--cap-add=NET_RAW" not in out


def test_compose_run_args_agg_capabilities_passed_through():
    out = _compose_run_args(
        {"container": {"capabilities": ["SYS_PTRACE"]}}, {},
    )
    assert "--cap-add=SYS_PTRACE" in out


def test_compose_run_args_dedup_across_sources():
    """If firewall expands NET_ADMIN and agg also requests it → only once."""
    out = _compose_run_args(
        {"container": {"capabilities": ["NET_ADMIN"]}},
        {"firewall": {"cap_add": ["NET_ADMIN"]}},
    )
    assert out.count("--cap-add=NET_ADMIN") == 1


def test_compose_run_args_firewall_caps_listed_first():
    """Order rule: firewall (boot-essential) listed before agg (project-specific)."""
    out = _compose_run_args(
        {"container": {"capabilities": ["SYS_PTRACE"]}},
        {"firewall": {"cap_add": ["NET_ADMIN"]}},
    )
    assert out.index("--cap-add=NET_ADMIN") < out.index("--cap-add=SYS_PTRACE")


def test_compose_run_args_empty_inputs_empty_output():
    assert _compose_run_args({}, {}) == []


# ─── _compose_container_env ───────────────────────────────────────────────────

def test_compose_container_env_passthrough_uses_localenv_syntax():
    """Secret env vars must use ${localEnv:NAME} so they don't get baked into JSON."""
    env = _compose_container_env(
        {"credentials": {"env_passthrough": ["GITHUB_TOKEN"]}}, {},
    )
    assert env == {"GITHUB_TOKEN": "${localEnv:GITHUB_TOKEN}"}


def test_compose_container_env_agg_env_added_when_no_collision():
    env = _compose_container_env(
        {}, {"container": {"env": {"DEBUG": "1"}}},
    )
    assert env == {"DEBUG": "1"}


def test_compose_container_env_passthrough_wins_on_collision():
    """If GITHUB_TOKEN is in passthrough AND in agg.container.env → passthrough wins.
    Reason: agg literal would bake the value; passthrough preserves the secret indirection."""
    env = _compose_container_env(
        {"credentials": {"env_passthrough": ["GITHUB_TOKEN"]}},
        {"container": {"env": {"GITHUB_TOKEN": "literal-leaked"}}},
    )
    assert env == {"GITHUB_TOKEN": "${localEnv:GITHUB_TOKEN}"}


def test_compose_container_env_empty_inputs_empty_output():
    assert _compose_container_env({}, {}) == {}


# ─── _compose_mounts ──────────────────────────────────────────────────────────

def test_compose_mounts_credential_mounts_first():
    """Credential mounts (boot-critical) listed before agg-volume mounts."""
    out = _compose_mounts(
        {"credentials": {"mounts": [{"source": "/creds", "target": "/run/credentials"}]}},
        {"container": {"volumes": [{"source": "data", "target": "/data"}]}},
    )
    assert "target=/run/credentials" in out[0]
    assert "target=/data" in out[1]


def test_compose_mounts_dedup_across_sources():
    """Same mount string appearing in both inputs → emitted once."""
    same = "source=/x,target=/y,type=bind"
    out = _compose_mounts(
        {"credentials": {"mounts": [same]}},
        {"container": {"volumes": [same]}},
    )
    assert out == [same]


def test_compose_mounts_skips_invalid_entries():
    """Dicts missing target → silently dropped."""
    out = _compose_mounts(
        {"credentials": {"mounts": [{"source": "no-target"}]}},
        {"container": {"volumes": []}},
    )
    assert out == []


def test_compose_mounts_empty_inputs_empty_output():
    assert _compose_mounts({}, {}) == []


# ─── _apply_version_overlays ──────────────────────────────────────────────────

def test_apply_version_overlays_known_lang_added():
    out = _apply_version_overlays({}, {"node": "20"})
    assert out == {"ghcr.io/devcontainers/features/node:1": {"version": "20"}}


def test_apply_version_overlays_unknown_lang_silently_skipped():
    """Only node + python supported; 'go' → no overlay (caller already validated upstream)."""
    out = _apply_version_overlays({}, {"go": "1.22"})
    assert out == {}


def test_apply_version_overlays_preserves_existing_feature_cfg():
    """If features already has the feature with other keys, keep them and just add version."""
    feat_id = "ghcr.io/devcontainers/features/python:1"
    existing = {feat_id: {"installTools": True}}
    out = _apply_version_overlays(existing, {"python": "3.12"})
    assert out[feat_id] == {"installTools": True, "version": "3.12"}


def test_apply_version_overlays_no_overlays_returns_unchanged():
    feats = {"ghcr.io/devcontainers/features/git:1": {}}
    out = _apply_version_overlays(feats, {})
    assert out == feats


def test_apply_version_overlays_input_features_not_mutated():
    """Defensive copy: caller's dict shouldn't be modified in place."""
    feats = {"ghcr.io/devcontainers/features/node:1": {"installTools": True}}
    snapshot = json.dumps(feats, sort_keys=True)
    _apply_version_overlays(feats, {"node": "20"})
    assert json.dumps(feats, sort_keys=True) == snapshot


# ─── write_aggregated ─────────────────────────────────────────────────────────

def test_write_aggregated_creates_parent_dir(tmp_path):
    """Nested out_dir gets created on demand (mkdir parents=True)."""
    nested = tmp_path / "a" / "b" / "c"
    write_aggregated({"foo": 1}, nested)
    assert nested.is_dir()


def test_write_aggregated_writes_sorted_json(tmp_path):
    """sort_keys=True ensures byte-stable output across runs."""
    p = write_aggregated({"z": 1, "a": 2}, tmp_path)
    text = p.read_text()
    assert text.index('"a"') < text.index('"z"')


def test_write_aggregated_trailing_newline(tmp_path):
    p = write_aggregated({}, tmp_path)
    assert p.read_text().endswith("\n")


def test_write_aggregated_returns_path_to_file(tmp_path):
    p = write_aggregated({}, tmp_path)
    assert p.name == "aggregated.json"
    assert p.is_file()


# ─── write_devcontainer ───────────────────────────────────────────────────────

def _minimal_dc(tmp_path: Path, **overrides) -> dict:
    """Run write_devcontainer with sane defaults, returning parsed JSON."""
    args = {
        "agg": {},
        "l1_variant": "latest",
        "l2_cli": "claude",
        "l3_image": None,
        "compose_result": {},
        "build_json": {"build_project": "test"},
        "out_dir": tmp_path,
    }
    args.update(overrides)
    p = write_devcontainer(**args)
    return json.loads(p.read_text())


def test_write_devcontainer_minimal_only_required_fields(tmp_path):
    """Empty agg + empty compose → only `name`, `image`, `remoteUser` emitted."""
    dc = _minimal_dc(tmp_path)
    assert set(dc.keys()) == {"name", "image", "remoteUser"}


def test_write_devcontainer_default_remote_user_is_claude(tmp_path):
    dc = _minimal_dc(tmp_path)
    assert dc["remoteUser"] == "claude"


def test_write_devcontainer_remote_user_overridable(tmp_path):
    dc = _minimal_dc(tmp_path, agg={"container": {"remote_user": "vscode"}})
    assert dc["remoteUser"] == "vscode"


def test_write_devcontainer_l3_image_used_when_present(tmp_path):
    dc = _minimal_dc(tmp_path, l3_image="ghcr.io/x/y:tag")
    assert dc["image"] == "ghcr.io/x/y:tag"


def test_write_devcontainer_features_only_when_present(tmp_path):
    """Empty features dict → key omitted (don't emit `"features": {}`)."""
    dc = _minimal_dc(tmp_path, compose_result={"features": {}})
    assert "features" not in dc


def test_write_devcontainer_features_emitted_when_set(tmp_path):
    dc = _minimal_dc(tmp_path, compose_result={
        "features": {"ghcr.io/devcontainers/features/node:1": {}},
    })
    assert "features" in dc


def test_write_devcontainer_version_overlay_applied_to_features(tmp_path):
    """Pin: emit applies version overlays so compose layer doesn't have to."""
    dc = _minimal_dc(tmp_path, compose_result={
        "features": {},
        "version_overlays": {"node": "20"},
    })
    feat_id = "ghcr.io/devcontainers/features/node:1"
    assert dc["features"][feat_id]["version"] == "20"


def test_write_devcontainer_init_chain_joined_with_double_amp(tmp_path):
    """init_chain → postStartCommand using ` && ` so a failure aborts the chain."""
    dc = _minimal_dc(tmp_path, compose_result={
        "init_chain": ["a.sh", "b.sh"],
    })
    assert dc["postStartCommand"] == "a.sh && b.sh"


def test_write_devcontainer_init_chain_empty_omits_post_start(tmp_path):
    dc = _minimal_dc(tmp_path, compose_result={"init_chain": []})
    assert "postStartCommand" not in dc


def test_write_devcontainer_run_args_only_when_present(tmp_path):
    dc = _minimal_dc(tmp_path)
    assert "runArgs" not in dc


def test_write_devcontainer_run_args_emitted_for_firewall(tmp_path):
    dc = _minimal_dc(tmp_path, compose_result={
        "firewall": {"cap_add": ["NET_ADMIN", "NET_RAW"]},
    })
    assert "--cap-add=NET_ADMIN" in dc["runArgs"]


def test_write_devcontainer_forward_ports_sorted_and_deduplicated(tmp_path):
    dc = _minimal_dc(tmp_path, agg={"ports": {"inbound": [8080, 3000, 8080, 3000]}})
    assert dc["forwardPorts"] == [3000, 8080]


def test_write_devcontainer_customizations_omitted_when_no_extensions_or_settings(tmp_path):
    dc = _minimal_dc(tmp_path)
    assert "customizations" not in dc


def test_write_devcontainer_customizations_emitted_for_extensions_only(tmp_path):
    dc = _minimal_dc(tmp_path, agg={"container": {"extensions": ["ms-python.python"]}})
    assert dc["customizations"]["vscode"]["extensions"] == ["ms-python.python"]
    assert "settings" not in dc["customizations"]["vscode"]


def test_write_devcontainer_customizations_emitted_for_settings_only(tmp_path):
    dc = _minimal_dc(tmp_path, agg={
        "container": {"vscode_settings": {"editor.formatOnSave": True}},
    })
    assert dc["customizations"]["vscode"]["settings"] == {"editor.formatOnSave": True}


def test_write_devcontainer_workspace_mount_and_folder_threaded_through(tmp_path):
    dc = _minimal_dc(tmp_path, agg={"container": {
        "workspace_mount": "source=ws,target=/workspace,type=volume",
        "workspace_folder": "/workspace",
    }})
    assert dc["workspaceMount"] == "source=ws,target=/workspace,type=volume"
    assert dc["workspaceFolder"] == "/workspace"


def test_write_devcontainer_lifecycle_hooks_threaded_through(tmp_path):
    dc = _minimal_dc(tmp_path, agg={"container": {
        "wait_for": "postStartCommand",
        "post_create": "echo created",
        "post_attach": "echo attached",
        "shutdown_action": "stopContainer",
    }})
    assert dc["waitFor"] == "postStartCommand"
    assert dc["postCreateCommand"] == "echo created"
    assert dc["postAttachCommand"] == "echo attached"
    assert dc["shutdownAction"] == "stopContainer"


def test_write_devcontainer_credentials_become_container_env(tmp_path):
    dc = _minimal_dc(tmp_path, compose_result={
        "credentials": {"env_passthrough": ["GITHUB_TOKEN"]},
    })
    assert dc["containerEnv"] == {"GITHUB_TOKEN": "${localEnv:GITHUB_TOKEN}"}


def test_write_devcontainer_credential_mounts_emitted_first(tmp_path):
    dc = _minimal_dc(tmp_path,
        agg={"container": {"volumes": [{"source": "data-vol", "target": "/data"}]}},
        compose_result={"credentials": {"mounts": [
            {"source": "/host/creds", "target": "/run/credentials", "type": "bind"},
        ]}},
    )
    assert "target=/run/credentials" in dc["mounts"][0]
    assert "target=/data" in dc["mounts"][1]


def test_write_devcontainer_output_is_sort_keyed_with_trailing_newline(tmp_path):
    """Byte-stable JSON across runs (deterministic builds)."""
    p = write_devcontainer(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        compose_result={}, build_json={}, out_dir=tmp_path,
    )
    text = p.read_text()
    assert text.endswith("\n")
    assert text.index('"image"') < text.index('"name"')
    assert text.index('"name"') < text.index('"remoteUser"')


def test_write_devcontainer_creates_nested_parent(tmp_path):
    nested = tmp_path / "builds" / "myproj"
    write_devcontainer(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        compose_result={}, build_json={}, out_dir=nested,
    )
    assert (nested / "devcontainer.json").is_file()


# ─── write_workspace_env ──────────────────────────────────────────────────────

def _read_env(p: Path) -> dict:
    """Parse KEY=VALUE lines into a dict (preserving empty values)."""
    out = {}
    for line in p.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def test_write_workspace_env_emits_six_canonical_keys(tmp_path):
    p = write_workspace_env(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        build_json={"project_repo": "owner/repo", "build_project": "my-build"},
        out_dir=tmp_path,
    )
    env = _read_env(p)
    assert set(env.keys()) == {
        "BASE_IMAGE", "AI_INSTALL", "PLUGIN_LAYER",
        "PROJECT_REPO", "BUILD_NAME", "LAST_MODIFIED",
    }


def test_write_workspace_env_threads_args_to_keys(tmp_path):
    p = write_workspace_env(
        agg={}, l1_variant="playwright_with_chromium", l2_cli="gemini",
        l3_image="ghcr.io/x/y:tag",
        build_json={"project_repo": "o/r", "build_project": "b"},
        out_dir=tmp_path,
    )
    env = _read_env(p)
    assert env["BASE_IMAGE"] == "playwright_with_chromium"
    assert env["AI_INSTALL"] == "gemini"
    assert env["PLUGIN_LAYER"] == "ghcr.io/x/y:tag"
    assert env["PROJECT_REPO"] == "o/r"
    assert env["BUILD_NAME"] == "b"


def test_write_workspace_env_l3_none_renders_empty_value(tmp_path):
    """`PLUGIN_LAYER=` with no value when no L3 image — tooling consumers must handle this."""
    p = write_workspace_env(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        build_json={}, out_dir=tmp_path,
    )
    env = _read_env(p)
    assert env["PLUGIN_LAYER"] == ""


def test_write_workspace_env_last_modified_is_today(tmp_path):
    p = write_workspace_env(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        build_json={}, out_dir=tmp_path,
    )
    env = _read_env(p)
    assert env["LAST_MODIFIED"] == datetime.date.today().isoformat()


def test_write_workspace_env_trailing_newline(tmp_path):
    p = write_workspace_env(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        build_json={}, out_dir=tmp_path,
    )
    assert p.read_text().endswith("\n")


def test_write_workspace_env_creates_nested_parent(tmp_path):
    nested = tmp_path / "builds" / "x"
    write_workspace_env(
        agg={}, l1_variant="latest", l2_cli="claude", l3_image=None,
        build_json={}, out_dir=nested,
    )
    assert (nested / "workspace.env").is_file()
