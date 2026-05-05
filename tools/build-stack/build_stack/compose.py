"""Phase 5b — L4 overlay composition, firewall, init script chain.

Computes:
- `extras_needed` (languages not in L1 floor → devcontainer features)
- `version_overlays` (baked-in lang at wrong version → side-by-side feature)
- `firewall_required` (derived from capabilities + script presence)
- final init script chain via topological sort

See plan §5, §7, §8.
"""

from __future__ import annotations


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


def compose_l4_features(aggregated: dict, l1_variant: str) -> dict:
    """Derive `extras_needed` and `version_overlays` from aggregated analysis."""
    raise NotImplementedError("compose.compose_l4_features is a stub.")


def derive_firewall_required(aggregated: dict) -> bool:
    """True iff aggregated capabilities include NET_ADMIN/NET_RAW or any init
    script touches iptables.
    """
    raise NotImplementedError("compose.derive_firewall_required is a stub.")


def assemble_init_chain(aggregated: dict) -> list:
    """Topologically sort union of per-repo init script chains under partial order.

    See plan §8 ordering algorithm.
    """
    raise NotImplementedError("compose.assemble_init_chain is a stub.")
