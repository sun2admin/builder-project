"""Dockerfile + devcontainer detection.

Populates these schema fields:
    dockerfile_base, system_packages, extra_binaries, global_js_packages,
    dockerfile_python_installs, dockerfile_go_installs,
    ports.inbound, env_vars,
    container.{capabilities, volumes, env, remote_user,
               post_start, post_create, post_start_chain, post_create_chain,
               init_scripts, extensions},
    credentials_required.{api_keys, tokens, ssh, other}
        — but only the env-var-routed (.env.example) and volume-routed
          (`/run/credentials/*` bind mounts) signals. Source-code env
          patterns + GitHub Actions secrets land in source_scan.py.

Source files scanned (per analyze-repo.sh lines 199-466 + 469-599 +
677-694 + 813-922 + 980-1006):
    .devcontainer/devcontainer.json (jsonc)
    .vscode/extensions.json (jsonc)
    Dockerfile / Dockerfile.* / *.dockerfile
    docker-compose*.yml / .yaml
    .env.example / .env.sample / .env.template / .env.test / .env.development
    in-repo scripts referenced by postStart/postCreate chains
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import AnalysisResult, PostChainStep


# ─── jsonc helpers ────────────────────────────────────────────────────────────

_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _parse_jsonc(text: str) -> dict:
    """Tolerant JSON-with-comments parser. Strips // and /* */ comments."""
    text = _LINE_COMMENT_RE.sub("", text)
    text = _BLOCK_COMMENT_RE.sub("", text)
    return json.loads(text)


# ─── devcontainer.json ────────────────────────────────────────────────────────

def _parse_mount_string(s: str) -> dict:
    """`source=X,target=Y,type=Z[,readonly,...]` → {name, target, type}."""
    parts = dict(p.split("=", 1) for p in s.split(",") if "=" in p)
    return {
        "name": parts.get("source", ""),
        "target": parts.get("target", ""),
        "type": parts.get("type", "volume"),
    }


def _parse_devcontainer(repo_path: Path) -> dict:
    """Return a dict with all devcontainer-derived fields, or empty defaults
    if the file is absent/malformed.
    """
    empty = {
        "capabilities": [],
        "volumes": [],
        "container_env": {},
        "post_start": "",
        "post_create": "",
        "extensions": [],
        "forward_ports": [],
        "remote_user": "",
    }
    f = repo_path / ".devcontainer" / "devcontainer.json"
    if not f.is_file():
        return empty
    try:
        d = _parse_jsonc(f.read_text(errors="ignore"))
    except Exception:
        return empty

    caps: list[str] = []
    for a in d.get("runArgs", []) or []:
        if "--cap-add" in a:
            caps.append(a.replace("--cap-add=", "").replace("--cap-add ", "").strip())

    mounts: list[dict] = []
    for m in d.get("mounts", []) or []:
        if isinstance(m, str) and "source=" in m:
            mounts.append(_parse_mount_string(m))
        elif isinstance(m, dict):
            mounts.append({
                "name": m.get("source", ""),
                "target": m.get("target", ""),
                "type": m.get("type", "volume"),
            })

    exts = ((d.get("customizations") or {}).get("vscode") or {}).get("extensions") or []
    post_start = d.get("postStartCommand", "") or ""
    post_create = d.get("postCreateCommand", "") or ""

    # postStart/Create may be a string or list — normalize to string for the
    # back-compat raw field. The spec also allows dicts of named commands;
    # for now stringify their values (rare in practice).
    if isinstance(post_start, list):
        post_start = " && ".join(str(x) for x in post_start)
    elif isinstance(post_start, dict):
        post_start = " && ".join(str(v) for v in post_start.values())
    if isinstance(post_create, list):
        post_create = " && ".join(str(x) for x in post_create)
    elif isinstance(post_create, dict):
        post_create = " && ".join(str(v) for v in post_create.values())

    return {
        "capabilities": caps,
        "volumes": mounts,
        "container_env": d.get("containerEnv", {}) or {},
        "post_start": post_start,
        "post_create": post_create,
        "extensions": list(exts),
        "forward_ports": list(d.get("forwardPorts", []) or []),
        "remote_user": d.get("remoteUser", "") or "",
    }


def _vscode_extensions(repo_path: Path) -> list[str]:
    """Return recommendations from .vscode/extensions.json (jsonc)."""
    f = repo_path / ".vscode" / "extensions.json"
    if not f.is_file():
        return []
    try:
        d = _parse_jsonc(f.read_text(errors="ignore"))
    except Exception:
        return []
    return list(d.get("recommendations", []) or [])


