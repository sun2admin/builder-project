"""Phase 6 — devcontainer.json + workspace.env writers.

Takes the composed stack decisions and emits final artifacts under
builds/<build_name>/. See `.claude/plans/build-workflow-stack-composition.md`
§5-§8 (composition) and Step 8 (output placement).
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path


_VERSION_FEATURE_MAP = {
    "node":   "ghcr.io/devcontainers/features/node:1",
    "python": "ghcr.io/devcontainers/features/python:1",
}


def write_aggregated(agg: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "aggregated.json"
    path.write_text(json.dumps(agg, sort_keys=True, indent=2) + "\n")
    return path


def _resolve_image(l1_variant: str, l2_cli: str, l3_image: str | None) -> str:
    # Phase 6 MVP image priority (per spec):
    # 1. l3_image (already inherits L1+L2) when present.
    # 2. layer2-ai-install:<l2_cli> (L1 variant comes from L2's parent).
    # The "L1-variant-direct" case (rule 3 — fall back to layer1 + features
    # to install L2) is left for a future iteration.
    if l3_image:
        return l3_image
    return f"ghcr.io/sun2admin/layer2-ai-install:{l2_cli}"


def _devcontainer_name(build_json: dict) -> str:
    name = build_json.get("build_project") or build_json.get("project") or "build"
    return f"{name} (build-stack)"


def _volume_to_mount_string(vol: object) -> str | None:
    if isinstance(vol, str):
        return vol or None
    if not isinstance(vol, dict):
        return None
    target = vol.get("target") or ""
    if not target:
        return None
    src = vol.get("source") or vol.get("name") or ""
    vtype = vol.get("type") or ("bind" if str(src).startswith(("/", "$", "~")) else "volume")
    parts = [f"source={src}", f"target={target}", f"type={vtype}"]
    if vol.get("readonly"):
        parts.append("readonly")
    consistency = vol.get("consistency")
    if consistency:
        parts.append(f"consistency={consistency}")
    return ",".join(parts)


def _compose_run_args(agg: dict, compose_result: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def _add(arg: str) -> None:
        if arg and arg not in seen:
            seen.add(arg)
            out.append(arg)

    if (compose_result.get("firewall") or {}).get("cap_add"):
        _add("--cap-add=NET_ADMIN")
        _add("--cap-add=NET_RAW")

    for cap in (agg.get("container") or {}).get("capabilities") or []:
        _add(f"--cap-add={cap}")

    return out


def _compose_container_env(compose_result: dict, agg: dict) -> dict:
    env: dict[str, str] = {}
    for name in (compose_result.get("credentials") or {}).get("env_passthrough") or []:
        env[name] = "${localEnv:" + name + "}"
    for k, v in ((agg.get("container") or {}).get("env") or {}).items():
        if k not in env:
            env[k] = v
    return env


def _compose_mounts(compose_result: dict, agg: dict) -> list[str]:
    mounts: list[str] = []
    seen: set[str] = set()

    def _add(s: str | None) -> None:
        if s and s not in seen:
            seen.add(s)
            mounts.append(s)

    for entry in (compose_result.get("credentials") or {}).get("mounts") or []:
        _add(_volume_to_mount_string(entry))

    for vol in (agg.get("container") or {}).get("volumes") or []:
        _add(_volume_to_mount_string(vol))

    return mounts


def _apply_version_overlays(features: dict, version_overlays: dict) -> dict:
    out = dict(features) if features else {}
    for lang, ver in (version_overlays or {}).items():
        feat = _VERSION_FEATURE_MAP.get(lang)
        if not feat:
            continue
        cfg = dict(out.get(feat) or {})
        cfg["version"] = ver
        out[feat] = cfg
    return out


def write_devcontainer(
    agg: dict,
    l1_variant: str,
    l2_cli: str,
    l3_image: str | None,
    compose_result: dict,
    build_json: dict,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    features = _apply_version_overlays(
        compose_result.get("features") or {},
        compose_result.get("version_overlays") or {},
    )

    container = agg.get("container") or {}
    remote_user = container.get("remote_user") or "claude"

    init_chain = compose_result.get("init_chain") or []
    post_start = " && ".join(s for s in init_chain if s) if init_chain else ""

    forward_ports = sorted(set((agg.get("ports") or {}).get("inbound") or []))
    extensions = list(container.get("extensions") or [])

    dc: dict = {
        "name": _devcontainer_name(build_json),
        "image": _resolve_image(l1_variant, l2_cli, l3_image),
        "remoteUser": remote_user,
    }

    if features:
        dc["features"] = features

    run_args = _compose_run_args(agg, compose_result)
    if run_args:
        dc["runArgs"] = run_args

    container_env = _compose_container_env(compose_result, agg)
    if container_env:
        dc["containerEnv"] = container_env

    mounts = _compose_mounts(compose_result, agg)
    if mounts:
        dc["mounts"] = mounts

    if forward_ports:
        dc["forwardPorts"] = forward_ports

    workspace_mount = container.get("workspace_mount") or ""
    if workspace_mount:
        dc["workspaceMount"] = workspace_mount

    workspace_folder = container.get("workspace_folder") or ""
    if workspace_folder:
        dc["workspaceFolder"] = workspace_folder

    if post_start:
        dc["postStartCommand"] = post_start

    wait_for = container.get("wait_for") or ""
    if wait_for:
        dc["waitFor"] = wait_for

    post_create = container.get("post_create") or ""
    if post_create:
        dc["postCreateCommand"] = post_create

    post_attach = container.get("post_attach") or ""
    if post_attach:
        dc["postAttachCommand"] = post_attach

    shutdown_action = container.get("shutdown_action") or ""
    if shutdown_action:
        dc["shutdownAction"] = shutdown_action

    vscode_settings = container.get("vscode_settings") or {}
    if extensions or vscode_settings:
        vscode: dict = {}
        if extensions:
            vscode["extensions"] = extensions
        if vscode_settings:
            vscode["settings"] = vscode_settings
        dc["customizations"] = {"vscode": vscode}

    path = out_dir / "devcontainer.json"
    path.write_text(json.dumps(dc, sort_keys=True, indent=2) + "\n")
    return path


def write_workspace_env(
    agg: dict,
    l1_variant: str,
    l2_cli: str,
    l3_image: str | None,
    build_json: dict,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    project_repo = build_json.get("project_repo") or ""
    build_name = build_json.get("build_project") or ""
    last_modified = datetime.date.today().isoformat()

    lines = [
        f"BASE_IMAGE={l1_variant}",
        f"AI_INSTALL={l2_cli}",
        f"PLUGIN_LAYER={l3_image or ''}",
        f"PROJECT_REPO={project_repo}",
        f"BUILD_NAME={build_name}",
        f"LAST_MODIFIED={last_modified}",
    ]

    path = out_dir / "workspace.env"
    path.write_text("\n".join(lines) + "\n")
    return path
