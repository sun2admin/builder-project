"""Phase 4 — multi-repo analysis aggregation.

Reads per-repo analysis.json files, merges per the rules in
`.claude/plans/build-workflow-stack-composition.md` §1.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


_SET_FIELDS = (
    "languages",
    "system_packages",
    "env_vars",
    "claude_plugins",
    "browser_tools",
    "extra_binaries",
    "global_js_packages",
    "dockerfile_python_installs",
    "dockerfile_go_installs",
    "runtime_extras",
)

_LIB_LANGS = ("node", "python", "go", "rust")

_INFERRED_LIST_FIELDS = (
    "tools",
    "py_imports",
    "ts_imports",
    "ci_tools",
)

_VERSION_NUM_RE = re.compile(r"(\d+(?:\.\d+)*)")


def _load_analysis(repo_root: Path, owner_repo: str) -> dict:
    path = repo_root / "analyzed_repos" / owner_repo / "analysis.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"missing analysis: {path} (run /analyze-repo {owner_repo})"
        )
    return json.loads(path.read_text())


def _empty_aggregate(build_project: str) -> dict:
    return {
        "schema_version": 0,
        "repo": build_project,
        "project": build_project,
        "analyzed_at": "",
        "purpose": "",
        "primary_language": "",
        "languages": [],
        "runtime_extras": [],
        "runtime_versions": {},
        "dockerfile_base": "",
        "system_packages": [],
        "extra_binaries": [],
        "global_js_packages": [],
        "dockerfile_python_installs": [],
        "dockerfile_go_installs": [],
        "libraries": {"node": [], "python": [], "go": [], "rust": []},
        "ports": {"inbound": []},
        "external_services": {"domains": [], "source": ""},
        "env_vars": [],
        "browser_tools": [],
        "github_api_usage": False,
        "container": {
            "capabilities": [],
            "volumes": [],
            "env": {},
            "remote_user": "",
            "post_start": "",
            "post_create": "",
            "post_start_chain": [],
            "post_create_chain": [],
            "init_scripts": [],
            "extensions": [],
        },
        "credentials_required": {
            "api_keys": [],
            "tokens": [],
            "ssh": False,
            "other": [],
        },
        "mcp_servers": [],
        "claude_plugins": [],
        "inferred": {
            "tools": [],
            "tools_new": [],
            "tools_confirmed": [],
            "py_imports": [],
            "py_imports_new": [],
            "py_imports_confirmed": [],
            "ts_imports": [],
            "ts_imports_new": [],
            "ts_imports_confirmed": [],
            "ci_tools": [],
        },
        "system_deps": {},
        "_sources": [],
    }


def _merge_set_field(out: dict, analysis: dict, field: str) -> None:
    out[field] = sorted(set(out.get(field, [])) | set(analysis.get(field, []) or []))


def _merge_libraries(out: dict, analysis: dict) -> None:
    src = analysis.get("libraries", {}) or {}
    dst = out["libraries"]
    for lang in _LIB_LANGS:
        dst[lang] = sorted(set(dst.get(lang, [])) | set(src.get(lang, []) or []))


def _merge_credentials(out: dict, analysis: dict) -> None:
    src = analysis.get("credentials_required", {}) or {}
    dst = out["credentials_required"]
    for bucket in ("api_keys", "tokens", "other"):
        dst[bucket] = sorted(set(dst.get(bucket, [])) | set(src.get(bucket, []) or []))
    dst["ssh"] = bool(dst.get("ssh", False)) or bool(src.get("ssh", False))


def _merge_mcp_servers(out: dict, analysis: dict, source: str) -> None:
    """Merge mcp_servers entries by name.

    Canonical analysis.json emits mcp_servers as list[str] (just names);
    schema dataclass declares list[dict]. Accept both shapes: a string is
    treated as a name-only entry equivalent to {"name": <s>}.
    """
    def _name_of(entry):
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return entry.get("name")
        return None

    existing = {_name_of(s): s for s in out["mcp_servers"] if _name_of(s)}
    for server in analysis.get("mcp_servers", []) or []:
        name = _name_of(server)
        if not name:
            continue
        if name in existing and existing[name] != server:
            raise ValueError(
                f"MCP server name conflict for '{name}': "
                f"{existing[name]!r} (already merged) vs {server!r} (from {source})"
            )
        existing[name] = server
    out["mcp_servers"] = sorted(
        existing.values(),
        key=lambda s: s if isinstance(s, str) else s.get("name", ""),
    )


def _parse_version_key(raw: str) -> tuple | None:
    """Return a comparable tuple for a pinned version, or None for unpinned."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("latest", "*", "any"):
        return None
    m = _VERSION_NUM_RE.search(s)
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def _versions_compatible(a: str, b: str) -> bool:
    """Two pinned versions are compatible iff their major matches."""
    ka, kb = _parse_version_key(a), _parse_version_key(b)
    if ka is None or kb is None:
        return True
    return ka[0] == kb[0]


