"""Unit tests for build_stack.compose — Phase 5b L4 overlay composition.

Covers: feature/version-overlay synthesis, firewall detection (capabilities +
script-name patterns), credentials delivery dispatch (containerEnv vs mount,
implicit SSH_AUTH_SOCK), init-chain topological sort under partial order with
deterministic tiebreakers, and the public re-export surface
(``compose_l4``, ``compose_l4_features``, ``derive_firewall_required``,
``assemble_init_chain``).

Pure-function module: tests use inline literal ``agg`` dicts. ``tmp_path`` is
used only for the baked-allowlist read in ``_compose_firewall``
(reads ``layer1-ai-depends/init-firewall.sh`` from the repo_root arg).
"""

from __future__ import annotations

from pathlib import Path

from build_stack.compose import (
    DEVCONTAINER_FEATURE_MAP,
    INIT_SCRIPT_CREDENTIAL_MAP,
    L1_LATEST_RUNTIMES,
    NETWORK_CAPS,
    VERSION_FEATURE_MAP,
    _basename,
    _compose_credentials,
    _compose_features,
    _compose_firewall,
    _compose_init_chain,
    _detect_redundant_passthrough,
    _is_firewall_script,
    _major_prefix,
    _partial_order_rank,
    _version_compatible,
    assemble_init_chain,
    compose_l4,
    compose_l4_features,
    derive_firewall_required,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _write_baked_firewall(repo_root: Path, domains: list[str]) -> None:
    """Create layer1-ai-depends/init-firewall.sh with quoted domains.

    ``_read_baked_allowlist`` extracts quoted FQDN-shaped tokens via regex,
    so each domain is written as a quoted shell argument.
    """
    layer1 = repo_root / "layer1-ai-depends"
    layer1.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f'echo "{d}"' for d in domains)
    (layer1 / "init-firewall.sh").write_text(body)


# ─── _major_prefix ────────────────────────────────────────────────────────────

def test_major_prefix_extracts_first_dotted_component():
    assert _major_prefix("3.12.4") == "3"
    assert _major_prefix("22") == "22"


def test_major_prefix_empty_returns_empty():
    assert _major_prefix("") == ""


# ─── _version_compatible ──────────────────────────────────────────────────────

def test_version_compatible_empty_requested_is_unconstrained():
    """No requested version → compatible with anything."""
    assert _version_compatible("3.12", "") is True


def test_version_compatible_exact_prefix_match():
    """`3.12.4` baked covers requested `3.12` (startswith)."""
    assert _version_compatible("3.12.4", "3.12") is True


def test_version_compatible_same_major_different_minor():
    """L1 cohabits same-major: 3.12 baked vs 3.13 requested → compatible."""
    assert _version_compatible("3.12", "3.13") is True


def test_version_compatible_cross_major_incompatible():
    """3.x baked vs 2.x requested → cross-major → incompatible (overlay needed)."""
    assert _version_compatible("3.12", "2.7") is False


def test_version_compatible_node_cross_major():
    assert _version_compatible("22", "20") is False
    assert _version_compatible("22", "22") is True


# ─── _is_firewall_script ──────────────────────────────────────────────────────

def test_is_firewall_script_canonical_name():
    assert _is_firewall_script("init-firewall.sh") is True


def test_is_firewall_script_init_firewall_variant_matches():
    """`init-firewall-strict.sh` matches the `init-firewall.*` pattern."""
    assert _is_firewall_script("init-firewall-strict.sh") is True


def test_is_firewall_script_firewall_dot_sh_pattern():
    """`firewall.*\\.sh$` matches names *starting* with `firewall` (re.match anchors start)."""
    assert _is_firewall_script("firewall.sh") is True
    assert _is_firewall_script("firewall-strict.sh") is True


def test_is_firewall_script_project_prefixed_name_rejected():
    """Pin the conservative detector: `project-firewall.sh` is NOT detected.
    The patterns are start-anchored — names with arbitrary prefixes don't match.
    This prevents false positives from project scripts that merely *mention*
    firewall in the middle of their name."""
    assert _is_firewall_script("project-firewall.sh") is False
    assert _is_firewall_script("custom-network.sh") is False


def test_is_firewall_script_init_network_pattern():
    assert _is_firewall_script("init-network-stuff") is True


def test_is_firewall_script_setup_network_pattern():
    assert _is_firewall_script("setup-network.sh") is True