# ─── postStart/postCreate chain decomposition ─────────────────────────────────

_INTERPRETERS = {"bash", "sh", "zsh", "python", "python3", "node", "ruby", "perl"}
_BASH_C_RE = re.compile(r"""^\s*(?:bash|sh)\s+-c\s+(["'])(.*)\1\s*$""", re.DOTALL)


def _strip_bash_c(cmd: str) -> str:
    m = _BASH_C_RE.match(cmd)
    return m.group(2) if m else cmd


def _split_chain(cmd: str) -> list[str]:
    """Split on top-level `&&` only (skip inside quotes)."""
    if not cmd:
        return []
    cmd = _strip_bash_c(cmd)
    parts: list[str] = []
    buf: list[str] = []
    q: str | None = None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            buf.append(c)
            if c == q and (i == 0 or cmd[i - 1] != "\\"):
                q = None
            i += 1
            continue
        if c in ("\"", "'"):
            q = c
            buf.append(c)
            i += 1
            continue
        if c == "&" and i + 1 < len(cmd) and cmd[i + 1] == "&":
            parts.append("".join(buf).strip())
            buf = []
            i += 2
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def _parse_step(raw: str) -> PostChainStep:
    """Decompose one chain step into a PostChainStep."""
    step = PostChainStep(raw=raw)
    parts = raw.split()
    if not parts:
        return step
    if parts[0] == "sudo":
        step.sudo = True
        parts = parts[1:]
    if not parts:
        return step
    head = parts[0]
    rest = parts[1:]
    while head.startswith("-") and rest:
        head = rest[0]
        rest = rest[1:]
    base = head.split("/")[-1].lower()
    base_no_ver = re.sub(r"\d+$", "", base)
    if base_no_ver in _INTERPRETERS and rest:
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            i += 1
        if i < len(rest):
            step.script = rest[i]
            step.args = " ".join(rest[i + 1:])
        else:
            step.args = " ".join(rest)
    else:
        step.script = head
        step.args = " ".join(rest)
    return step


def _in_repo_path(repo_path: Path, script: str) -> str | None:
    """Return repo-relative path if `script` lives in the cloned repo, else None."""
    if not script:
        return None
    if script.startswith("/workspace/"):
        # /workspace/<repo>/X → strip /workspace/<owner-or-name>/
        rel = script.split("/", 3)[-1] if script.count("/") >= 3 else script
        cand = repo_path / rel
        if cand.is_file():
            return rel
    elif script.startswith("/"):
        return None  # absolute path outside workspace; baked into image
    else:
        cand = repo_path / script
        if cand.is_file():
            return script

    # Fallback: progressively strip leading path components and try again
    parts = script.lstrip("/").split("/")
    for prefix_len in range(1, 5):
        if prefix_len >= len(parts):
            break
        rel = "/".join(parts[prefix_len:])
        cand = repo_path / rel
        if cand.is_file():
            return rel
    return None


_SCRIPT_FW_RE = re.compile(r"\b(iptables|ipset|init-firewall|nft\b|ufw\b)")
_SCRIPT_SSH_RE = re.compile(r"\b(ssh-add|ssh-agent|SSH_AUTH_SOCK)\b")
_SCRIPT_GH_RE = re.compile(r"\bgh\s+(auth|api)\b|@octokit|PyGithub")
_GIT_CLONE_RE = re.compile(r"git\s+clone\s+(?:--\S+\s+)*([^\s]+)")
_DOMAIN_RE = re.compile(r"https?://([^/\s\"']+)")
_GIT_DOMAIN_RE = re.compile(r"(?:https?://|git@)([^/:]+)")


def _scan_script(repo_path: Path, rel: str) -> tuple[bool, bool, bool, list[str]]:
    """Scan an in-repo script for firewall/ssh/gh hooks and outbound domains.

    Returned but not currently propagated by `detect()` — source_scan.py is
    the canonical owner of those signals. Kept here as a hook for future
    integration (`init_signal_*` style env routing) without re-reading files.
    """
    try:
        text = (repo_path / rel).read_text(errors="ignore")
    except Exception:
        return False, False, False, []
    fw = bool(_SCRIPT_FW_RE.search(text))
    ssh = bool(_SCRIPT_SSH_RE.search(text))
    gh = bool(_SCRIPT_GH_RE.search(text))
    domains: list[str] = []
    for m in _GIT_CLONE_RE.finditer(text):
        dm = _GIT_DOMAIN_RE.search(m.group(1))
        if dm:
            domains.append(dm.group(1))
    domains.extend(m.group(1) for m in _DOMAIN_RE.finditer(text))
    return fw, ssh, gh, sorted(set(domains))