def _merge_runtime_versions(out: dict, analysis: dict, source: str) -> None:
    dst = out["runtime_versions"]
    for lang, ver in (analysis.get("runtime_versions") or {}).items():
        if lang not in dst:
            dst[lang] = ver
            continue
        cur = dst[lang]
        cur_key = _parse_version_key(cur)
        new_key = _parse_version_key(ver)
        if cur_key is None and new_key is None:
            continue
        if cur_key is None:
            dst[lang] = ver
            continue
        if new_key is None:
            continue
        if not _versions_compatible(cur, ver):
            raise ValueError(
                f"runtime version cross-pin conflict for '{lang}': "
                f"{cur!r} vs {ver!r} (from {source})"
            )
        if new_key > cur_key:
            dst[lang] = ver


def _merge_container(out: dict, analysis: dict, source: str, is_project: bool) -> None:
    src = analysis.get("container", {}) or {}
    dst = out["container"]

    dst["capabilities"] = sorted(
        set(dst.get("capabilities", [])) | set(src.get("capabilities", []) or [])
    )

    by_target: dict[str, str] = {}
    for vol in dst.get("volumes", []):
        target = _volume_target(vol)
        by_target.setdefault(target, vol)
    for vol in src.get("volumes", []) or []:
        target = _volume_target(vol)
        by_target.setdefault(target, vol)
    dst["volumes"] = list(by_target.values())

    src_env = src.get("env", {}) or {}
    for k, v in src_env.items():
        if k in dst["env"]:
            if dst["env"][k] != v:
                if is_project:
                    dst["env"][k] = v
                else:
                    print(
                        f"warning: container.env conflict on '{k}': "
                        f"keeping {dst['env'][k]!r}, ignoring {v!r} from {source}",
                        file=sys.stderr,
                    )
        else:
            dst["env"][k] = v

    if is_project:
        if not dst.get("remote_user"):
            dst["remote_user"] = src.get("remote_user", "")
        if not dst.get("post_start"):
            dst["post_start"] = src.get("post_start", "")
        if not dst.get("post_create"):
            dst["post_create"] = src.get("post_create", "")

    dst["post_start_chain"] = list(dst["post_start_chain"]) + list(
        src.get("post_start_chain", []) or []
    )
    dst["post_create_chain"] = list(dst["post_create_chain"]) + list(
        src.get("post_create_chain", []) or []
    )

    seen_scripts: set[str] = set(dst["init_scripts"])
    for script in src.get("init_scripts", []) or []:
        if script not in seen_scripts:
            dst["init_scripts"].append(script)
            seen_scripts.add(script)

    dst["extensions"] = sorted(
        set(dst.get("extensions", [])) | set(src.get("extensions", []) or [])
    )


def _volume_target(vol: str) -> str:
    if not isinstance(vol, str):
        return str(vol)
    parts = vol.split(":")
    if len(parts) >= 2:
        return parts[1]
    return vol


def _merge_ports(out: dict, analysis: dict) -> None:
    src = (analysis.get("ports") or {}).get("inbound", []) or []
    out["ports"]["inbound"] = sorted(set(out["ports"]["inbound"]) | set(src))


def _merge_external_services(out: dict, analysis: dict) -> None:
    src = analysis.get("external_services", {}) or {}
    out["external_services"]["domains"] = sorted(
        set(out["external_services"]["domains"]) | set(src.get("domains", []) or [])
    )
    src_source = src.get("source", "") or ""
    cur_source = out["external_services"]["source"]
    if not cur_source:
        out["external_services"]["source"] = src_source
    elif src_source and src_source != cur_source:
        out["external_services"]["source"] = "multi"


def _merge_inferred(out: dict, analysis: dict) -> None:
    src = analysis.get("inferred", {}) or {}
    dst = out["inferred"]
    for fld in _INFERRED_LIST_FIELDS:
        dst[fld] = sorted(set(dst.get(fld, [])) | set(src.get(fld, []) or []))