def test_is_firewall_script_unrelated_names_rejected():
    assert _is_firewall_script("load-projects.sh") is False
    assert _is_firewall_script("init-ssh.sh") is False
    assert _is_firewall_script("init-gh-token.sh") is False


def test_is_firewall_script_strips_path_prefix():
    """Match operates on basename — directory prefix is irrelevant."""
    assert _is_firewall_script(".devcontainer/init-firewall.sh") is True


# ─── _basename ────────────────────────────────────────────────────────────────

def test_basename_strips_path_prefix():
    assert _basename("/abs/path/to/foo.sh") == "foo.sh"
    assert _basename("rel/foo.sh") == "foo.sh"


def test_basename_no_path_passthrough():
    assert _basename("foo.sh") == "foo.sh"


def test_basename_empty_string():
    assert _basename("") == ""


# ─── _partial_order_rank ──────────────────────────────────────────────────────

def test_partial_order_rank_known_scripts_ascending():
    """Pin the boot-order ranks: firewall(0) → ssh(1) → gh-token(2) →
    github-mcp(3) → projects(99). Unknown = 50, sandwiched in between."""
    assert _partial_order_rank("init-firewall.sh") == 0
    assert _partial_order_rank("init-ssh.sh") == 1
    assert _partial_order_rank("init-gh-token.sh") == 2
    assert _partial_order_rank("init-github-mcp.sh") == 3
    assert _partial_order_rank("load-projects.sh") == 99


def test_partial_order_rank_unknown_script_is_50():
    assert _partial_order_rank("user-custom.sh") == 50


def test_partial_order_rank_firewall_pattern_treated_as_rank_zero():
    """A non-canonical firewall name that DOES match the regex (starts with
    `firewall`) still gets rank 0 — _partial_order_rank delegates to
    _is_firewall_script for non-canonical names."""
    assert _partial_order_rank("firewall-strict.sh") == 0


def test_partial_order_rank_project_prefixed_firewall_is_unknown():
    """A name like `project-firewall.sh` doesn't match the start-anchored
    firewall regex → falls through to the unknown-script default (50)."""
    assert _partial_order_rank("project-firewall.sh") == 50


# ─── _compose_features ────────────────────────────────────────────────────────

def test_compose_features_empty_agg_yields_nothing():
    feats, overlays, unmapped = _compose_features({}, [])
    assert feats == {}
    assert overlays == {}
    assert unmapped == []


def test_compose_features_l1_baseline_languages_skip_features():
    """node, python, shell are baked into L1 → no devcontainer feature added."""
    feats, _, unmapped = _compose_features(
        {"languages": ["node", "python", "shell"]}, []
    )
    assert feats == {}
    assert unmapped == []


def test_compose_features_go_adds_devcontainer_feature():
    feats, _, unmapped = _compose_features({"languages": ["go"]}, [])
    assert DEVCONTAINER_FEATURE_MAP["go"] in feats
    assert unmapped == []


def test_compose_features_unmapped_language_reported():
    """A language with no devcontainer feature → reported in `unmapped`."""
    feats, _, unmapped = _compose_features({"languages": ["haskell"]}, [])
    assert feats == {}
    assert "haskell" in unmapped


def test_compose_features_version_match_no_overlay():
    """python 3.12 matches L1 baseline → no overlay synthesized."""
    _, overlays, _ = _compose_features(
        {"runtime_versions": {"python": "3.12"}}, []
    )
    assert overlays == {}


def test_compose_features_version_same_major_no_overlay():
    """Same major (3.12 baked vs 3.13 requested) → cohabit OK, no overlay."""
    _, overlays, _ = _compose_features(
        {"runtime_versions": {"python": "3.13"}}, []
    )
    assert overlays == {}


def test_compose_features_version_cross_major_creates_overlay():
    """Cross-major (2.7 vs 3.12) → version overlay synthesized AND feature
    config picks up the requested version."""
    feats, overlays, _ = _compose_features(
        {"runtime_versions": {"python": "2.7"}}, []
    )
    assert overlays == {"python": "2.7"}
    py_feature = VERSION_FEATURE_MAP["python"]
    assert feats[py_feature] == {"version": "2.7"}


def test_compose_features_unknown_runtime_no_overlay():
    """Runtime not in L1_LATEST_VERSIONS (e.g. ruby) → no overlay (out of scope)."""
    _, overlays, _ = _compose_features(
        {"runtime_versions": {"ruby": "3.0"}}, []
    )
    assert overlays == {}


