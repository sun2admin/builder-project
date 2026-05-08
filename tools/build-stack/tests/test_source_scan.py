"""Unit tests for build_stack.analyzers.source_scan helpers.

Covers the highest-value testable surface of the 705-LOC module:
  * _firewall_domains — quoted-domain extraction from firewall scripts
  * _scan_external_services — priority (firewall > source) + skip rules
  * _scan_py_imports / _scan_ts_imports — stdlib/builtin/local exclusion
  * _scan_source_env_vars — TS/JS narrow (KEY/TOKEN/SECRET/PAT suffix)
    vs Python/Go wide (any all-caps) routing
  * _route_source_env / _route_gha_secrets — credential bucket routing
  * _has_ssh_signal / _has_github_api — boolean detectors

Skipped: _extract_commands / _scan_ci_workflows / _scan_mcp_servers /
_scan_claude_plugins (large, complex, low ROI per test — those are
covered indirectly by the corpus parity test once it's re-enabled).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from build_stack.analyzers import source_scan as ss
from build_stack.analyzers.schema import AnalysisResult


# ─── _firewall_domains ────────────────────────────────────────────────────────

def test_firewall_domains_extracts_from_init_firewall_sh(tmp_path):
    (tmp_path / "init-firewall.sh").write_text(
        '#!/bin/bash\n'
        'ALLOWED=("api.anthropic.com" "registry.npmjs.org")\n'
    )
    out = ss._firewall_domains(tmp_path)
    assert "api.anthropic.com" in out
    assert "registry.npmjs.org" in out


def test_firewall_domains_matches_setup_network_pattern(tmp_path):
    """Filename starts-with `setup-network` (no extension required)."""
    (tmp_path / "setup-network-rules.sh").write_text('IP_ALLOW=("api.openai.com")\n')
    assert ss._firewall_domains(tmp_path) == ["api.openai.com"]


def test_firewall_domains_skips_unrelated_scripts(tmp_path):
    """A script not matching any firewall name pattern is ignored, even if it
    contains quoted domain literals."""
    (tmp_path / "deploy.sh").write_text('echo "api.anthropic.com"\n')
    assert ss._firewall_domains(tmp_path) == []


def test_firewall_domains_requires_dot_in_match(tmp_path):
    """A bare quoted token like "host" without a dot isn't a domain."""
    (tmp_path / "init-firewall.sh").write_text('echo "localhost"\n')
    out = ss._firewall_domains(tmp_path)
    assert "localhost" not in out


# ─── _scan_external_services priority ─────────────────────────────────────────

def test_scan_external_services_firewall_priority_over_source(tmp_path):
    """When firewall script is present → its domains win, source signal is skipped."""
    (tmp_path / "init-firewall.sh").write_text('A=("only-firewall.example")\n')
    (tmp_path / "app.py").write_text('requests.get("https://only-source.example/x")\n')
    domains, src = ss._scan_external_services(tmp_path)
    assert src == "init-firewall.sh"
    assert domains == ["only-firewall.example"]
    assert "only-source.example" not in domains


def test_scan_external_services_falls_back_to_source(tmp_path):
    """No firewall script → fall back to in-source HTTP-call domain extraction."""
    (tmp_path / "app.py").write_text('requests.get("https://api.openai.com/v1/x")\n')
    domains, src = ss._scan_external_services(tmp_path)
    assert src == "source_scan"
    assert "api.openai.com" in domains


def test_scan_external_services_skips_localhost(tmp_path):
    """`_ALWAYS_SKIP_DOMAIN_RE` filters localhost/127./192.168./10./0.0.0.0/::1."""
    (tmp_path / "app.py").write_text(
        'requests.get("http://localhost:8080/x")\n'
        'requests.get("http://127.0.0.1/x")\n'
        'requests.get("https://api.real.example/x")\n'
    )
    domains, _ = ss._scan_external_services(tmp_path)
    assert "localhost" not in domains
    assert not any(d.startswith("127.") for d in domains)
    assert "api.real.example" in domains


def test_scan_external_services_source_skips_comment_lines(tmp_path):
    """Lines starting with comment markers are skipped in source files."""
    (tmp_path / "app.py").write_text(
        '# old: requests.get("https://deprecated.example/x")\n'
        'requests.get("https://current.example/x")\n'
    )
    domains, _ = ss._scan_external_services(tmp_path)
    assert "current.example" in domains
    assert "deprecated.example" not in domains


def test_scan_external_services_empty_repo(tmp_path):
    domains, src = ss._scan_external_services(tmp_path)
    assert domains == []
    assert src == "source_scan"


