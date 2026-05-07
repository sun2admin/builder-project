"""Dataclasses for the analysis-result schema.

Mirrors the JSON shape documented in
`.claude/skills/analyze-repo/DATA_SCHEMA.md`. `schema_version` is bumped
when a backward-incompatible field change ships; current = 2.

Serialization: use `dataclasses.asdict()` to convert to plain dict. The
write_outputs helper sorts keys at JSON dump time, so dataclass field
order is documentation only.
"""

from __future__ import annotations

from dataclasses import dataclass, field


SCHEMA_VERSION = 2


@dataclass
class Libraries:
    node: list[str] = field(default_factory=list)
    python: list[str] = field(default_factory=list)
    go: list[str] = field(default_factory=list)
    rust: list[str] = field(default_factory=list)


@dataclass
class Ports:
    inbound: list[int] = field(default_factory=list)


@dataclass
class ExternalServices:
    domains: list[str] = field(default_factory=list)
    source: str = ""  # firewall_script | source_scan | config_files | readme_codefence | readme_prose | multi


@dataclass
class CredentialsRequired:
    api_keys: list[str] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)
    ssh: bool = False
    other: list[str] = field(default_factory=list)


@dataclass
class PostChainStep:
    raw: str = ""
    sudo: bool = False
    script: str = ""
    args: str = ""
    in_repo: bool = False


@dataclass
class Container:
    capabilities: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    remote_user: str = ""
    post_start: str = ""
    post_create: str = ""
    post_attach: str = ""
    post_start_chain: list[PostChainStep] = field(default_factory=list)
    post_create_chain: list[PostChainStep] = field(default_factory=list)
    init_scripts: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    vscode_settings: dict = field(default_factory=dict)
    workspace_mount: str = ""
    workspace_folder: str = ""
    wait_for: str = ""
    shutdown_action: str = ""


@dataclass
class Inferred:
    tools: list[str] = field(default_factory=list)
    tools_new: list[str] = field(default_factory=list)
    tools_confirmed: list[str] = field(default_factory=list)
    py_imports: list[str] = field(default_factory=list)
    py_imports_new: list[str] = field(default_factory=list)
    py_imports_confirmed: list[str] = field(default_factory=list)
    ts_imports: list[str] = field(default_factory=list)
    ts_imports_new: list[str] = field(default_factory=list)
    ts_imports_confirmed: list[str] = field(default_factory=list)
    ci_tools: list[str] = field(default_factory=list)


@dataclass
class SystemDep:
    apt_package: str | None = None
    apt_depends: list[str] = field(default_factory=list)


@dataclass
class Suggested:
    base_image: str = "latest"  # latest | playwright_with_chromium
    ai_install: str = "claude"
    plugin_layer: str = ""


@dataclass
class AnalysisResult:
    repo: str = ""
    project: str = ""
    analyzed_at: str = ""
    purpose: str = ""
    primary_language: str = ""
    languages: list[str] = field(default_factory=list)
    runtime_extras: list[str] = field(default_factory=list)
    runtime_versions: dict[str, str] = field(default_factory=dict)
    dockerfile_base: str = ""
    system_packages: list[str] = field(default_factory=list)
    extra_binaries: list[str] = field(default_factory=list)
    global_js_packages: list[str] = field(default_factory=list)
    dockerfile_python_installs: list[str] = field(default_factory=list)
    dockerfile_go_installs: list[str] = field(default_factory=list)
    libraries: Libraries = field(default_factory=Libraries)
    ports: Ports = field(default_factory=Ports)
    external_services: ExternalServices = field(default_factory=ExternalServices)
    env_vars: list[str] = field(default_factory=list)
    browser_tools: list[str] = field(default_factory=list)
    github_api_usage: bool = False
    container: Container = field(default_factory=Container)
    credentials_required: CredentialsRequired = field(default_factory=CredentialsRequired)
    mcp_servers: list[dict] = field(default_factory=list)
    claude_plugins: list[str] = field(default_factory=list)
    inferred: Inferred = field(default_factory=Inferred)
    system_deps: dict[str, SystemDep] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    suggested: Suggested = field(default_factory=Suggested)
    is_marketplace: bool = False
    marketplace_name: str = ""
    marketplace_plugins: list[dict] = field(default_factory=list)