def test_compose_features_empty_version_string_no_overlay():
    """runtime_versions with empty string → unconstrained → no overlay."""
    _, overlays, _ = _compose_features(
        {"runtime_versions": {"python": ""}}, []
    )
    assert overlays == {}


def test_compose_features_l1_extras_chromium_adds_desktop_lite():
    feats, _, _ = _compose_features({}, ["chromium"])
    assert "ghcr.io/devcontainers/features/desktop-lite:1" in feats


def test_compose_features_l1_extras_unknown_cap_reported_unmapped():
    _, _, unmapped = _compose_features({}, ["cap-i-do-not-know"])
    assert "cap-i-do-not-know" in unmapped


# ─── _compose_firewall ────────────────────────────────────────────────────────

def test_compose_firewall_net_admin_capability_triggers_cap_add(tmp_path):
    out = _compose_firewall(
        {"container": {"capabilities": ["NET_ADMIN"]}}, tmp_path,
    )
    assert out["cap_add"] is True


def test_compose_firewall_net_raw_capability_triggers_cap_add(tmp_path):
    out = _compose_firewall(
        {"container": {"capabilities": ["NET_RAW"]}}, tmp_path,
    )
    assert out["cap_add"] is True


def test_compose_firewall_unrelated_capability_no_cap_add(tmp_path):
    """SYS_PTRACE is not a network cap → no cap_add."""
    out = _compose_firewall(
        {"container": {"capabilities": ["SYS_PTRACE"]}}, tmp_path,
    )
    assert out["cap_add"] is False


def test_compose_firewall_init_scripts_firewall_triggers_cap_add(tmp_path):
    out = _compose_firewall(
        {"container": {"init_scripts": ["init-firewall.sh"]}}, tmp_path,
    )
    assert out["cap_add"] is True


def test_compose_firewall_post_start_chain_firewall_triggers_cap_add(tmp_path):
    """Firewall script in post_start_chain (not just init_scripts) flips cap_add too."""
    out = _compose_firewall(
        {"container": {"post_start_chain": [
            {"script": "init-firewall.sh", "raw": "init-firewall.sh"},
        ]}},
        tmp_path,
    )
    assert out["cap_add"] is True


def test_compose_firewall_no_signal_no_cap_add(tmp_path):
    out = _compose_firewall({"container": {}}, tmp_path)
    assert out["cap_add"] is False
    assert out["extra_domains"] == []


def test_compose_firewall_no_baked_allowlist_all_domains_extra(tmp_path):
    """No baked init-firewall.sh present → all requested domains are 'extra'."""
    out = _compose_firewall(
        {"external_services": {"domains": ["api.example.com", "cdn.example.com"]}},
        tmp_path,
    )
    assert out["extra_domains"] == ["api.example.com", "cdn.example.com"]


def test_compose_firewall_extra_domains_subtracts_baked(tmp_path):
    """Domains already in baked allowlist drop out of extra_domains."""
    _write_baked_firewall(tmp_path, ["api.example.com", "github.com"])
    out = _compose_firewall(
        {"external_services": {"domains": ["api.example.com", "new.example.com"]}},
        tmp_path,
    )
    assert out["extra_domains"] == ["new.example.com"]


def test_compose_firewall_extra_domains_returned_sorted(tmp_path):
    out = _compose_firewall(
        {"external_services": {"domains": ["zulu.example.com", "alpha.example.com"]}},
        tmp_path,
    )
    assert out["extra_domains"] == sorted(out["extra_domains"])


# ─── _compose_credentials ─────────────────────────────────────────────────────

def test_compose_credentials_empty_returns_empty_buckets():
    assert _compose_credentials({}, {}) == {"env_passthrough": [], "mounts": []}


def test_compose_credentials_api_keys_default_to_env_passthrough():
    out = _compose_credentials(
        {"credentials_required": {"api_keys": ["FOO_API_KEY"]}}, {},
    )
    assert "FOO_API_KEY" in out["env_passthrough"]
    assert out["mounts"] == []


def test_compose_credentials_dedups_across_buckets():
    """Same name appearing in api_keys + tokens → single entry in output."""
    out = _compose_credentials(
        {"credentials_required": {"api_keys": ["DUP"], "tokens": ["DUP"]}}, {},
    )
    assert out["env_passthrough"].count("DUP") == 1


