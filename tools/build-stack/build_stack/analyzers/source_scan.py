"""Source-tree inference: tool calls + imports + external services + creds.

Populates these schema fields:
    inferred.tools / tools_new / tools_confirmed
    inferred.py_imports / py_imports_new / py_imports_confirmed
    inferred.ts_imports / ts_imports_new / ts_imports_confirmed
    inferred.ci_tools
    external_services.{domains, source}
    env_vars (additions only — does not replace dockerfile.detect output)
    github_api_usage
    claude_plugins
    mcp_servers
    credentials_required.{api_keys, tokens, ssh, other}
        — source-code env reads + GitHub Actions secrets only;
          the env-var-routed (.env.example) and volume-routed signals
          live in dockerfile.py.

Source files scanned (per analyze-repo.sh lines 696-979 + 1019-1242):
    Firewall init scripts                  → external_services
    Source tree                            → URL scan, import scan, command scan
    Markdown / docs                        → README codefences + service-keyword prose
    Config / env files (yml/json/toml/ini) → external_services (high confidence)
    .github/workflows/*.yml                → ci_tools, secrets routing
    .mcp.json / .claude/mcp.json / settings.json / package.json deps → mcp_servers
    .claude-plugin/marketplace.json        → claude_plugins
    Shell + Makefile + Taskfile + justfile → inferred.tools
    *.py / *.ts / *.js                     → py_imports / ts_imports

Dedup against `result.libraries.{python,node}` and `result.system_packages`
to populate the `_new` / `_confirmed` siblings — assumes manifests.detect()
and dockerfile.detect() have already run.

Mirrors detection rules from analyze-repo.sh; the bash skill's inline
Python is adapted directly here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .schema import AnalysisResult


# ─── shared regex / constants ─────────────────────────────────────────────────

_SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "__pycache__", "gen", "generated"}
_SKIP_DIRS_LITE = {".git", "node_modules", "vendor", ".venv", "__pycache__"}
_SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "Gemfile.lock", "composer.lock",
}

_DOMAIN_RE = re.compile(r"https?://([a-z0-9][a-z0-9.-]+\.[a-z]{2,})", re.IGNORECASE)
_BADGE_RE = re.compile(r"\[!\[")
_COMMENT_RE = re.compile(r"^\s*(?://|#|\*|<!--)")
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.DOTALL)
_ALWAYS_SKIP_DOMAIN_RE = re.compile(r"^(?:localhost|127\.|192\.168\.|10\.|0\.0\.0\.0|::1)")

_SERVICE_KW = {
    "api", "service", "endpoint", "webhook", "connect", "host",
    "server", "baseurl", "base_url", "origin", "remote", "backend",
}
_HTTP_CALL_RE = re.compile(
    r"(?:fetch|axios\s*\.\s*(?:get|post|put|delete|patch|request)"
    r"|requests\s*\.\s*(?:get|post|put|delete|patch|head)"
    r"|urllib(?:\.request)?\s*\.\s*(?:urlopen|Request)"
    r"|http(?:s)?\.(?:Get|Post|Do|NewRequest)"
    r"|grpc\.(?:Dial|NewClient)"
    r"|curl\b|wget\b"
    r")\s*[\s(\'\"]",
    re.IGNORECASE,
)


def _iter_repo_files(repo_path: Path):
    """Yield all files under `repo_path`, skipping noisy dirs."""
    for f in repo_path.rglob("*"):
        if not f.is_file():
            continue
        if any(d in _SKIP_DIRS for d in f.relative_to(repo_path).parts):
            continue
        yield f


def _read_text(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""


# ─── external services ────────────────────────────────────────────────────────

_FIREWALL_NAME_RE = re.compile(r"^(init-firewall|firewall.*\.sh|setup-network.*\.sh|init-network.*\.sh)$")
_QUOTED_DOMAIN_RE = re.compile(r"\"([a-z0-9][a-z0-9.-]+\.[a-z]{2,})\"")


def _firewall_domains(repo_path: Path) -> list[str]:
    """Priority 1: scan firewall scripts for double-quoted domain literals."""
    domains: list[str] = []
    for f in _iter_repo_files(repo_path):
        name = f.name
        if not (
            name.startswith("init-firewall")
            or (name.startswith("firewall") and name.endswith(".sh"))
            or name.startswith("setup-network")
            or name.startswith("init-network")
        ):
            continue
        text = _read_text(f)
        for m in _QUOTED_DOMAIN_RE.finditer(text):
            d = m.group(1)
            if "." in d:
                domains.append(d)
    return domains


def _scan_external_services(repo_path: Path) -> tuple[list[str], str]:
    """Return (sorted-unique-domains, source-tag).

    Priority: firewall_script > source_scan.
    """
    fw = _firewall_domains(repo_path)
    if fw:
        return sorted(set(fw)), "init-firewall.sh"

    domains_high: set[str] = set()
    domains_medium: set[str] = set()

    for f in _iter_repo_files(repo_path):
        if f.name in _SKIP_FILES or f.suffix == ".svg":
            continue
        content = _read_text(f)
        if not content:
            continue

        suffix = f.suffix
        # ── Markdown / docs: owner-stated baseline ─────────────────────────
        if suffix in {".md", ".rst", ".txt", ".adoc"}:
            for block in _CODE_FENCE_RE.findall(content):
                for m in _DOMAIN_RE.finditer(block):
                    d = m.group(1).lower()
                    if not _ALWAYS_SKIP_DOMAIN_RE.match(d):
                        domains_medium.add(d)
            prose = _CODE_FENCE_RE.sub("", content)
            for line in prose.splitlines():
                if _BADGE_RE.search(line):
                    continue
                low = line.lower()
                if any(kw in low for kw in _SERVICE_KW):
                    for m in _DOMAIN_RE.finditer(line):
                        d = m.group(1).lower()
                        if not _ALWAYS_SKIP_DOMAIN_RE.match(d):
                            domains_medium.add(d)
            continue

        # ── Source code: only HTTP-call lines, skip comments ───────────────
        if suffix in {".py", ".ts", ".js", ".go", ".rs", ".sh", ".bash"}:
            for line in content.splitlines():
                if _COMMENT_RE.match(line):
                    continue
                if _HTTP_CALL_RE.search(line):
                    for m in _DOMAIN_RE.finditer(line):
                        d = m.group(1).lower()
                        if not _ALWAYS_SKIP_DOMAIN_RE.match(d):
                            domains_high.add(d)
            continue

        # ── Config / env files: any URL is runtime config ──────────────────
        if (
            suffix in {".yml", ".yaml", ".toml", ".cfg", ".ini", ".conf"}
            or f.name.startswith(".env")
            or suffix == ".json"
        ):
            for m in _DOMAIN_RE.finditer(content):
                d = m.group(1).lower()
                if not _ALWAYS_SKIP_DOMAIN_RE.match(d):
                    domains_high.add(d)

    merged = sorted(domains_high | domains_medium)
    return merged, "source_scan"


# ─── shell tool extraction ────────────────────────────────────────────────────

_DELIMITERS_RE = re.compile(
    r"(?:^|[;|&({`\n])\s*(?:sudo\s+|env\s+(?:[A-Z_]+=\S+\s+)*)?"
    r"([a-zA-Z][a-zA-Z0-9_-]*)",
    re.MULTILINE,
)
_EXPLICIT_DEP_RE = re.compile(r"(?:command\s+-[vV]|which|type)\s+([a-zA-Z][a-zA-Z0-9_-]*)")
_SHEBANG_RE = re.compile(r"#!/usr/bin/env\s+([a-zA-Z][a-zA-Z0-9_.-]*)")
_LINE_COMMENT_RE = re.compile(r"^\s*#")

_NOISE = {
    "true", "false", "null", "yes", "no", "on", "off", "ok", "all", "none",
    "default", "main", "not", "new", "get", "set", "add", "push", "pull",
    "run", "build", "test", "clean", "init", "use", "with", "from", "to",
    "at", "by", "as", "of", "is", "it", "do", "done", "pass", "fail", "skip",
    "start", "stop", "restart", "status", "check", "list", "show", "help",
    "version", "install", "uninstall", "update", "upgrade", "config",
    "create", "delete", "remove", "apply", "deploy", "release", "tag",
}

_BASH_BUILTINS_FALLBACK = {
    "if", "then", "else", "elif", "fi", "for", "while", "until",
    "do", "done", "case", "esac", "in", "function", "time",
    "echo", "cd", "export", "source", "read", "return", "exit",
    "break", "continue", "eval", "exec", "set", "unset", "local",
    "declare", "typeset", "readonly", "shift", "getopts", "trap",
    "wait", "jobs", "fg", "bg", "kill", "umask", "ulimit", "alias",
    "unalias", "hash", "help", "let", "printf", "test", "true", "false",
}


def _bash_builtins() -> set[str]:
    try:
        out = subprocess.check_output(
            ["bash", "-c", "compgen -b; compgen -k"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return set(out.split()) or _BASH_BUILTINS_FALLBACK
    except Exception:
        return _BASH_BUILTINS_FALLBACK


def _extract_commands(content: str, shell_builtins: set[str]) -> set[str]:
    """Pull command-position tokens from shell-like text."""
    lines = [l for l in content.splitlines() if not _LINE_COMMENT_RE.match(l)]
    clean = "\n".join(lines)
    cmds: set[str] = set()
    for m in _DELIMITERS_RE.finditer(clean):
        cmd = m.group(1)
        if (
            cmd
            and len(cmd) > 1
            and cmd not in shell_builtins
            and cmd not in _NOISE
            and not cmd.isupper()
            and not cmd[0].isupper()
            and "/" not in cmd
            and not cmd[0].isdigit()
        ):
            cmds.add(cmd)
    for m in _EXPLICIT_DEP_RE.finditer(clean):
        cmd = m.group(1)
        if cmd and len(cmd) > 1 and cmd not in shell_builtins:
            cmds.add(cmd)
    return cmds


_TASK_FILE_NAMES = {
    "Makefile", "makefile", "GNUmakefile",
    "Taskfile.yml", "Taskfile.yaml",
    "justfile", "Justfile",
}
_MAKEFILE_NAMES = {"Makefile", "makefile", "GNUmakefile"}
_SHEBANG_HEADERS = (
    b"#!/bin/bash", b"#!/bin/sh",
    b"#!/usr/bin/env bash", b"#!/usr/bin/env sh",
)


def _makefile_recipes_only(content: str) -> str:
    """Return only TAB-indented recipe lines from a Makefile."""
    return "\n".join(l for l in content.splitlines() if l.startswith("\t"))


def _collect_shell_files(repo_path: Path) -> list[Path]:
    out: list[Path] = []
    for f in repo_path.rglob("*"):
        if not f.is_file():
            continue
        if any(d in _SKIP_DIRS_LITE for d in f.relative_to(repo_path).parts):
            continue
        if f.suffix in {".sh", ".bash"}:
            out.append(f)
        elif not f.suffix:
            try:
                hdr = f.read_bytes()[:100]
                if any(s in hdr for s in _SHEBANG_HEADERS):
                    out.append(f)
            except Exception:
                pass
    return out


def _collect_task_files(repo_path: Path) -> list[Path]:
    return [repo_path / n for n in _TASK_FILE_NAMES if (repo_path / n).exists()]


def _scan_tools(repo_path: Path, shell_builtins: set[str]) -> set[str]:
    tools: set[str] = set()
    for f in _collect_shell_files(repo_path) + _collect_task_files(repo_path):
        content = _read_text(f)
        parse_content = _makefile_recipes_only(content) if f.name in _MAKEFILE_NAMES else content
        tools |= _extract_commands(parse_content, shell_builtins)
        for m in _SHEBANG_RE.finditer(content):
            cmd = m.group(1)
            if cmd not in shell_builtins:
                tools.add(cmd)
    return tools


# ─── CI workflows ─────────────────────────────────────────────────────────────

_USES_RE = re.compile(r"uses:\s*([^\s@\n]+)")
_RUN_BLOCK_RE = re.compile(r"^\s+run:\s*[|>]?\s*\n((?:[ \t]+.+\n?)*)", re.MULTILINE)
_GHA_EXPR_RE = re.compile(r"\$\{\{[^}]*\}\}")
_INLINE_SCRIPT_RE = re.compile(
    r"""(?:node|bun|deno|python3?|ruby|perl)\s+(?:-\w+\s+)*-[ec]\s+(?:"[^"]*"|'[^']*')"""
)
_CI_STRIP_RE = re.compile(
    r"^(?:setup|install|action|run)-|-(?:action|toolchain|cache|setup|runner|builder)$"
)
_CI_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_.-]+$")
_CI_RUN_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_-]+$")
_GHA_SECRET_RE = re.compile(r"(?<=secrets\.)[A-Z_]+")


