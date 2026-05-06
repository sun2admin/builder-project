"""Markdown report emitter.

Renders an `AnalysisResult` (or its asdict form) into the human-readable
markdown summary written to `analyzed_repos/<owner>/<repo>/analysis.md`.

Mirrors the inline Python markdown block in `analyze-repo.sh`
(lines ~1469-1617) — output must match canonical samples in
`analyzed_repos/`.
"""

from __future__ import annotations


def _fmt(items, empty: str = "none detected") -> str:
    if not items:
        return empty
    return ", ".join(str(i) for i in items)


def _fmt_creds(c: dict) -> str:
    parts: list[str] = []
    if c.get("api_keys"):
        parts.append(f"API keys: {', '.join(c['api_keys'])}")
    if c.get("tokens"):
        parts.append(f"Tokens: {', '.join(c['tokens'])}")
    if c.get("ssh"):
        parts.append("SSH key required")
    if c.get("other"):
        parts.append(f"Other: {', '.join(c['other'])}")
    if not parts:
        return "  none detected"
    return "\n".join(f"  - {p}" for p in parts)


def _fmt_container(c: dict) -> str:
    lines: list[str] = []
    if c.get("capabilities"):
        lines.append(f"  - Docker caps: {', '.join(c['capabilities'])}")
    if c.get("remote_user"):
        lines.append(f"  - User: {c['remote_user']}")
    if c.get("post_start"):
        lines.append(f"  - postStartCommand: `{c['post_start']}`")
    if c.get("post_create"):
        lines.append(f"  - postCreateCommand: `{c['post_create']}`")
    for v in c.get("volumes") or []:
        if isinstance(v, dict):
            name = v.get("name", "")
            target = v.get("target", "")
        else:
            name = str(v)
            target = ""
        lines.append(f"  - Volume: `{name}` → `{target}`")
    for k in c.get("env") or {}:
        lines.append(f"  - ENV: `{k}`")
    if not lines:
        return "  standard (no special requirements)"
    return "\n".join(lines)


def _fmt_chain(chain: list, label: str) -> str:
    if not chain:
        return f"  - {label}: none\n"
    out = [f"  - **{label}**:"]
    for step in chain:
        marker = "✓ in-repo" if step.get("in_repo") else "○ baked/external"
        sudo = " (sudo)" if step.get("sudo") else ""
        script = step.get("script") or "(no script)"
        args = f" `{step['args']}`" if step.get("args") else ""
        out.append(f"      - {marker}{sudo}: `{script}`{args}")
    return "\n".join(out) + "\n"