def test_compose_credentials_main_set_alphabetically_sorted():
    """Pre-ssh portion of env_passthrough is sorted set order."""
    out = _compose_credentials(
        {"credentials_required": {"api_keys": ["ZULU", "ALPHA", "MIKE"]}}, {},
    )
    assert out["env_passthrough"] == ["ALPHA", "MIKE", "ZULU"]


def test_compose_credentials_override_routes_to_mount():
    """Override delivery=mount → entry goes to mounts (and out of env_passthrough)
    with the canonical /run/host-credentials/X → /run/credentials/X mapping."""
    out = _compose_credentials(
        {"credentials_required": {"api_keys": ["FOO_API_KEY"]}},
        {"overrides": {"credentials_delivery": {"FOO_API_KEY": "mount"}}},
    )
    assert out["env_passthrough"] == []
    assert out["mounts"] == [{
        "source": "/run/host-credentials/FOO_API_KEY",
        "target": "/run/credentials/FOO_API_KEY",
        "readonly": True,
    }]


def test_compose_credentials_ssh_appends_ssh_auth_sock():
    """ssh=True implicitly adds SSH_AUTH_SOCK to env_passthrough."""
    out = _compose_credentials({"credentials_required": {"ssh": True}}, {})
    assert "SSH_AUTH_SOCK" in out["env_passthrough"]


def test_compose_credentials_ssh_does_not_double_add_ssh_auth_sock():
    """If SSH_AUTH_SOCK already listed (e.g. user added explicitly), the
    ssh-driven append is idempotent — appears exactly once."""
    out = _compose_credentials(
        {"credentials_required": {"api_keys": ["SSH_AUTH_SOCK"], "ssh": True}}, {},
    )
    assert out["env_passthrough"].count("SSH_AUTH_SOCK") == 1


def test_compose_credentials_ssh_appended_after_sorted_block():
    """Ordering contract: alpha-sorted secrets first, then SSH_AUTH_SOCK
    appended at the end (preserves visual grouping in the rendered devcontainer)."""
    out = _compose_credentials(
        {"credentials_required": {"api_keys": ["ZULU", "ALPHA"], "ssh": True}}, {},
    )
    assert out["env_passthrough"] == ["ALPHA", "ZULU", "SSH_AUTH_SOCK"]


# ─── _compose_init_chain ──────────────────────────────────────────────────────

def test_compose_init_chain_empty_yields_empty():
    assert _compose_init_chain({}) == ([], [])


def test_compose_init_chain_single_step_passthrough():
    chain, conflicts = _compose_init_chain({"container": {"post_start_chain": [
        {"script": "init-ssh.sh", "raw": "bash init-ssh.sh"},
    ]}})
    assert chain == ["bash init-ssh.sh"]
    assert conflicts == []


def test_compose_init_chain_canonical_partial_order():
    """Boot sequence: firewall → ssh → gh-token → github-mcp → projects.

    Provided in REVERSE order to prove the topo sort actually rearranges them.
    """
    chain, conflicts = _compose_init_chain({"container": {"post_start_chain": [
        {"script": "load-projects.sh",   "raw": "load-projects.sh"},
        {"script": "init-github-mcp.sh", "raw": "init-github-mcp.sh"},
        {"script": "init-gh-token.sh",   "raw": "init-gh-token.sh"},
        {"script": "init-ssh.sh",        "raw": "init-ssh.sh"},
        {"script": "init-firewall.sh",   "raw": "init-firewall.sh"},
    ]}})
    assert chain == [
        "init-firewall.sh",
        "init-ssh.sh",
        "init-gh-token.sh",
        "init-github-mcp.sh",
        "load-projects.sh",
    ]
    assert conflicts == []


def test_compose_init_chain_unknown_scripts_get_middle_rank():
    """Unknown scripts (rank 50) sort between firewall (0) and load-projects (99)."""
    chain, _ = _compose_init_chain({"container": {"post_start_chain": [
        {"script": "user-custom.sh",   "raw": "user-custom.sh"},
        {"script": "init-firewall.sh", "raw": "init-firewall.sh"},
        {"script": "load-projects.sh", "raw": "load-projects.sh"},
    ]}})
    assert chain == ["init-firewall.sh", "user-custom.sh", "load-projects.sh"]