def _scan_ci_workflows(repo_path: Path, shell_builtins: set[str]) -> tuple[set[str], set[str]]:
    """Return (ci_tools, gha_secrets) found in any *.yml under a
    `.github/` path anywhere in the tree (matches the bash skill's
    `rglob('*.yml')` + `'.github' in str(wf)` filter so monorepo
    layouts with per-subdir `.github/` are picked up).

    GHA secrets are scanned across the same set plus *.yaml.
    """
    ci_tools: set[str] = set()
    secrets: set[str] = set()
    # ci_tools: bash skill only scans *.yml under '.github' paths
    for wf in repo_path.rglob("*.yml"):
        if not wf.is_file():
            continue
        rel = wf.relative_to(repo_path)
        if ".github" not in str(rel):
            continue
        if any(d in _SKIP_DIRS_LITE for d in rel.parts):
            continue
        content = _read_text(wf)
        # uses:
        for m in _USES_RE.finditer(content):
            parts = m.group(1).lower().split("/")
            if len(parts) >= 2:
                tool = _CI_STRIP_RE.sub("", parts[1]).strip("-")
                if tool and len(tool) > 1 and _CI_TOOL_NAME_RE.match(tool):
                    ci_tools.add(tool)
        # run:
        for m in _RUN_BLOCK_RE.finditer(content):
            run_content = _GHA_EXPR_RE.sub(" __EXPR__ ", m.group(1))
            run_content = _INLINE_SCRIPT_RE.sub(" __INLINE_SCRIPT__ ", run_content)
            ci_tools |= {
                t for t in _extract_commands(run_content, shell_builtins)
                if _CI_RUN_TOKEN_RE.match(t)
            }
        # secrets.X (also scanned in *.yaml below)
        for m in _GHA_SECRET_RE.finditer(content):
            secrets.add(m.group(0))

    # GHA secrets (analyze-repo.sh 836-848) — additionally scan *.yaml under
    # `.github/workflows/`. The bash skill globs both extensions for secrets.
    for wf in repo_path.rglob("*.yaml"):
        if not wf.is_file():
            continue
        rel = wf.relative_to(repo_path)
        sr = str(rel)
        if ".github" not in sr or "workflows" not in sr:
            continue
        if any(d in _SKIP_DIRS_LITE for d in rel.parts):
            continue
        for m in _GHA_SECRET_RE.finditer(_read_text(wf)):
            secrets.add(m.group(0))
    return ci_tools, secrets