def _process_chain(repo_path: Path, cmd: str) -> tuple[list[PostChainStep], list[str]]:
    """Return (chain_steps, in_repo_script_paths)."""
    chain: list[PostChainStep] = []
    scripts: list[str] = []
    for raw in _split_chain(cmd):
        step = _parse_step(raw)
        rel = _in_repo_path(repo_path, step.script) if step.script else None
        if rel:
            step.in_repo = True
            step.script = rel
            scripts.append(rel)
        chain.append(step)
    return chain, scripts


# ─── Dockerfile parsing ───────────────────────────────────────────────────────

_DOCKERFILE_GLOBS = ("Dockerfile", "Dockerfile.*", "*.dockerfile")
_PKG_NAME_RE = re.compile(r"^[a-z][a-z0-9._+-]{1,}$")
_FROM_RE = re.compile(r"FROM\s+(\S+)")
_PKG_INSTALL_RE = re.compile(r"apt-get install|apt install|apk add")
_PKG_BODY_RE = re.compile(r".*(?:install|add)\s+")
_PKG_TAIL_RE = re.compile(r"&&.*")
_BIN_RE = re.compile(r"releases/download/[^/\s]+/([^\s\"'\\]+)")
_BIN_LINE_RE = re.compile(r"wget|curl\s+-[oL]")
_JS_PATTERNS = (
    re.compile(r"\b(?:npm|pnpm|bun)\s+(?:install|i|add)\s+-g\b(.*?)(?:&&|\|\||;|$)"),
    re.compile(r"\byarn\s+global\s+add\b(.*?)(?:&&|\|\||;|$)"),
)
_PIP_RE = re.compile(r"\b(?:pip|pip3|pipx)\s+install\b(.*?)(?:&&|\|\||;|$)")
_PIP_HAS_REQ_RE = re.compile(r"\s-r\s")
_PIP_FLAGS_WITH_VAL = {
    "-r", "--requirement", "-c", "--constraint",
    "-e", "--editable", "--index-url", "--extra-index-url",
    "--find-links", "--target", "--prefix",
}
_GO_INSTALL_RE = re.compile(r"\bgo\s+install\b(.*?)(?:&&|\|\||;|$)")
_ENV_NAME_ANY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _join_continuations(text: str) -> list[str]:
    """Fold backslash-continuation lines into single logical lines."""
    joined: list[str] = []
    buf = ""
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
        else:
            buf += stripped
            joined.append(buf)
            buf = ""
    if buf:
        joined.append(buf)
    return joined


def _find_dockerfiles(repo_path: Path):
    """Yield dockerfile paths, excluding .git."""
    seen: set[Path] = set()
    for pat in _DOCKERFILE_GLOBS:
        for p in repo_path.rglob(pat):
            if ".git" in p.parts or not p.is_file() or p in seen:
                continue
            seen.add(p)
            yield p


def _parse_pip_tokens(body: str) -> list[str]:
    toks = body.split()
    out: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("-"):
            if t in _PIP_FLAGS_WITH_VAL:
                i += 2
                continue
            i += 1
            continue
        if t in ("|", "||", "&&", ";"):
            i += 1
            continue
        out.append(t)
        i += 1
    return out


def _parse_dockerfile(text: str) -> dict:
    """Extract base image, system packages, binaries, language-installs.

    Returns {base, packages, binaries, js_global, py_installs, go_installs,
              env_vars, expose_ports}.
    """
    joined = _join_continuations(text)

    base = ""
    packages: list[str] = []
    binaries: list[str] = []
    js_global: list[str] = []
    py_installs: list[str] = []
    go_installs: list[str] = []
    env_vars: list[str] = []
    expose_ports: list[int] = []

    for line in joined:
        if not base:
            m = _FROM_RE.match(line)
            if m:
                base = m.group(1)

        if _PKG_INSTALL_RE.search(line):
            body = _PKG_BODY_RE.sub("", line, count=1)
            body = _PKG_TAIL_RE.sub("", body)
            for p in body.split():
                if _PKG_NAME_RE.match(p) and p not in ("apt-get", "apt", "apk"):
                    packages.append(p)

        if _BIN_LINE_RE.search(line):
            m = _BIN_RE.search(line)
            if m:
                binaries.append(m.group(1))

        for pat in _JS_PATTERNS:
            for m in pat.finditer(line):
                for tok in m.group(1).split():
                    if tok.startswith("-") or tok in ("|", "||", "&&", ";"):
                        continue
                    js_global.append(tok)

        for m in _PIP_RE.finditer(line):
            body = m.group(1)
            if _PIP_HAS_REQ_RE.search(body):
                continue
            py_installs.extend(_parse_pip_tokens(body))

        for m in _GO_INSTALL_RE.finditer(line):
            for tok in m.group(1).split():
                if tok.startswith("-") or "@" not in tok or tok in ("|", "||", "&&", ";"):
                    continue
                go_installs.append(tok)

        # ENV directives: `ENV K=V K2=V2 ...` or legacy `ENV NAME value...`
        if line.startswith("ENV "):
            body = line[4:].strip()
            if "=" in body:
                for tok in body.split():
                    name = tok.split("=", 1)[0]
                    if _ENV_NAME_ANY_RE.match(name):
                        env_vars.append(name)
            else:
                first = body.split(maxsplit=1)[0] if body else ""
                if _ENV_NAME_ANY_RE.match(first):
                    env_vars.append(first)

        if line.startswith("EXPOSE"):
            for tok in line[6:].split():
                num = tok.split("/", 1)[0]
                if num.isdigit():
                    expose_ports.append(int(num))

    return {
        "base": base,
        "packages": packages,
        "binaries": binaries,
        "js_global": js_global,
        "py_installs": py_installs,
        "go_installs": go_installs,
        "env_vars": env_vars,
        "expose_ports": expose_ports,
    }