def test_compose_init_chain_duplicate_same_raw_dedupes_silently():
    """Same basename + same raw command → kept once, no conflict reported."""
    chain, conflicts = _compose_init_chain({"container": {"post_start_chain": [
        {"script": "init-ssh.sh", "raw": "init-ssh.sh"},
        {"script": "init-ssh.sh", "raw": "init-ssh.sh"},
    ]}})
    assert chain == ["init-ssh.sh"]
    assert conflicts == []


def test_compose_init_chain_duplicate_different_raw_reports_conflict():
    """Same basename but different raw command → first wins, conflict reported."""
    chain, conflicts = _compose_init_chain({"container": {"post_start_chain": [
        {"script": "init-firewall.sh", "raw": "init-firewall.sh"},
        {"script": "init-firewall.sh", "raw": "sudo init-firewall.sh --strict"},
    ]}})
    assert chain == ["init-firewall.sh"]
    assert len(conflicts) == 1
    assert "init-firewall.sh" in conflicts[0]
    assert "duplicate" in conflicts[0].lower()


def test_compose_init_chain_skips_non_dict_entries():
    """Mixed input types → only dict entries participate."""
    chain, _ = _compose_init_chain({"container": {"post_start_chain": [
        "not-a-dict",
        {"script": "init-ssh.sh", "raw": "init-ssh.sh"},
        42,
    ]}})
    assert chain == ["init-ssh.sh"]


# ─── compose_l4 (public orchestrator) ─────────────────────────────────────────

def test_compose_l4_returns_all_required_keys(tmp_path):
    result = compose_l4({}, "light", [], {}, tmp_path)
    expected = {
        "features", "version_overlays", "firewall",
        "credentials", "init_chain", "init_chain_conflicts",
    }
    assert expected.issubset(result.keys())


def test_compose_l4_features_unmapped_omitted_when_empty(tmp_path):
    """Happy path: features_unmapped key is absent from the result entirely."""
    result = compose_l4({}, "light", [], {}, tmp_path)
    assert "features_unmapped" not in result


def test_compose_l4_features_unmapped_present_when_nonempty(tmp_path):
    """An unmapped language surfaces in the result keyed `features_unmapped`."""
    result = compose_l4({"languages": ["haskell"]}, "light", [], {}, tmp_path)
    assert result.get("features_unmapped") == ["haskell"]


def test_compose_l4_features_unmapped_dedups_and_sorts(tmp_path):
    """Duplicate caps in input → output unmapped is set-deduped and sorted."""
    result = compose_l4(
        {"languages": ["haskell"]},
        "light",
        ["zulu", "alpha", "alpha"],
        {},
        tmp_path,
    )
    unmapped = result.get("features_unmapped") or []
    assert unmapped == sorted(set(unmapped))


# ─── compose_l4_features (compatibility surface) ──────────────────────────────

def test_compose_l4_features_returns_three_keys():
    out = compose_l4_features({}, "light")
    assert set(out.keys()) == {"features", "version_overlays", "features_unmapped"}


def test_compose_l4_features_unmapped_always_present():
    """Unlike compose_l4, this surface always returns features_unmapped (possibly empty)."""
    out = compose_l4_features({}, "light")
    assert out["features_unmapped"] == []


# ─── derive_firewall_required ─────────────────────────────────────────────────

def test_derive_firewall_required_net_admin_capability():
    assert derive_firewall_required({"container": {"capabilities": ["NET_ADMIN"]}}) is True


def test_derive_firewall_required_init_scripts_firewall():
    assert derive_firewall_required({"container": {"init_scripts": ["init-firewall.sh"]}}) is True


def test_derive_firewall_required_post_start_chain_firewall():
    assert derive_firewall_required({"container": {"post_start_chain": [
        {"script": "init-firewall.sh", "raw": "init-firewall.sh"},
    ]}}) is True


def test_derive_firewall_required_unrelated_returns_false():
    assert derive_firewall_required({"container": {"init_scripts": ["init-ssh.sh"]}}) is False


def test_derive_firewall_required_empty_returns_false():
    assert derive_firewall_required({}) is False


# ─── assemble_init_chain (public re-export) ───────────────────────────────────

def test_assemble_init_chain_drops_conflicts_returns_only_chain():
    """Public surface returns just the ordered chain — conflicts are not exposed."""
    chain = assemble_init_chain({"container": {"post_start_chain": [
        {"script": "init-firewall.sh", "raw": "init-firewall.sh"},
        {"script": "init-firewall.sh", "raw": "sudo init-firewall.sh"},
    ]}})
    assert chain == ["init-firewall.sh"]