# ─── language imports ─────────────────────────────────────────────────────────

_PY_IMPORT_RE = re.compile(
    r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.MULTILINE,
)
_TS_IMPORT_RE = re.compile(
    r"""(?:import|require)\s*(?:\(['"]|from\s+['"])([@a-zA-Z][^'"]+)['"]"""
)


def _python_stdlib() -> frozenset[str]:
    """sys.stdlib_module_names if available, plus builtin_module_names."""
    names = frozenset(getattr(sys, "stdlib_module_names", frozenset()))
    if not names:
        try:
            import pkgutil, sysconfig
            stdlib_path = sysconfig.get_python_lib(standard_lib=True)
            names = frozenset(m.name for m in pkgutil.iter_modules([stdlib_path]))
        except Exception:
            names = frozenset()
    return names | frozenset(sys.builtin_module_names)


_NODE_BUILTINS_CACHE: frozenset[str] | None = None


def _node_builtins() -> frozenset[str]:
    """Lazy `node -e ...builtinModules` lookup; cached for the process."""
    global _NODE_BUILTINS_CACHE
    if _NODE_BUILTINS_CACHE is not None:
        return _NODE_BUILTINS_CACHE
    # Allow override via env var (matches bash skill's AR_NODE_BUILTINS)
    raw = os.environ.get("AR_NODE_BUILTINS")
    if raw:
        try:
            mods = json.loads(raw)
            _NODE_BUILTINS_CACHE = frozenset(m.replace("node:", "") for m in mods)
            return _NODE_BUILTINS_CACHE
        except Exception:
            pass
    try:
        out = subprocess.check_output(
            ["node", "-e", 'console.log(JSON.stringify(require("module").builtinModules))'],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        )
        mods = json.loads(out)
        _NODE_BUILTINS_CACHE = frozenset(m.replace("node:", "") for m in mods)
    except Exception:
        _NODE_BUILTINS_CACHE = frozenset()
    return _NODE_BUILTINS_CACHE


