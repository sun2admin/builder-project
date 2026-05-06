"""Phase 5b — L4 overlay composition, firewall, init script chain.

Computes:
- `extras_needed` (languages not in L1 floor → devcontainer features)
- `version_overlays` (baked-in lang at wrong version → side-by-side feature)
- `firewall.cap_add` (NET_ADMIN/NET_RAW required) and `extra_domains` diff
- credentials wiring (containerEnv passthrough vs /run/credentials/<name> mount)
- final init script chain via topological sort under partial order

See `.claude/plans/build-workflow-stack-composition.md` §5–§8.
"""

from __future__ import annotations

import re
from pathlib import Path


L1_LATEST_RUNTIMES = {"node", "python", "shell"}
L1_LATEST_VERSIONS = {"node": "22", "python": "3.12"}

DEVCONTAINER_FEATURE_MAP = {
    "go":     "ghcr.io/devcontainers/features/go:1",
    "rust":   "ghcr.io/devcontainers/features/rust:1",
    "ruby":   "ghcr.io/devcontainers/features/ruby:1",
    "java":   "ghcr.io/devcontainers/features/java:1",
    "php":    "ghcr.io/devcontainers/features/php:1",
    "dotnet": "ghcr.io/devcontainers/features/dotnet:1",
}

L1_EXTRA_FEATURE_MAP = {
    "chromium": "ghcr.io/devcontainers/features/desktop-lite:1",
    "firefox":  "ghcr.io/devcontainers/features/desktop-lite:1",
    "webkit":   "ghcr.io/devcontainers/features/desktop-lite:1",
    "graphics-libs": "ghcr.io/devcontainers/features/desktop-lite:1",
    "dev-tools": "ghcr.io/devcontainers/features/common-utils:2",
}

VERSION_FEATURE_MAP = {
    "node":   "ghcr.io/devcontainers/features/node:1",
    "python": "ghcr.io/devcontainers/features/python:1",
}

FIREWALL_NAME_PATTERNS = (
    re.compile(r"init-firewall.*"),
    re.compile(r"firewall.*\.sh$"),
    re.compile(r"setup-network.*"),
    re.compile(r"init-network.*"),
)

NETWORK_CAPS = {"NET_ADMIN", "NET_RAW"}

ALLOWLIST_DOMAIN_RE = re.compile(r'"([a-z0-9][a-z0-9.-]+\.[a-z]{2,})"')


def _read_baked_allowlist(repo_root: Path) -> set[str]:
    path = repo_root / "layer1-ai-depends" / "init-firewall.sh"
    if not path.is_file():
        return set()
    text = path.read_text()
    return set(ALLOWLIST_DOMAIN_RE.findall(text))