def test_assemble_init_chain_canonical_order():
    chain = assemble_init_chain({"container": {"post_start_chain": [
        {"script": "init-ssh.sh",      "raw": "init-ssh.sh"},
        {"script": "init-firewall.sh", "raw": "init-firewall.sh"},
    ]}})
    assert chain == ["init-firewall.sh", "init-ssh.sh"]


# ─── module-level constants are stable contracts ──────────────────────────────

def test_l1_latest_runtimes_baseline_set():
    """Pin the L1 baseline languages — extras_needed (= languages - baseline)
    in _compose_features depends on this set being exactly these three."""
    assert L1_LATEST_RUNTIMES == {"node", "python", "shell"}


def test_network_caps_constant():
    """The 'firewall-required' detector only checks these two caps."""
    assert NETWORK_CAPS == {"NET_ADMIN", "NET_RAW"}


# ─── F8 v1: redundant-passthrough detection ──────────────────────────────────

def test_init_script_credential_map_contains_gh_token():
    """Pin the canonical entry: init-gh-token.sh handles the GitHub token family.
    The three names cover what `gh`/`git`/octokit-style libs read at runtime."""
    assert INIT_SCRIPT_CREDENTIAL_MAP["init-gh-token.sh"] == (
        "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN",
    )


def test_init_script_credential_map_contains_ssh():
    """init-ssh.sh sets up the internal-agent socket → handles SSH_AUTH_SOCK."""
    assert INIT_SCRIPT_CREDENTIAL_MAP["init-ssh.sh"] == ("SSH_AUTH_SOCK",)


def test_init_script_credential_map_size_pinned():
    """Catalog starts at 2 entries. Bumping this number requires a corresponding
    test for the new entry's contract — forces us to think about each addition."""
    assert len(INIT_SCRIPT_CREDENTIAL_MAP) == 2


def test_detect_redundant_empty_agg_empty_passthrough():
    assert _detect_redundant_passthrough({}, []) == []


def test_detect_redundant_empty_passthrough_no_overlap():
    """Detection helper returns the *intersection* with env_passthrough.
    No env_passthrough → no possible intersection."""
    agg = {"container": {"post_start_chain": [
        {"script": "/workspace/.devcontainer/scripts/init-gh-token.sh"},
    ]}}
    assert _detect_redundant_passthrough(agg, []) == []


def test_detect_redundant_no_known_scripts_no_detection():
    """Chain has scripts but none are in the catalog → nothing to detect."""
    agg = {"container": {"post_start_chain": [
        {"script": "user-custom.sh"},
        {"script": "init-firewall.sh"},
    ]}}
    assert _detect_redundant_passthrough(agg, ["GITHUB_TOKEN"]) == []


def test_detect_redundant_gh_token_in_chain_dict_form():
    """Builder-project shape: post_start_chain entries are dicts with a
    `script` key carrying the full path. Basename match against catalog
    catches init-gh-token.sh → marks GITHUB_TOKEN as already-handled."""
    agg = {"container": {"post_start_chain": [
        {"script": "/workspace/.devcontainer/scripts/init-gh-token.sh"},
    ]}}
    assert _detect_redundant_passthrough(agg, ["GITHUB_TOKEN"]) == ["GITHUB_TOKEN"]


def test_detect_redundant_ssh_in_chain_dict_form():
    """init-ssh.sh in chain → SSH_AUTH_SOCK is already-handled."""
    agg = {"container": {"post_start_chain": [
        {"script": "/workspace/.devcontainer/scripts/init-ssh.sh"},
    ]}}
    assert _detect_redundant_passthrough(agg, ["SSH_AUTH_SOCK"]) == ["SSH_AUTH_SOCK"]


def test_detect_redundant_only_returns_overlap_with_passthrough():
    """A chain that handles GITHUB_TOKEN but env_passthrough only has FOO_API_KEY
    → no overlap → empty result. The detection is intersection-based, not union."""
    agg = {"container": {"post_start_chain": [
        {"script": "init-gh-token.sh"},
    ]}}
    assert _detect_redundant_passthrough(agg, ["FOO_API_KEY"]) == []


def test_detect_redundant_returns_sorted():
    """Multiple overlapping names returned alphabetically — deterministic
    ordering for warning output and for test assertions downstream."""
    agg = {"container": {"post_start_chain": [
        {"script": "init-ssh.sh"},
        {"script": "init-gh-token.sh"},
    ]}}
    out = _detect_redundant_passthrough(
        agg, ["SSH_AUTH_SOCK", "GITHUB_TOKEN"],
    )
    assert out == ["GITHUB_TOKEN", "SSH_AUTH_SOCK"]