# ─── docker-compose ports ─────────────────────────────────────────────────────

_COMPOSE_PORT_LINE_RE = re.compile(r"""^\s*-\s*['"]?[0-9]*:[0-9]""")
_COMPOSE_PORT_RE = re.compile(r"\b([0-9]{2,5})\b")


def _compose_inbound_ports(repo_path: Path) -> list[int]:
    """Bash skill grep: lines like `- "8080:80"` → all 2-5 digit number-ish
    tokens on that line. Caps at 20 ports total to match `head -20`.
    """
    ports: list[int] = []
    files = list(repo_path.rglob("docker-compose*.yml")) + \
            list(repo_path.rglob("docker-compose*.yaml"))
    for f in files:
        if ".git" in f.parts or not f.is_file():
            continue
        try:
            for line in f.read_text(errors="ignore").splitlines():
                if _COMPOSE_PORT_LINE_RE.match(line):
                    for m in _COMPOSE_PORT_RE.finditer(line):
                        ports.append(int(m.group(1)))
                        if len(ports) >= 20:
                            return ports
        except Exception:
            continue
    return ports


# ─── env-var collection (.env.example + Dockerfile ENV + containerEnv) ────────

_ENV_FILES = (".env.example", ".env.sample", ".env.template", ".env.test", ".env.development")
_ENV_KEY_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)(?==)", re.MULTILINE)


def _env_keys_from_file(p: Path) -> list[str]:
    try:
        return _ENV_KEY_RE.findall(p.read_text(errors="ignore"))
    except Exception:
        return []


# ─── credentials routing ──────────────────────────────────────────────────────

_API_KEY_RE = re.compile(r"_KEY$|_SECRET$")
_TOKEN_RE = re.compile(r"_TOKEN$|_PAT$")
_OTHER_PREFIX_RE = re.compile(
    r"^(DATABASE_URL|REDIS_URL|MONGODB_URI|POSTGRES|MYSQL|SMTP_|"
    r"SENDGRID|TWILIO|STRIPE|DATADOG|SENTRY)"
)
_MOUNT_SSH_RE = re.compile(
    r"(?i)(^|_)(ssh|known_hosts|id_(rsa|ed25519|ecdsa|dsa))(_|$)|"
    r"_(ed25519|rsa|ecdsa|dsa)$"
)
_MOUNT_KEY_RE = re.compile(r"(?i)_key$")
_MOUNT_TOK_RE = re.compile(r"(?i)_(token|pat)$")
_MOUNT_SECRET_RE = re.compile(r"(?i)_secret$")


def _route_env_credentials(env_keys: list[str], result: AnalysisResult) -> None:
    """Bash routing (analyze-repo.sh 822-833): exclusive — each key lands in
    at most one bucket. Keys not matching any pattern are dropped from
    credentials_required (still appear in env_vars).
    """
    for key in env_keys:
        if _API_KEY_RE.search(key):
            result.credentials_required.api_keys.append(key)
        elif _TOKEN_RE.search(key):
            result.credentials_required.tokens.append(key)
        elif _OTHER_PREFIX_RE.match(key):
            result.credentials_required.other.append(key)