def render(data: dict) -> str:
    """Return markdown report string for the analysis dict.

    Input is the dict returned by `analyzers.analyze(repo)`, matching
    the analysis.json schema (no `analyzed_at` mutations, all fields
    populated by detector modules).
    """
    libraries = data.get("libraries") or {}
    ports = data.get("ports") or {}
    external = data.get("external_services") or {}
    container = data.get("container") or {}
    creds = data.get("credentials_required") or {}
    inferred = data.get("inferred") or {}
    sys_deps = data.get("system_deps") or {}

    runtime_versions = data.get("runtime_versions") or {}
    versions_list = [f"{k} {v}" for k, v in runtime_versions.items()]

    md = f"""# Dependency Analysis: {data.get('project', '')}

**Repo:** {data.get('repo', '')}
**Analyzed:** {data.get('analyzed_at', '')}
**Purpose:** {data.get('purpose') or 'see README'}

---

## Languages & Runtimes
- Languages: {_fmt(data.get('languages') or [])}
- Runtime extras: {_fmt(data.get('runtime_extras') or [])}
- Versions: {_fmt(versions_list)}
- Base image: `{data.get('dockerfile_base') or 'not specified'}`

## System Packages
{_fmt(data.get('system_packages') or [])}

## Global JS Package Installs *(Dockerfile npm/pnpm/yarn/bun globals)*
{_fmt(data.get('global_js_packages') or [])}

## Dockerfile Python Installs *(`pip` / `pipx` in RUN blocks)*
{_fmt(data.get('dockerfile_python_installs') or [])}

## Dockerfile Go Installs *(`go install` in RUN blocks)*
{_fmt(data.get('dockerfile_go_installs') or [])}

## Libraries
"""

    lib_lines: list[str] = []
    for lang, libs in libraries.items():
        if libs:
            preview = libs[:12]
            more = f" ... ({len(libs) - 12} more)" if len(libs) > 12 else ""
            lib_lines.append(
                f"  - **{lang}**: {', '.join(str(x) for x in preview)}{more}"
            )
    if not any(libraries.values()):
        md += "  none detected\n"
    else:
        md += "\n".join(lib_lines) + "\n"

    inbound = [str(p) for p in (ports.get("inbound") or [])]
    md += f"""
## Ports
- Inbound: {_fmt(inbound)}

## External Services *(source: {external.get('source', '')})*
{_fmt(external.get('domains') or [])}

## Environment Variables
{_fmt(data.get('env_vars') or [])}

## Container Requirements
{_fmt_container(container)}

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
"""

    md += _fmt_chain(container.get("post_start_chain") or [], "post_start_chain")
    md += _fmt_chain(container.get("post_create_chain") or [], "post_create_chain")
    init_scripts = container.get("init_scripts") or []
    if init_scripts:
        md += f"  - **init_scripts (in-repo)**: {_fmt(init_scripts)}\n"

    mcp_servers = data.get("mcp_servers") or []
    if mcp_servers and isinstance(mcp_servers[0], dict):
        mcp_display = [m.get("name", "") for m in mcp_servers if m.get("name")]
    else:
        mcp_display = mcp_servers

    md += f"""

## Credentials Required
{_fmt_creds(creds)}

## MCP Servers
{_fmt(mcp_display)}

## Claude Plugins
{_fmt(data.get('claude_plugins') or [])}

## Browser / Test Tools
{_fmt(data.get('browser_tools') or [])}

## GitHub API Usage
{'Yes' if data.get('github_api_usage') else 'No'}

## Inferred from Source *(tools/commands found in repo files)*
"""

    tools_new = inferred.get("tools_new") or []
    tools_confirmed = inferred.get("tools_confirmed") or []
    py_imports = inferred.get("py_imports") or []
    ts_imports = inferred.get("ts_imports") or []
    ci_tools = inferred.get("ci_tools") or []
    py_imports_new = inferred.get("py_imports_new") or []
    py_imports_confirmed = inferred.get("py_imports_confirmed") or []
    ts_imports_new = inferred.get("ts_imports_new") or []
    ts_imports_confirmed = inferred.get("ts_imports_confirmed") or []

    has_inferred = bool(tools_new or py_imports or ts_imports or ci_tools)
    if has_inferred:
        if tools_new:
            md += f"  - **Tools/binaries (not in Dockerfile)**: {_fmt(tools_new)}\n"
        if tools_confirmed:
            md += f"  - **Confirmed by Dockerfile**: {_fmt(tools_confirmed)}\n"
        if ci_tools:
            md += f"  - **CI toolchain (GitHub Actions)**: {_fmt(ci_tools)}\n"
        if py_imports_new:
            md += f"  - **Python imports (not in manifest)**: {_fmt(py_imports_new)}\n"
        if py_imports_confirmed:
            md += f"  - **Python imports confirmed by manifest**: {_fmt(py_imports_confirmed)}\n"
        if ts_imports_new:
            md += f"  - **TS/JS imports (not in package.json)**: {_fmt(ts_imports_new)}\n"
        if ts_imports_confirmed:
            md += f"  - **TS/JS imports confirmed by package.json**: {_fmt(ts_imports_confirmed)}\n"
    elif tools_confirmed:
        md += f"  - all detected tools already declared in Dockerfile: {_fmt(tools_confirmed)}\n"
    else:
        md += "  none detected\n"

    if sys_deps:
        md += "\n## System Dependencies *(tools → apt packages, via tool-deps.json cache)*\n"
        for tool, info in sys_deps.items():
            pkg = info.get("apt_package") or tool
            deps = info.get("apt_depends") or []
            dep_str = f" (needs: {', '.join(deps[:5])})" if deps else ""
            md += f"  - `{tool}` → `{pkg}`{dep_str}\n"

    return md