def test_detect_redundant_falls_back_to_post_start_text():
    """When post_start_chain is missing/empty, split agg.container.post_start
    on '&&' as a fallback. Some older analyses may have only the text form."""
    agg = {"container": {"post_start": (
        "sudo /usr/local/bin/init-firewall.sh && "
        "/workspace/.devcontainer/scripts/init-gh-token.sh"
    )}}
    assert _detect_redundant_passthrough(agg, ["GITHUB_TOKEN"]) == ["GITHUB_TOKEN"]


def test_detect_redundant_chain_empty_post_start_empty_returns_empty():
    """Both signals absent → nothing to detect, even with env_passthrough set."""
    agg = {"container": {}}
    assert _detect_redundant_passthrough(agg, ["GITHUB_TOKEN"]) == []


def test_detect_redundant_handles_args_after_script():
    """Post_start text steps may carry arguments (e.g. `load-projects.sh -live X`).
    The first whitespace-split token is the script; basename must still match."""
    agg = {"container": {"post_start": (
        "/workspace/.devcontainer/scripts/init-gh-token.sh --strict"
    )}}
    assert _detect_redundant_passthrough(agg, ["GITHUB_TOKEN"]) == ["GITHUB_TOKEN"]


def test_detect_redundant_dedup_when_script_handles_multiple_creds():
    """init-gh-token.sh handles 3 names. If env_passthrough has all 3,
    all 3 are returned — and exactly once each (set-intersection semantics)."""
    agg = {"container": {"post_start_chain": [
        {"script": "init-gh-token.sh"},
    ]}}
    out = _detect_redundant_passthrough(
        agg, ["GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN"],
    )
    assert out == ["GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN"]


def test_detect_redundant_skips_non_dict_chain_entries():
    """Chain may contain stray non-dict entries (parser glitches, future
    schema changes) — must not crash. Only dict entries with 'script' are read."""
    agg = {"container": {"post_start_chain": [
        "not-a-dict",
        {"script": "init-gh-token.sh"},
        42,
        {"no_script_key": True},
    ]}}
    assert _detect_redundant_passthrough(agg, ["GITHUB_TOKEN"]) == ["GITHUB_TOKEN"]


# ─── F8 v1: warning emission inside _compose_credentials ─────────────────────

_BUILDER_PROJECT_SHAPED_AGG = {
    "credentials_required": {
        "tokens": ["GITHUB_TOKEN"],
        "ssh": True,
    },
    "container": {
        "post_start_chain": [
            {"script": "/usr/local/bin/init-firewall.sh"},
            {"script": "/workspace/.devcontainer/scripts/init-ssh.sh"},
            {"script": "/workspace/.devcontainer/scripts/init-gh-token.sh"},
        ],
    },
}


def test_compose_credentials_warns_on_token_overlap(capsys):
    """v2 (2026-05-10): builder-project shape produces a token-class warning
    for GITHUB_TOKEN. SSH_AUTH_SOCK is auto-suppressed silently — see the
    asymmetric-remedy block in `_compose_credentials`."""
    _compose_credentials(_BUILDER_PROJECT_SHAPED_AGG, {})
    err = capsys.readouterr().err
    assert "GITHUB_TOKEN" in err
    assert "SSH_AUTH_SOCK" not in err


def test_compose_credentials_warning_format_pinned(capsys):
    """Warning message format is the contract — downstream tooling (CI output
    parsers, future skill UX) may match on it. Pin the substrings."""
    _compose_credentials(_BUILDER_PROJECT_SHAPED_AGG, {})
    err = capsys.readouterr().err
    assert "build-stack: warning:" in err
    assert "already delivered by an init-script" in err
    assert 'overrides.credentials_delivery.GITHUB_TOKEN="mount"' in err


def test_compose_credentials_warning_one_line_for_token_overlap(capsys):
    """v2: only the token-class overlap (GITHUB_TOKEN) warns; SSH suppressed
    silently. Exactly one warning line lets users count and grep."""
    _compose_credentials(_BUILDER_PROJECT_SHAPED_AGG, {})
    err = capsys.readouterr().err
    warning_lines = [ln for ln in err.splitlines() if "build-stack: warning:" in ln]
    assert len(warning_lines) == 1