def _route_mount_credentials(mounts: list[dict], result: AnalysisResult) -> None:
    """No-op for parity. The bash skill's mount-routing heredoc is shadowed
    by `echo $DC_VOLUMES | python3 << PYEOF` (heredoc captures stdin), so it
    emits no SSH/KEY/TOK/OTH lines. We match that observed behavior — SSH is
    still detected via source_scan's ssh-pattern grep + sys-package check.
    """
    return


# ─── orchestrator ─────────────────────────────────────────────────────────────

def detect(repo_path: Path, result: AnalysisResult) -> None:
    """Mutate `result` in place with Dockerfile + devcontainer-derived fields."""

    # ── devcontainer.json ─────────────────────────────────────────────────────
    dc = _parse_devcontainer(repo_path)
    result.container.capabilities = dc["capabilities"]
    result.container.volumes = dc["volumes"]
    result.container.env = dc["container_env"]
    result.container.post_start = dc["post_start"]
    result.container.post_create = dc["post_create"]
    result.container.remote_user = dc["remote_user"]

    # Merge .vscode/extensions.json recommendations after dc extensions, dedup
    exts = list(dc["extensions"])
    seen_exts = set(exts)
    for e in _vscode_extensions(repo_path):
        if e not in seen_exts:
            exts.append(e)
            seen_exts.add(e)
    result.container.extensions = exts

    # ── chain decomposition + in-repo script enumeration ──────────────────────
    ps_chain, ps_scripts = _process_chain(repo_path, dc["post_start"])
    pc_chain, pc_scripts = _process_chain(repo_path, dc["post_create"])
    result.container.post_start_chain = ps_chain
    result.container.post_create_chain = pc_chain
    result.container.init_scripts = sorted(set(ps_scripts + pc_scripts))

    # ── Dockerfile parsing (aggregate over all dockerfiles) ───────────────────
    df_base = ""
    sys_pkgs: list[str] = []
    binaries: list[str] = []
    js_global: list[str] = []
    py_installs: list[str] = []
    go_installs: list[str] = []
    df_env: list[str] = []
    df_ports: list[int] = []

    for df in _find_dockerfiles(repo_path):
        try:
            parsed = _parse_dockerfile(df.read_text(errors="ignore"))
        except Exception:
            continue
        if not df_base and parsed["base"]:
            df_base = parsed["base"]
        sys_pkgs.extend(parsed["packages"])
        binaries.extend(parsed["binaries"])
        js_global.extend(parsed["js_global"])
        py_installs.extend(parsed["py_installs"])
        go_installs.extend(parsed["go_installs"])
        df_env.extend(parsed["env_vars"])
        df_ports.extend(parsed["expose_ports"])

    result.dockerfile_base = df_base
    result.system_packages = sorted({p for p in sys_pkgs if _PKG_NAME_RE.match(p)})
    result.extra_binaries = binaries
    result.global_js_packages = js_global
    result.dockerfile_python_installs = py_installs
    result.dockerfile_go_installs = go_installs

    # ── ports.inbound (EXPOSE + docker-compose + devcontainer.forwardPorts) ───
    inbound: set[int] = set()
    inbound.update(df_ports)
    inbound.update(_compose_inbound_ports(repo_path))
    for p in dc["forward_ports"]:
        # forwardPorts entries can be int or "host:container" string
        if isinstance(p, int):
            inbound.add(p)
        elif isinstance(p, str):
            for m in re.finditer(r"\b([0-9]{2,5})\b", p):
                inbound.add(int(m.group(1)))
    result.ports.inbound = sorted(inbound)

    # ── env_vars (.env.example + Dockerfile ENV + devcontainer.containerEnv) ──
    env_set: set[str] = set()
    env_keys_from_envfiles: list[str] = []
    for fname in _ENV_FILES:
        f = repo_path / fname
        if f.is_file():
            keys = _env_keys_from_file(f)
            env_keys_from_envfiles.extend(keys)
            env_set.update(keys)
    env_set.update(v for v in df_env if _ENV_NAME_ANY_RE.match(v))
    env_set.update(k for k in dc["container_env"].keys() if _ENV_NAME_ANY_RE.match(k))
    result.env_vars = sorted(env_set)

    # ── credentials_required (env-var routing + volume routing) ───────────────
    # Source-code env-pattern routing + GitHub Actions secrets are
    # source_scan.py's responsibility.
    _route_env_credentials(env_keys_from_envfiles, result)
    _route_mount_credentials(dc["volumes"], result)

    result.credentials_required.api_keys = sorted(set(result.credentials_required.api_keys))
    result.credentials_required.tokens = sorted(set(result.credentials_required.tokens))
    result.credentials_required.other = sorted(set(result.credentials_required.other))