def _scan_py_imports(repo_path: Path) -> set[str]:
    stdlib = _python_stdlib()
    local_modules = (
        {p.name for p in repo_path.iterdir() if p.is_dir() and not p.name.startswith(".")}
        | {p.stem for p in repo_path.glob("*.py")}
    )
    found: set[str] = set()
    for py in repo_path.rglob("*.py"):
        if any(d in _SKIP_DIRS_LITE for d in py.relative_to(repo_path).parts):
            continue
        content = _read_text(py)
        for m in _PY_IMPORT_RE.finditer(content):
            pkg = m.group(1).split(".")[0]
            if pkg and pkg not in stdlib and not pkg.startswith("_") and pkg not in local_modules:
                found.add(pkg)
    return found


def _scan_ts_imports(repo_path: Path) -> set[str]:
    builtins = _node_builtins()
    found: set[str] = set()
    for tsf in list(repo_path.rglob("*.ts")) + list(repo_path.rglob("*.js")):
        if any(d in _SKIP_DIRS_LITE for d in tsf.relative_to(repo_path).parts):
            continue
        content = _read_text(tsf)
        for m in _TS_IMPORT_RE.finditer(content):
            pkg = m.group(1).split("/")[0]
            if pkg and not pkg.startswith(".") and pkg not in builtins:
                found.add(pkg)
    return found