def test_compose_credentials_no_warning_when_no_chain(capsys):
    """No init-script chain → no detection signal → no warning, even when
    env_passthrough has credentials."""
    _compose_credentials(
        {"credentials_required": {"tokens": ["GITHUB_TOKEN"], "ssh": True}}, {},
    )
    err = capsys.readouterr().err
    assert "warning" not in err


def test_compose_credentials_no_warning_when_chain_unrelated(capsys):
    """Chain has scripts but none are in the catalog → no warning."""
    _compose_credentials(
        {
            "credentials_required": {"tokens": ["GITHUB_TOKEN"]},
            "container": {"post_start_chain": [
                {"script": "init-firewall.sh"},
                {"script": "user-custom.sh"},
            ]},
        }, {},
    )
    err = capsys.readouterr().err
    assert "warning" not in err


def test_compose_credentials_v2_token_kept_in_env_passthrough_when_warned(capsys):
    """v2 parallel-delivery semantics: when a token-class credential warns,
    it STAYS in env_passthrough. The warning surfaces the duplicate delivery;
    it does not act on it. (Contrast with the SSH case below.)"""
    out = _compose_credentials(_BUILDER_PROJECT_SHAPED_AGG, {})
    err = capsys.readouterr().err
    assert "GITHUB_TOKEN" in out["env_passthrough"]
    assert "warning" in err  # token warning fired — sanity


def test_compose_credentials_v2_ssh_auto_suppressed_from_env_passthrough(capsys):
    """v2 behaviour-conflict semantics: SSH_AUTH_SOCK is REMOVED from
    env_passthrough when init-ssh.sh appears in the chain. No warning emitted
    (asymmetric vs token-class). Pins the headline v2 behaviour change."""
    out = _compose_credentials(_BUILDER_PROJECT_SHAPED_AGG, {})
    err = capsys.readouterr().err
    assert "SSH_AUTH_SOCK" not in out["env_passthrough"]
    assert "SSH_AUTH_SOCK" not in err


def test_compose_credentials_v2_ssh_kept_when_init_ssh_not_in_chain():
    """Negative case: ssh=True but no init-ssh.sh in chain → no v2 suppression
    triggers → SSH_AUTH_SOCK still appears in env_passthrough as the v1
    default. Pins that suppression is gated on init-script detection, not on
    ssh=True alone."""
    out = _compose_credentials(
        {
            "credentials_required": {"ssh": True},
            "container": {"post_start_chain": [
                {"script": "init-firewall.sh"},
            ]},
        }, {},
    )
    assert "SSH_AUTH_SOCK" in out["env_passthrough"]


def test_compose_credentials_v2_ssh_suppressed_no_other_creds(capsys):
    """Minimal SSH-only fixture: ssh=True + init-ssh.sh in chain, no tokens.
    Expected: env_passthrough is empty (SSH suppressed), no warnings, no
    mounts. Isolates the v2 SSH behaviour from the token interaction."""
    out = _compose_credentials(
        {
            "credentials_required": {"ssh": True},
            "container": {"post_start_chain": [
                {"script": "/workspace/.devcontainer/scripts/init-ssh.sh"},
            ]},
        }, {},
    )
    err = capsys.readouterr().err
    assert out["env_passthrough"] == []
    assert out["mounts"] == []
    assert "warning" not in err


def test_compose_credentials_mount_override_suppresses_warning_for_that_cred(capsys):
    """v2: with a mount override on GITHUB_TOKEN, it routes to mount instead
    of env_passthrough → not in the redundancy intersection → no token
    warning. SSH_AUTH_SOCK is already auto-suppressed by v2's asymmetric
    rule, so neither name appears in stderr. Demonstrates that the mount
    override and v2 SSH suppression compose cleanly."""
    out = _compose_credentials(
        _BUILDER_PROJECT_SHAPED_AGG,
        {"overrides": {"credentials_delivery": {"GITHUB_TOKEN": "mount"}}},
    )
    err = capsys.readouterr().err
    assert "GITHUB_TOKEN" not in err
    assert "SSH_AUTH_SOCK" not in err
    assert "GITHUB_TOKEN" not in out["env_passthrough"]
    assert "SSH_AUTH_SOCK" not in out["env_passthrough"]
    assert any(m["target"] == "/run/credentials/GITHUB_TOKEN" for m in out["mounts"])