# ─── _scan_py_imports ─────────────────────────────────────────────────────────

def test_scan_py_imports_picks_up_third_party(tmp_path):
    (tmp_path / "main.py").write_text("import requests\nfrom fastapi import APIRouter\n")
    out = ss._scan_py_imports(tmp_path)
    assert "requests" in out
    assert "fastapi" in out


def test_scan_py_imports_excludes_stdlib(tmp_path):
    """`os`, `json`, `sys` are stdlib → not in third-party imports."""
    (tmp_path / "main.py").write_text("import os\nimport json\nfrom sys import argv\n")
    out = ss._scan_py_imports(tmp_path)
    assert "os" not in out
    assert "json" not in out
    assert "sys" not in out


def test_scan_py_imports_excludes_local_modules(tmp_path):
    """A repo with subdir `mypackage/` → `import mypackage` doesn't count as third-party."""
    (tmp_path / "mypackage").mkdir()
    (tmp_path / "mypackage" / "__init__.py").write_text("")
    (tmp_path / "main.py").write_text("import mypackage\nimport requests\n")
    out = ss._scan_py_imports(tmp_path)
    assert "mypackage" not in out
    assert "requests" in out


def test_scan_py_imports_excludes_local_top_level_modules(tmp_path):
    """Top-level `utils.py` → `from utils import x` doesn't count as third-party."""
    (tmp_path / "utils.py").write_text("def helper(): pass\n")
    (tmp_path / "main.py").write_text("from utils import helper\nimport pytest\n")
    out = ss._scan_py_imports(tmp_path)
    assert "utils" not in out
    assert "pytest" in out


def test_scan_py_imports_skips_node_modules(tmp_path):
    """node_modules and .venv are skipped via _SKIP_DIRS_LITE."""
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "leaked.py").write_text("import third_party_thing\n")
    out = ss._scan_py_imports(tmp_path)
    assert "third_party_thing" not in out


def test_scan_py_imports_strips_dotted_path_to_top_level(tmp_path):
    """`from foo.bar.baz import X` → 'foo' (top-level package name)."""
    (tmp_path / "main.py").write_text("from anthropic.types import Message\n")
    out = ss._scan_py_imports(tmp_path)
    assert "anthropic" in out


# ─── _scan_ts_imports ─────────────────────────────────────────────────────────

def test_scan_ts_imports_handles_require_form(tmp_path, monkeypatch):
    """`require("pkg")` is the most reliably-matched form."""
    monkeypatch.setenv("AR_NODE_BUILTINS", '["fs","path"]')
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.js").write_text(
        'const lodash = require("lodash");\n'
        'const sdk = require("@anthropic-ai/sdk");\n'
        'const fs = require("fs");\n'
    )
    out = ss._scan_ts_imports(tmp_path)
    assert "lodash" in out
    assert "@anthropic-ai" in out  # scoped pkg's first slash-segment
    assert "fs" not in out


def test_scan_ts_imports_handles_dynamic_import(tmp_path, monkeypatch):
    """`import("pkg")` — dynamic-import form — also matches."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('const x = await import("zod");\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" in out


def test_scan_ts_imports_excludes_relative_paths(tmp_path, monkeypatch):
    """Relative paths (./x, ../y) are stripped from the result set."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.js").write_text(
        'const x = require("./local");\n'
        'const y = require("../sibling");\n'
        'const z = require("real-pkg");\n'
    )
    out = ss._scan_ts_imports(tmp_path)
    assert all(not p.startswith(".") for p in out)
    assert "real-pkg" in out


def test_scan_ts_imports_es6_named_import_form(tmp_path, monkeypatch):
    """ES6 named import: `import { z } from "zod"`. The regex's middle branch
    (`[^'"\\n]*?from\\s+['"]`) consumes ` { z } ` between `import` and `from`."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('import { z } from "zod";\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" in out


def test_scan_ts_imports_es6_default_import_form(tmp_path, monkeypatch):
    """ES6 default import: `import zod from "zod"`. Same middle branch
    consumes the bare identifier between `import` and `from`."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('import zod from "zod";\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" in out


def test_scan_ts_imports_es6_default_plus_named_form(tmp_path, monkeypatch):
    """`import React, { useState } from "react"` — combined default+named."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text(
        'import React, { useState } from "react";\n'
    )
    out = ss._scan_ts_imports(tmp_path)
    assert "react" in out


def test_scan_ts_imports_es6_namespace_import_form(tmp_path, monkeypatch):
    """`import * as z from "zod"` — namespace import (whole module as object)."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('import * as z from "zod";\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" in out