# ─── env-var reads from source code ───────────────────────────────────────────

_TS_ENV_RE = re.compile(r"process\.env\.([A-Z_]+(?:KEY|TOKEN|SECRET|PAT))")
_PY_ENV_RE = re.compile(
    r"""(?:os\.environ\.get\(['"]|os\.environ\[['"])([A-Z_]+)"""
)
_GO_ENV_RE = re.compile(r"""os\.Getenv\(["']([A-Z_]+)["']\)""")


def _scan_source_env_vars(repo_path: Path) -> set[str]:
    """Mirror analyze-repo.sh lines 850-864 — all caps env names from
    source code env reads. TS/JS only those with KEY/TOKEN/SECRET/PAT
    suffix; Python and Go capture any all-caps name.
    """
    found: set[str] = set()
    for f in repo_path.rglob("*"):
        if not f.is_file():
            continue
        if any(d in _SKIP_DIRS_LITE for d in f.relative_to(repo_path).parts):
            continue
        suffix = f.suffix
        if suffix in {".ts", ".js"}:
            content = _read_text(f)
            for m in _TS_ENV_RE.finditer(content):
                found.add(m.group(1))
        elif suffix == ".py":
            content = _read_text(f)
            for m in _PY_ENV_RE.finditer(content):
                found.add(m.group(1))
        elif suffix == ".go":
            content = _read_text(f)
            for m in _GO_ENV_RE.finditer(content):
                found.add(m.group(1))
    return found