def _is_firewall_script(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return any(p.fullmatch(base) or p.match(base) for p in FIREWALL_NAME_PATTERNS)


def _major_prefix(version: str) -> str:
    if not version:
        return ""
    return str(version).split(".", 1)[0]


def _version_compatible(baked: str, requested: str) -> bool:
    if not requested:
        return True
    return baked.startswith(requested) or _major_prefix(baked) == _major_prefix(requested)


def _compose_features(
    agg: dict, l1_extras: list[str]
) -> tuple[dict, dict, list[str]]:
    languages = set(agg.get("languages") or [])
    extras_needed = languages - L1_LATEST_RUNTIMES

    features: dict[str, dict] = {}
    unmapped: list[str] = []

    for lang in sorted(extras_needed):
        feature = DEVCONTAINER_FEATURE_MAP.get(lang)
        if feature:
            features[feature] = {}
        else:
            unmapped.append(lang)

    version_overlays: dict[str, str] = {}
    for lang, ver in (agg.get("runtime_versions") or {}).items():
        if lang not in L1_LATEST_VERSIONS or not ver:
            continue
        if _version_compatible(L1_LATEST_VERSIONS[lang], ver):
            continue
        version_overlays[lang] = ver
        feature = VERSION_FEATURE_MAP.get(lang)
        if feature:
            features.setdefault(feature, {})["version"] = ver

    for cap in l1_extras or []:
        feature = L1_EXTRA_FEATURE_MAP.get(cap)
        if feature:
            features.setdefault(feature, {})
        else:
            unmapped.append(cap)

    return features, version_overlays, unmapped


def _compose_firewall(agg: dict, repo_root: Path) -> dict:
    container = agg.get("container") or {}
    capabilities = set(container.get("capabilities") or [])

    cap_add = bool(capabilities & NETWORK_CAPS)

    init_scripts = container.get("init_scripts") or []
    chain = container.get("post_start_chain") or []
    chain_scripts = [step.get("script", "") for step in chain if isinstance(step, dict)]

    for name in list(init_scripts) + chain_scripts:
        if name and _is_firewall_script(name):
            cap_add = True
            break

    requested = set((agg.get("external_services") or {}).get("domains") or [])
    baked = _read_baked_allowlist(repo_root)
    if baked:
        extra_domains = sorted(requested - baked)
    else:
        extra_domains = sorted(requested)

    return {"cap_add": cap_add, "extra_domains": extra_domains}


def _compose_credentials(agg: dict, build_json: dict) -> dict:
    creds = agg.get("credentials_required") or {}
    overrides = (build_json.get("overrides") or {}).get("credentials_delivery") or {}

    all_names: list[str] = []
    for bucket in ("api_keys", "tokens", "other"):
        all_names.extend(creds.get(bucket) or [])

    env_passthrough: list[str] = []
    mounts: list[dict] = []

    for name in sorted(set(all_names)):
        delivery = overrides.get(name, "containerEnv")
        if delivery == "mount":
            mounts.append({
                "source": f"/run/host-credentials/{name}",
                "target": f"/run/credentials/{name}",
                "readonly": True,
            })
        else:
            env_passthrough.append(name)

    if creds.get("ssh"):
        if "SSH_AUTH_SOCK" not in env_passthrough:
            env_passthrough.append("SSH_AUTH_SOCK")

    return {"env_passthrough": env_passthrough, "mounts": mounts}


_PARTIAL_ORDER_EDGES = (
    ("init-firewall.sh", "init-ssh.sh"),
    ("init-firewall.sh", "init-gh-token.sh"),
    ("init-firewall.sh", "init-github-mcp.sh"),
    ("init-firewall.sh", "load-projects.sh"),
    ("init-ssh.sh", "init-gh-token.sh"),
    ("init-gh-token.sh", "init-github-mcp.sh"),
    ("init-ssh.sh", "load-projects.sh"),
    ("init-gh-token.sh", "load-projects.sh"),
    ("init-github-mcp.sh", "load-projects.sh"),
)


def _basename(name: str) -> str:
    if not name:
        return ""
    return name.rsplit("/", 1)[-1]


def _partial_order_rank(basename: str) -> int:
    if basename == "init-firewall.sh" or _is_firewall_script(basename):
        return 0
    if basename == "init-ssh.sh":
        return 1
    if basename == "init-gh-token.sh":
        return 2
    if basename == "init-github-mcp.sh":
        return 3
    if basename == "load-projects.sh":
        return 99
    return 50


def _compose_init_chain(agg: dict) -> tuple[list[str], list[str]]:
    chain = (agg.get("container") or {}).get("post_start_chain") or []

    steps: list[dict] = [s for s in chain if isinstance(s, dict)]
    if not steps:
        return [], []

    by_basename: dict[str, dict] = {}
    original_order: list[str] = []
    duplicates: list[str] = []

    for step in steps:
        base = _basename(step.get("script", "") or step.get("raw", ""))
        if not base:
            base = step.get("raw", "") or ""
        if base in by_basename:
            existing = by_basename[base]
            if existing.get("raw") != step.get("raw"):
                duplicates.append(
                    f"duplicate script {base!r} with differing raw commands: "
                    f"{existing.get('raw')!r} vs {step.get('raw')!r}"
                )
            continue
        by_basename[base] = step
        original_order.append(base)

    edges: dict[str, set[str]] = {b: set() for b in original_order}
    for a, b in _PARTIAL_ORDER_EDGES:
        if a in by_basename and b in by_basename:
            edges[a].add(b)

    indegree: dict[str, int] = {b: 0 for b in original_order}
    for src, targets in edges.items():
        for t in targets:
            indegree[t] = indegree.get(t, 0) + 1

    pos = {b: i for i, b in enumerate(original_order)}

    def _key(b: str) -> tuple[int, int, str]:
        return (_partial_order_rank(b), pos.get(b, len(pos)), b)

    ready = sorted([b for b, d in indegree.items() if d == 0], key=_key)
    ordered: list[str] = []

    while ready:
        nxt = ready.pop(0)
        ordered.append(nxt)
        for t in sorted(edges.get(nxt, ()), key=_key):
            indegree[t] -= 1
            if indegree[t] == 0:
                ready.append(t)
        ready.sort(key=_key)

    conflicts = list(duplicates)
    if len(ordered) != len(original_order):
        unresolved = [b for b in original_order if b not in ordered]
        conflicts.append(
            "cycle detected in init chain partial order; "
            f"unresolved scripts: {sorted(unresolved)} — falling back to partial-order default"
        )
        ordered = ordered + sorted(unresolved, key=_key)

    raw_chain = [by_basename[b].get("raw", "") for b in ordered if b in by_basename]
    raw_chain = [r for r in raw_chain if r]

    return raw_chain, conflicts


def compose_l4(
    agg: dict,
    l1_variant: str,
    l1_extras: list[str],
    build_json: dict,
    repo_root: Path,
) -> dict:
    features, version_overlays, unmapped = _compose_features(agg, l1_extras or [])
    firewall = _compose_firewall(agg, repo_root)
    credentials = _compose_credentials(agg, build_json)
    init_chain, init_chain_conflicts = _compose_init_chain(agg)

    result: dict = {
        "features": features,
        "version_overlays": version_overlays,
        "firewall": firewall,
        "credentials": credentials,
        "init_chain": init_chain,
        "init_chain_conflicts": init_chain_conflicts,
    }
    if unmapped:
        result["features_unmapped"] = sorted(set(unmapped))
    return result


def compose_l4_features(aggregated: dict, l1_variant: str) -> dict:
    features, version_overlays, unmapped = _compose_features(aggregated, [])
    return {
        "features": features,
        "version_overlays": version_overlays,
        "features_unmapped": unmapped,
    }


def derive_firewall_required(aggregated: dict) -> bool:
    container = aggregated.get("container") or {}
    if set(container.get("capabilities") or []) & NETWORK_CAPS:
        return True
    init_scripts = container.get("init_scripts") or []
    chain = container.get("post_start_chain") or []
    chain_scripts = [s.get("script", "") for s in chain if isinstance(s, dict)]
    for name in list(init_scripts) + chain_scripts:
        if name and _is_firewall_script(name):
            return True
    return False


def assemble_init_chain(aggregated: dict) -> list:
    chain, _ = _compose_init_chain(aggregated)
    return chain