def test_scan_ts_imports_typescript_type_only_import(tmp_path, monkeypatch):
    """`import type { z } from "zod"` — TS type-only import. The `type` keyword
    sits between `import` and `from`; middle branch handles it identically to
    other identifiers/braces."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('import type { z } from "zod";\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" in out


def test_scan_ts_imports_side_effect_only_import(tmp_path, monkeypatch):
    """`import "polyfills"` — side-effect-only import (no binding). Matches
    via the regex's third branch `['"]` after `import\\s*`."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('import "polyfills";\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "polyfills" in out


def test_scan_ts_imports_multiline_import_NOT_matched(tmp_path, monkeypatch):
    """KNOWN COVERAGE GAP: multi-line import statements where the brace block
    crosses a newline are NOT matched. The middle branch's character class
    `[^'"\\n]*?` excludes newlines deliberately — extending it to span lines
    would require tracking matched braces or risk over-eager capture across
    unrelated `from` strings. Pinning this as a contract — if a future PR
    fixes the multi-line case, this test will fail and the dev can decide
    whether to flip it (positive assertion) or keep tracking the gap.

    Mitigations available today: `prettier --print-width 200` collapses most
    multi-line imports into one line; npm projects with consistent formatting
    rarely emit truly multi-line imports outside very wide named-import lists."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text(
        "import {\n"
        "  z,\n"
        "  ZodSchema,\n"
        '} from "zod";\n'
    )
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" not in out


def test_scan_ts_imports_export_from_NOT_matched(tmp_path, monkeypatch):
    """KNOWN COVERAGE GAP: `export { z } from "zod"` (re-export) is NOT
    matched — the regex requires `import` or `require` as anchor. Re-exports
    are semantically also imports (the module IS loaded), but in practice
    they're used as relays and the actual user import lives elsewhere in the
    project, so the missing detection rarely loses signal. Pinned for tracking."""
    monkeypatch.setenv("AR_NODE_BUILTINS", "[]")
    monkeypatch.setattr(ss, "_NODE_BUILTINS_CACHE", None)
    (tmp_path / "app.ts").write_text('export { z } from "zod";\n')
    out = ss._scan_ts_imports(tmp_path)
    assert "zod" not in out


# ─── _scan_source_env_vars ────────────────────────────────────────────────────

def test_scan_source_env_vars_python_any_all_caps_name(tmp_path):
    """Python: os.environ.get("ANY_NAME") captures bare names — no suffix filter."""
    (tmp_path / "app.py").write_text(
        'import os\n'
        'x = os.environ.get("DEBUG_MODE")\n'
        'y = os.environ["DATABASE_URL"]\n'
    )
    out = ss._scan_source_env_vars(tmp_path)
    assert "DEBUG_MODE" in out
    assert "DATABASE_URL" in out


def test_scan_source_env_vars_typescript_only_with_credential_suffix(tmp_path):
    """TS/JS: process.env.X only matches when X ends with KEY/TOKEN/SECRET/PAT.
    Generic `process.env.DEBUG` is intentionally NOT captured."""
    (tmp_path / "app.ts").write_text(
        'const k = process.env.ANTHROPIC_API_KEY;\n'
        'const t = process.env.GITHUB_TOKEN;\n'
        'const d = process.env.DEBUG;\n'
    )
    out = ss._scan_source_env_vars(tmp_path)
    assert "ANTHROPIC_API_KEY" in out
    assert "GITHUB_TOKEN" in out
    assert "DEBUG" not in out


def test_scan_source_env_vars_go(tmp_path):
    (tmp_path / "main.go").write_text(
        'package main\n'
        'import "os"\n'
        'func main() { _ = os.Getenv("API_HOST") }\n'
    )
    out = ss._scan_source_env_vars(tmp_path)
    assert "API_HOST" in out


def test_scan_source_env_vars_skips_node_modules(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "leaked.js").write_text(
        'process.env.LEAKED_API_KEY;\n'
    )
    out = ss._scan_source_env_vars(tmp_path)
    assert "LEAKED_API_KEY" not in out


# ─── _route_source_env ────────────────────────────────────────────────────────

def test_route_source_env_only_strict_suffixes():
    """Source-env routing is STRICTER than env.example routing — only `_KEY$`
    and `_TOKEN$` are recognized. `_SECRET$` and `_PAT$` are NOT routed here
    (intentional asymmetry vs dockerfile.py)."""
    r = AnalysisResult()
    ss._route_source_env({"X_API_KEY", "Y_TOKEN", "Z_SECRET", "W_PAT"}, r)
    assert "X_API_KEY" in r.credentials_required.api_keys
    assert "Y_TOKEN" in r.credentials_required.tokens
    # Strict: SECRET/PAT not routed in source-env path
    assert "Z_SECRET" not in r.credentials_required.api_keys
    assert "W_PAT" not in r.credentials_required.tokens


def test_route_source_env_unrecognized_dropped():
    r = AnalysisResult()
    ss._route_source_env({"DEBUG", "PORT", "HOST"}, r)
    assert r.credentials_required.api_keys == []
    assert r.credentials_required.tokens == []


# ─── _route_gha_secrets ───────────────────────────────────────────────────────

def test_route_gha_secrets_key_to_api_keys():
    r = AnalysisResult()
    ss._route_gha_secrets({"ANTHROPIC_API_KEY"}, r)
    assert "ANTHROPIC_API_KEY" in r.credentials_required.api_keys


def test_route_gha_secrets_token_to_tokens():
    r = AnalysisResult()
    ss._route_gha_secrets({"NPM_TOKEN"}, r)
    assert "NPM_TOKEN" in r.credentials_required.tokens


def test_route_gha_secrets_github_token_special_case():
    """`GITHUB_TOKEN` is the GHA-provided default token — pinned in tokens
    bucket even though its name doesn't end in _TOKEN by suffix-only logic
    (it does, but the special-case branch documents the intent)."""
    r = AnalysisResult()
    ss._route_gha_secrets({"GITHUB_TOKEN"}, r)
    assert "GITHUB_TOKEN" in r.credentials_required.tokens


def test_route_gha_secrets_unmatched_routed_to_other():
    """GHA secrets routing is exhaustive: anything not matching key/token
    falls into `other`. (Source env routing drops these instead — pin
    the asymmetry.)"""
    r = AnalysisResult()
    ss._route_gha_secrets({"DEPLOY_HOST", "RANDOM_THING"}, r)
    assert set(r.credentials_required.other) == {"DEPLOY_HOST", "RANDOM_THING"}


def test_route_gha_secrets_routing_exclusive():
    """Each secret name lands in exactly one bucket."""
    r = AnalysisResult()
    ss._route_gha_secrets({"FOO_KEY", "BAR_TOKEN", "BAZ_HOST"}, r)
    assert "FOO_KEY" not in r.credentials_required.tokens
    assert "FOO_KEY" not in r.credentials_required.other
    assert "BAR_TOKEN" not in r.credentials_required.api_keys


# ─── _has_ssh_signal ──────────────────────────────────────────────────────────

def test_has_ssh_signal_detects_ssh_keyword(tmp_path):
    (tmp_path / "deploy.sh").write_text("ssh user@host 'echo'\n")
    assert ss._has_ssh_signal(tmp_path) is True


def test_has_ssh_signal_detects_ssh_auth_sock(tmp_path):
    """Container-side env-passthrough hint."""
    (tmp_path / "config.yaml").write_text("env: SSH_AUTH_SOCK\n")
    assert ss._has_ssh_signal(tmp_path) is True


def test_has_ssh_signal_negative_case(tmp_path):
    (tmp_path / "deploy.sh").write_text("rsync -av src/ dst/\n")
    assert ss._has_ssh_signal(tmp_path) is False


def test_has_ssh_signal_skips_unscanned_extensions(tmp_path):
    """`.md` is NOT in `_SSH_SCAN_SUFFIXES` — README mentions of ssh don't count."""
    (tmp_path / "README.md").write_text("Use ssh to connect.\n")
    assert ss._has_ssh_signal(tmp_path) is False


# ─── _has_github_api ──────────────────────────────────────────────────────────

def test_has_github_api_detects_octokit(tmp_path):
    (tmp_path / "app.ts").write_text('import { Octokit } from "@octokit/rest";\n')
    assert ss._has_github_api(tmp_path) is True


def test_has_github_api_detects_pygithub(tmp_path):
    (tmp_path / "deploy.py").write_text('from github import Github  # PyGithub\n')
    assert ss._has_github_api(tmp_path) is True


def test_has_github_api_detects_gh_api_call(tmp_path):
    """`gh api repos/X/Y` in shell scripts."""
    (tmp_path / "deploy.sh").write_text('gh api repos/x/y --jq .name\n')
    assert ss._has_github_api(tmp_path) is True


def test_has_github_api_negative_case(tmp_path):
    (tmp_path / "app.py").write_text('print("hello")\n')
    assert ss._has_github_api(tmp_path) is False


def test_has_github_api_skips_node_modules(tmp_path):
    """SKIP_DIRS_LITE applies — third-party deps don't trigger the signal."""
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.ts").write_text('import "@octokit/rest";\n')
    assert ss._has_github_api(tmp_path) is False