# ─── credentials routing for source-code-discovered names ─────────────────────

_KEY_SUF_RE = re.compile(r"_KEY$")
_TOKEN_SUF_RE = re.compile(r"_TOKEN$")


def _route_source_env(names: set[str], result: AnalysisResult) -> None:
    """Source-code env vars use a stricter routing than .env.example:
    only `_KEY$` → api_keys, only `_TOKEN$` → tokens.
    """
    for n in names:
        if _KEY_SUF_RE.search(n):
            result.credentials_required.api_keys.append(n)
        if _TOKEN_SUF_RE.search(n):
            result.credentials_required.tokens.append(n)


def _route_gha_secrets(secrets: set[str], result: AnalysisResult) -> None:
    """GHA secrets routing per analyze-repo.sh lines 837-848:
    `_KEY$` → api_keys; `_TOKEN$` or literal GITHUB_TOKEN → tokens; else other.
    """
    for s in secrets:
        if _KEY_SUF_RE.search(s):
            result.credentials_required.api_keys.append(s)
        elif _TOKEN_SUF_RE.search(s) or s == "GITHUB_TOKEN":
            result.credentials_required.tokens.append(s)
        else:
            result.credentials_required.other.append(s)


# ─── SSH detection ────────────────────────────────────────────────────────────

_SSH_PATTERN_RE = re.compile(r"ssh|id_rsa|known_hosts|ssh-keygen|ssh-agent|SSH_AUTH_SOCK")
_SSH_SCAN_SUFFIXES = {".sh", ".ts", ".js", ".py", ".json", ".yml", ".yaml"}


def _has_ssh_signal(repo_path: Path) -> bool:
    for f in repo_path.rglob("*"):
        if not f.is_file():
            continue
        if f.name in _SKIP_FILES:
            continue
        if any(d in _SKIP_DIRS_LITE for d in f.relative_to(repo_path).parts):
            continue
        if f.suffix not in _SSH_SCAN_SUFFIXES:
            continue
        content = _read_text(f)
        if _SSH_PATTERN_RE.search(content):
            return True
    return False


# ─── GitHub API usage ─────────────────────────────────────────────────────────

_GH_API_RE = re.compile(r"@octokit|PyGithub|go-github|Octokit|github\.rest\.|gh api ")
_GH_API_SUFFIXES = {".json", ".txt", ".py", ".go", ".ts", ".js", ".sh"}


def _has_github_api(repo_path: Path) -> bool:
    for f in repo_path.rglob("*"):
        if not f.is_file():
            continue
        if any(d in _SKIP_DIRS_LITE for d in f.relative_to(repo_path).parts):
            continue
        if f.suffix not in _GH_API_SUFFIXES:
            continue
        content = _read_text(f)
        if _GH_API_RE.search(content):
            return True
    return False


# ─── MCP servers ──────────────────────────────────────────────────────────────

_MCP_CFG_PATHS = (
    ".mcp.json",
    ".claude/mcp.json",
    ".claude/settings.json",
    ".claude/settings.local.json",
)


def _scan_mcp_servers(repo_path: Path) -> list[str]:
    """Return sorted unique server names across all MCP configs + npm deps."""
    servers: set[str] = set()
    for rel in _MCP_CFG_PATHS:
        f = repo_path / rel
        if not f.is_file():
            continue
        try:
            d = json.loads(_read_text(f))
        except Exception:
            continue
        for name in (d.get("mcpServers") or {}).keys():
            if name:
                servers.add(name)

    pj = repo_path / "package.json"
    if pj.is_file():
        try:
            d = json.loads(_read_text(pj))
            all_deps = {**(d.get("dependencies") or {}), **(d.get("devDependencies") or {})}
            for k in all_deps:
                if "@modelcontextprotocol" in k or "mcp-server" in k:
                    servers.add(k)
        except Exception:
            pass

    return sorted(servers)