def _recompute_inferred_dedup(out: dict) -> None:
    libs = out["libraries"]
    sys_pkgs = set(out["system_packages"])
    inferred = out["inferred"]

    confirmed_tools = set(sys_pkgs)
    for sysdep in out["system_deps"].values():
        pkg = (sysdep or {}).get("apt_package")
        if pkg:
            confirmed_tools.add(pkg)
    tools = inferred.get("tools", [])
    inferred["tools_confirmed"] = sorted(t for t in tools if t in confirmed_tools)
    inferred["tools_new"] = sorted(t for t in tools if t not in confirmed_tools)

    py_libs = {p.lower() for p in libs.get("python", [])}
    py_imports = inferred.get("py_imports", [])
    inferred["py_imports_confirmed"] = sorted(
        p for p in py_imports if p.lower() in py_libs
    )
    inferred["py_imports_new"] = sorted(
        p for p in py_imports if p.lower() not in py_libs
    )

    ts_libs = {p.lower() for p in libs.get("node", [])}
    ts_imports = inferred.get("ts_imports", [])
    inferred["ts_imports_confirmed"] = sorted(
        t for t in ts_imports if t.lower() in ts_libs
    )
    inferred["ts_imports_new"] = sorted(
        t for t in ts_imports if t.lower() not in ts_libs
    )


def _merge_system_deps(out: dict, analysis: dict, source: str) -> None:
    src = analysis.get("system_deps", {}) or {}
    dst = out["system_deps"]
    for tool, info in src.items():
        info = info or {}
        if tool in dst:
            cur = dst[tool] or {}
            cur_pkg = cur.get("apt_package")
            new_pkg = info.get("apt_package")
            if cur_pkg and new_pkg and cur_pkg != new_pkg:
                raise ValueError(
                    f"system_deps apt_package conflict for tool '{tool}': "
                    f"{cur_pkg!r} vs {new_pkg!r} (from {source})"
                )
            merged_depends = sorted(
                set(cur.get("apt_depends", []) or [])
                | set(info.get("apt_depends", []) or [])
            )
            dst[tool] = {
                "apt_package": cur_pkg or new_pkg,
                "apt_depends": merged_depends,
            }
        else:
            dst[tool] = {
                "apt_package": info.get("apt_package"),
                "apt_depends": list(info.get("apt_depends", []) or []),
            }


def _merge_one(out: dict, analysis: dict, source: str, *, is_project: bool) -> None:
    out["schema_version"] = max(
        int(out.get("schema_version", 0) or 0),
        int(analysis.get("schema_version", 0) or 0),
    )

    analyzed_at = analysis.get("analyzed_at", "") or ""
    if analyzed_at > (out.get("analyzed_at") or ""):
        out["analyzed_at"] = analyzed_at

    if is_project:
        out["primary_language"] = analysis.get("primary_language", "") or ""
        out["purpose"] = analysis.get("purpose", "") or ""
        out["dockerfile_base"] = analysis.get("dockerfile_base", "") or ""
    else:
        if not out["primary_language"]:
            out["primary_language"] = analysis.get("primary_language", "") or ""

    if analysis.get("github_api_usage"):
        out["github_api_usage"] = True

    for fld in _SET_FIELDS:
        _merge_set_field(out, analysis, fld)

    _merge_libraries(out, analysis)
    _merge_credentials(out, analysis)
    _merge_mcp_servers(out, analysis, source)
    _merge_runtime_versions(out, analysis, source)
    _merge_container(out, analysis, source, is_project=is_project)
    _merge_ports(out, analysis)
    _merge_external_services(out, analysis)
    _merge_inferred(out, analysis)
    _merge_system_deps(out, analysis, source)

    out["_sources"].append(source)


def aggregate(build_json: dict, repo_root: Path) -> dict:
    """Read all referenced analysis.json files and merge per parent plan §1."""
    project_repo = build_json.get("project_repo")
    plugin_repos = list(build_json.get("plugin_repos", []) or [])
    build_project = build_json.get("build_project", "")

    out = _empty_aggregate(build_project)

    if project_repo:
        analysis = _load_analysis(repo_root, project_repo)
        _merge_one(out, analysis, project_repo, is_project=True)

    for plugin in plugin_repos:
        analysis = _load_analysis(repo_root, plugin)
        _merge_one(out, analysis, plugin, is_project=False)

    out["repo"] = build_project
    out["project"] = build_project

    if out["schema_version"] == 0:
        from .analyzers.schema import SCHEMA_VERSION
        out["schema_version"] = SCHEMA_VERSION

    _recompute_inferred_dedup(out)

    return out