# ─── Claude plugins ───────────────────────────────────────────────────────────

def _scan_claude_plugins(repo_path: Path) -> list[str]:
    f = repo_path / ".claude-plugin" / "marketplace.json"
    if not f.is_file():
        return []
    try:
        d = json.loads(_read_text(f))
    except Exception:
        return []
    out: list[str] = []
    for p in d.get("plugins") or []:
        name = p.get("name", "")
        if name:
            out.append(name)
    return out


# ─── orchestrator ─────────────────────────────────────────────────────────────

def detect(repo_path: Path, result: AnalysisResult) -> None:
    """Mutate `result` in place with source-scan-derived fields.

    Assumes manifests.detect() and dockerfile.detect() have already run.
    """
    shell_builtins = _bash_builtins()

    # ── external services ────────────────────────────────────────────────────
    domains, source = _scan_external_services(repo_path)
    result.external_services.domains = domains
    result.external_services.source = source

    # ── inferred.tools (shell + makefile + taskfile) ─────────────────────────
    tools = _scan_tools(repo_path, shell_builtins)

    # ── ci_tools + gha secrets ───────────────────────────────────────────────
    ci_tools, gha_secrets = _scan_ci_workflows(repo_path, shell_builtins)

    # ── language imports ─────────────────────────────────────────────────────
    py_imports = _scan_py_imports(repo_path)
    ts_imports = _scan_ts_imports(repo_path)

    # ── populate inferred.* with new/confirmed dedup ─────────────────────────
    sys_pkg_set = set(result.system_packages)
    py_lib_set = {p.lower() for p in result.libraries.python}
    node_lib_set = {n for n in result.libraries.node}

    result.inferred.tools = sorted(tools)
    result.inferred.tools_confirmed = sorted(t for t in tools if t in sys_pkg_set)
    result.inferred.tools_new = sorted(t for t in tools if t not in sys_pkg_set)

    result.inferred.py_imports = sorted(py_imports)
    result.inferred.py_imports_confirmed = sorted(
        p for p in py_imports if p.lower() in py_lib_set
    )
    result.inferred.py_imports_new = sorted(
        p for p in py_imports if p.lower() not in py_lib_set
    )

    result.inferred.ts_imports = sorted(ts_imports)
    result.inferred.ts_imports_confirmed = sorted(t for t in ts_imports if t in node_lib_set)
    result.inferred.ts_imports_new = sorted(t for t in ts_imports if t not in node_lib_set)

    result.inferred.ci_tools = sorted(ci_tools)

    # ── source-code env vars: ADD to existing list, route into creds ─────────
    src_env = _scan_source_env_vars(repo_path)
    if src_env:
        merged = set(result.env_vars) | src_env
        result.env_vars = sorted(merged)
    _route_source_env(src_env, result)

    # ── GitHub Actions secrets routing ───────────────────────────────────────
    _route_gha_secrets(gha_secrets, result)

    # ── SSH signal ───────────────────────────────────────────────────────────
    if _has_ssh_signal(repo_path):
        result.credentials_required.ssh = True
    # outbound port hint: openssh / ssh in system packages
    sys_blob = " ".join(result.system_packages).lower()
    if "openssh" in sys_blob or " ssh " in f" {sys_blob} ":
        result.credentials_required.ssh = True

    # ── github API usage ─────────────────────────────────────────────────────
    result.github_api_usage = _has_github_api(repo_path)

    # ── MCP + plugins ────────────────────────────────────────────────────────
    result.mcp_servers = _scan_mcp_servers(repo_path)
    result.claude_plugins = _scan_claude_plugins(repo_path)

    # ── final dedup of credentials buckets ───────────────────────────────────
    result.credentials_required.api_keys = sorted(set(result.credentials_required.api_keys))
    result.credentials_required.tokens = sorted(set(result.credentials_required.tokens))
    result.credentials_required.other = sorted(set(result.credentials_required.other))
