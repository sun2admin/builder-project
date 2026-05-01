#!/bin/bash
# analyze-project: Deep scan a GitHub repo for all container stack dependencies
# Usage: analyze-project.sh [owner/repo]
# stdout: path to builds/<owner>/<repo>/analysis.json
# exit 0=success, 1=error

set -euo pipefail

source "$(dirname "$0")/../build-workspace/lib.sh"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
BUILDS_DIR="${REPO_ROOT}/builds"

TEMP_DIR=""
cleanup() { [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]] && rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

# ============================================================================
# Input
# ============================================================================

REPO="${1:-}"
if [[ -z "$REPO" ]]; then
  read_input "GitHub repo (owner/repo): "
  REPO="$input"
fi

if [[ ! "$REPO" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]]; then
  echo -e "${RED}✘ Invalid format. Use owner/repo (e.g. sun2admin/myapp)${NC}" >&2
  exit 1
fi

REPO_OWNER="${REPO%%/*}"
REPO_NAME="${REPO##*/}"

# ============================================================================
# Clone
# ============================================================================

echo -e "\n${BLUE}=== analyze-project: ${REPO} ===${NC}" >&2
echo "" >&2

# Fetch repo metadata from GitHub API before cloning
echo "Fetching repo metadata..." >&2
REPO_META=$(gh api "repos/${REPO}" --jq '{description: .description, language: .language, topics: .topics}' 2>/dev/null || echo '{}')
REPO_DESC=$(echo "$REPO_META" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('description','') or '')" 2>/dev/null || echo "")
REPO_LANG=$(echo "$REPO_META" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('language','') or '')" 2>/dev/null || echo "")

echo "Cloning (shallow)..." >&2
TEMP_DIR=$(mktemp -d "/tmp/analyze-${REPO_NAME}-XXXXX")

if ! gh repo clone "$REPO" "$TEMP_DIR" -- --depth=1 --quiet 2>/dev/null; then
  echo -e "${RED}✘ Clone failed. Check repo name and access.${NC}" >&2
  exit 1
fi

echo -e "${GREEN}✓ Cloned${NC}" >&2
echo "" >&2

cd "$TEMP_DIR"

# Query Node.js for its own builtin module list (used later to filter ts_imports)
NODE_BUILTINS_JSON="[]"
if command -v node >/dev/null 2>&1; then
  NODE_BUILTINS_JSON=$(node -e "console.log(JSON.stringify(require('module').builtinModules))" 2>/dev/null || echo "[]")
fi
export AP_NODE_BUILTINS="$NODE_BUILTINS_JSON"

# ============================================================================
# Project purpose (README first paragraph + repo description)
# ============================================================================

echo "  → purpose..." >&2
PURPOSE=""
if [[ -f "README.md" ]]; then
  PURPOSE=$(python3 -c "
import re, sys
txt = open('README.md').read()
# Strip badges, HTML, headings — get first real paragraph
lines = txt.splitlines()
paras = []
buf = []
for l in lines:
    stripped = l.strip()
    if not stripped:
        if buf:
            paras.append(' '.join(buf))
            buf = []
    elif not stripped.startswith(('#', '!', '<', '|', '[', '>')):
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', stripped)
        clean = re.sub(r'[*_\`]', '', clean)
        clean = re.sub(r'<[^>]+>', '', clean)  # strip inline HTML tags
        if len(clean) > 20:
            buf.append(clean)
if buf:
    paras.append(' '.join(buf))
print(next((p for p in paras if len(p) > 30), '')[:300])
" 2>/dev/null || echo "")
fi
# Fall back to API description when README yields nothing or only a short snippet
# (<80 chars suggests a dialogue fragment or transitional notice, not a real description)
[[ ( -z "$PURPOSE" || ${#PURPOSE} -lt 80 ) && -n "$REPO_DESC" ]] && PURPOSE="$REPO_DESC"

# ============================================================================
# Languages and runtime
# ============================================================================

echo "  → languages..." >&2
LANGUAGES=()
[[ -f "package.json" ]]                                                              && LANGUAGES+=("node")
[[ -f "requirements.txt" || -f "setup.py" || -f "Pipfile" || -f "pyproject.toml" ]] && LANGUAGES+=("python")
[[ -f "Gemfile" ]]                                                                    && LANGUAGES+=("ruby")
[[ -f "go.mod" ]]                                                                     && LANGUAGES+=("go")
[[ -f "Cargo.toml" ]]                                                                 && LANGUAGES+=("rust")
[[ -f "pom.xml" || -f "build.gradle" || -f "build.gradle.kts" ]]                    && LANGUAGES+=("java")
[[ -f "composer.json" ]]                                                              && LANGUAGES+=("php")
[[ -n "$(find . -name '*.sh' -not -path './.git/*' | head -1)" ]]                   && LANGUAGES+=("shell")

# Alternate runtimes / package managers
RUNTIME_EXTRAS=()
if grep -rl "#!/usr/bin/env bun" . --include="*.ts" --include="*.js" --include="*.sh" 2>/dev/null | head -1 | grep -q .; then
  RUNTIME_EXTRAS+=("bun")
fi
[[ -f "bun.lockb" || -f "bun.lock" ]] && RUNTIME_EXTRAS+=("bun")
[[ -f "deno.json" || -f "deno.lock" || -f "deno.jsonc" ]] && RUNTIME_EXTRAS+=("deno")
[[ -f "pnpm-lock.yaml" ]] && RUNTIME_EXTRAS+=("pnpm")
[[ -f "yarn.lock" ]] && RUNTIME_EXTRAS+=("yarn")
RUNTIME_EXTRAS=($(printf '%s\n' "${RUNTIME_EXTRAS[@]:-}" | sort -u))

# bun implies node even without package.json
if printf '%s\n' "${RUNTIME_EXTRAS[@]:-}" | grep -q "^bun$"; then
  printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^node$" || LANGUAGES+=("node")
fi

# File-scan fallback: always run for secondary languages regardless of primary_language.
# A Shell repo can still have substantial Python scripts, a Go repo can have TS tooling, etc.
# Threshold >2 files avoids false positives from single utility scripts.
if ! printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^python$"; then
  _pycount=$(find . -name "*.py" -not -path "./.git/*" -not -path "*/node_modules/*" -not -path "*/.venv/*" 2>/dev/null | wc -l)
  [[ "$_pycount" -gt 2 ]] && LANGUAGES+=("python")
fi
if ! printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^node$"; then
  _tscount=$(find . \( -name "*.ts" -o -name "*.js" \) -not -path "./.git/*" -not -path "*/node_modules/*" 2>/dev/null | wc -l)
  [[ "$_tscount" -gt 2 ]] && LANGUAGES+=("node")
fi
if ! printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^go$"; then
  _gocount=$(find . -name "*.go" -not -path "./.git/*" 2>/dev/null | wc -l)
  [[ "$_gocount" -gt 2 ]] && LANGUAGES+=("go")
fi

# Runtime versions (best-effort)
NODE_VER=""
GO_VER=""
PYTHON_VER=""
if [[ -f "package.json" ]]; then
  NODE_VER=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('engines',{}).get('node',''))" 2>/dev/null || true)
fi
# Fallback: .nvmrc or .node-version
if [[ -z "$NODE_VER" ]]; then
  for nvmf in .nvmrc .node-version; do
    [[ -f "$nvmf" ]] && NODE_VER=$(tr -d 'v \n' < "$nvmf" 2>/dev/null | head -1) && break
  done
fi
if [[ -f "go.mod" ]]; then
  GO_VER=$(grep "^go " go.mod 2>/dev/null | awk '{print $2}' | head -1 || true)
fi

# ============================================================================
# Devcontainer — authoritative source for packages, capabilities, env, volumes
# ============================================================================

echo "  → devcontainer..." >&2
DC_SYSTEM_PACKAGES="[]"
DC_CAPABILITIES="[]"
DC_VOLUMES="[]"
DC_CONTAINER_ENV="{}"
DC_POST_START=""
DC_POST_CREATE=""
DC_EXTENSIONS="[]"
DC_FORWARD_PORTS="[]"
DC_REMOTE_USER=""
DC_BASE_IMAGE=""

if [[ -f ".devcontainer/devcontainer.json" ]]; then
  DC_DATA=$(python3 << 'PYEOF'
import json, re, sys, os

def parse_jsonc(text):
    # Strip // line comments and /* */ block comments
    text = re.sub(r'//[^\n]*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return json.loads(text)

try:
    raw = open('.devcontainer/devcontainer.json').read()
    d = parse_jsonc(raw)

    caps = [a.replace('--cap-add=','').replace('--cap-add ','').strip()
            for a in d.get('runArgs', [])
            if '--cap-add' in a]

    mounts = []
    for m in d.get('mounts', []):
        if isinstance(m, str) and 'source=' in m:
            parts = dict(p.split('=',1) for p in m.split(',') if '=' in p)
            mounts.append({'name': parts.get('source',''), 'target': parts.get('target',''), 'type': parts.get('type','volume')})
        elif isinstance(m, dict):
            mounts.append({'name': m.get('source',''), 'target': m.get('target',''), 'type': m.get('type','volume')})

    exts = (d.get('customizations',{}).get('vscode',{}).get('extensions') or [])
    ports = d.get('forwardPorts', [])

    result = {
        'capabilities': caps,
        'volumes': mounts,
        'container_env': d.get('containerEnv', {}),
        'post_start': d.get('postStartCommand', ''),
        'post_create': d.get('postCreateCommand', ''),
        'extensions': exts,
        'forward_ports': ports,
        'remote_user': d.get('remoteUser', ''),
    }
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e), 'capabilities': [], 'volumes': [], 'container_env': {}, 'post_start': '', 'post_create': '', 'extensions': [], 'forward_ports': [], 'remote_user': ''}))
PYEOF
)
  DC_CAPABILITIES=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('capabilities',[])))" 2>/dev/null || echo "[]")
  DC_VOLUMES=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('volumes',[])))" 2>/dev/null || echo "[]")
  DC_CONTAINER_ENV=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('container_env',{})))" 2>/dev/null || echo "{}")
  DC_POST_START=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('post_start',''))" 2>/dev/null || echo "")
  DC_POST_CREATE=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('post_create',''))" 2>/dev/null || echo "")
  DC_EXTENSIONS=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('extensions',[])))" 2>/dev/null || echo "[]")
  DC_FORWARD_PORTS=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('forward_ports',[])))" 2>/dev/null || echo "[]")
  DC_REMOTE_USER=$(echo "$DC_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('remote_user',''))" 2>/dev/null || echo "")
fi

# VS Code extensions from .vscode/extensions.json (supplement devcontainer)
if [[ -f ".vscode/extensions.json" ]]; then
  VSCODE_EXTS=$(python3 -c "
import json, re
raw = open('.vscode/extensions.json').read()
raw = re.sub(r'//[^\n]*','',raw)
d = json.loads(raw)
print(json.dumps(d.get('recommendations', [])))
" 2>/dev/null || echo "[]")
  # Merge with DC_EXTENSIONS
  DC_EXTENSIONS=$(python3 -c "
import json, sys
a = json.loads('${DC_EXTENSIONS}')
b = json.loads('${VSCODE_EXTS}')
merged = list(dict.fromkeys(a + b))
print(json.dumps(merged))
" 2>/dev/null || echo "$DC_EXTENSIONS")
fi

# ============================================================================
# Dockerfile — authoritative system packages, base image, extra binaries
# ============================================================================

echo "  → system packages..." >&2
SYS_PACKAGES_RAW=""
DOCKERFILE_BASE=""
EXTRA_BINARIES=()

while IFS= read -r dockerfile; do
  # Use Python to join backslash-continuation lines before parsing
  parsed=$(python3 - "$dockerfile" << 'PYEOF'
import sys, re

path = sys.argv[1]
try:
    lines = open(path).readlines()
except:
    sys.exit(0)

# Join continuation lines
joined = []
buf = ""
for line in lines:
    stripped = line.rstrip()
    if stripped.endswith("\\"):
        buf += stripped[:-1] + " "
    else:
        buf += stripped
        joined.append(buf)
        buf = ""
if buf:
    joined.append(buf)

# Base image
for l in joined:
    m = re.match(r'FROM\s+(\S+)', l)
    if m:
        print("BASE:" + m.group(1))
        break

# apt-get/apt/apk packages
for l in joined:
    if re.search(r'apt-get install|apt install|apk add', l):
        # strip flags and commands
        pkgs = re.sub(r'.*(?:install|add)\s+', '', l)
        pkgs = re.sub(r'&&.*', '', pkgs)
        for p in pkgs.split():
            if re.match(r'^[a-z][a-z0-9._+-]{1,}$', p) and p not in ('apt-get','apt','apk'):
                print("PKG:" + p)

# wget/curl binary downloads
for l in joined:
    if re.search(r'wget|curl\s+-[oL]', l):
        m = re.search(r'releases/download/[^/\s]+/([^\s"\'\\]+)', l)
        if m:
            print("BIN:" + m.group(1))
PYEOF
)

  while IFS= read -r pline; do
    case "$pline" in
      BASE:*) [[ -z "$DOCKERFILE_BASE" ]] && DOCKERFILE_BASE="${pline#BASE:}" ;;
      PKG:*)  SYS_PACKAGES_RAW+=" ${pline#PKG:}" ;;
      BIN:*)  EXTRA_BINARIES+=("${pline#BIN:}") ;;
    esac
  done <<< "$parsed"

done < <(find . \( -name "Dockerfile" -o -name "Dockerfile.*" -o -name "*.dockerfile" \) -not -path "./.git/*" 2>/dev/null)

SYS_PACKAGES=$(echo "$SYS_PACKAGES_RAW" | tr ' ' '\n' \
  | { grep -E '^[a-z][a-z0-9._+-]{1,}$' || true; } | sort -u \
  | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" \
  2>/dev/null || echo "[]")

# ============================================================================
# Libraries
# ============================================================================

echo "  → libraries..." >&2
NODE_LIBS="[]"
PYTHON_LIBS="[]"
GO_LIBS="[]"
RUST_LIBS="[]"
RUST_VER=""

# Rust: scan all Cargo.toml files (workspace + member crates)
if [[ -n "$(find . -name "Cargo.toml" -not -path "./.git/*" 2>/dev/null | head -1)" ]]; then
  RUST_DATA=$(python3 << 'PYEOF'
import re, json
from pathlib import Path

TOML_SECTIONS = {'workspace', 'package', 'lib', 'bin', 'features', 'profile', 'patch', 'replace', 'badges', 'lints'}

deps = set()
rust_ver = ''

for cargo in Path('.').rglob('Cargo.toml'):
    if '.git' in str(cargo):
        continue
    try:
        content = cargo.read_text(errors='ignore')
        # rust-version from any Cargo.toml
        if not rust_ver:
            m = re.search(r'rust-version\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                rust_ver = m.group(1)
        # deps: name = "version" or name = { version = ...}
        for m in re.finditer(r'^([a-z][a-z0-9_-]+)\s*=\s*[\{"\'0-9]', content, re.MULTILINE):
            name = m.group(1)
            if name not in TOML_SECTIONS:
                deps.add(name)
        # [dependencies.name] table form
        for m in re.finditer(r'^\[(?:workspace\.)?(?:dev-|build-)?dependencies\.([a-z][a-z0-9_-]+)\]', content, re.MULTILINE):
            deps.add(m.group(1))
    except:
        pass

print(json.dumps({'rust_version': rust_ver, 'deps': sorted(deps)[:80]}))
PYEOF
)
  RUST_VER=$(echo "$RUST_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('rust_version',''))" 2>/dev/null || echo "")
  RUST_LIBS=$(echo "$RUST_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('deps',[])))" 2>/dev/null || echo "[]")
fi

if [[ -f "package.json" ]]; then
  NODE_LIBS=$(python3 -c "
import json
try:
  d = json.load(open('package.json'))
  deps = list((d.get('dependencies') or {}).keys()) + list((d.get('devDependencies') or {}).keys())
  print(json.dumps(deps[:60]))
except: print('[]')
" 2>/dev/null || echo "[]")
fi

if [[ -f "requirements.txt" ]]; then
  PYTHON_LIBS=$({ grep -v "^#\|^$\|^-" requirements.txt || true; } 2>/dev/null \
    | sed 's/[>=<!=;[].*//' \
    | tr '[:upper:]' '[:lower:]' \
    | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines[:60]))" \
    2>/dev/null || echo "[]")
fi

if [[ -f "go.mod" ]]; then
  GO_LIBS=$(grep "^\s" go.mod 2>/dev/null \
    | awk '{print $1}' | grep "/" \
    | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines[:60]))" \
    2>/dev/null || echo "[]")
fi

# ============================================================================
# Ports (inbound: EXPOSE/listen; outbound: derived from external services)
# ============================================================================

echo "  → ports..." >&2
INBOUND_PORTS_RAW=""
INBOUND_PORTS_RAW+=$(find . \( -name "Dockerfile" -o -name "Dockerfile.*" \) -not -path "./.git/*" 2>/dev/null \
  | xargs grep -h "^EXPOSE" 2>/dev/null | grep -oP '\d+' || true)
INBOUND_PORTS_RAW+=" "
INBOUND_PORTS_RAW+=$(find . -name "docker-compose*.yml" -o -name "docker-compose*.yaml" 2>/dev/null \
  | xargs grep -h "^\s*-\s*['\"]?[0-9]*:[0-9]" 2>/dev/null | grep -oP '\b[0-9]{2,5}\b' | head -20 || true)
# forward ports from devcontainer
INBOUND_PORTS_RAW+=$(echo "$DC_FORWARD_PORTS" | python3 -c "import sys,json; ports=json.load(sys.stdin); print(' '.join(str(p) for p in ports))" 2>/dev/null || echo "")

INBOUND_PORTS=$(echo "$INBOUND_PORTS_RAW" | tr ' ' '\n' \
  | { grep -E '^[0-9]{2,5}$' || true; } | sort -un \
  | python3 -c "import sys,json; print(json.dumps([int(l) for l in sys.stdin if l.strip()]))" \
  2>/dev/null || echo "[]")

# ============================================================================
# External services — firewall scripts are the most authoritative source
# ============================================================================

echo "  → external services..." >&2
EXT_DOMAINS=()
EXT_SOURCE="source_scan"

# Priority 1: firewall/network init scripts
while IFS= read -r script; do
  # Extract quoted domain strings
  while IFS= read -r domain; do
    [[ "$domain" =~ \. ]] && EXT_DOMAINS+=("$domain")
  done < <(grep -oP '"[a-z0-9][a-z0-9.-]+\.[a-z]{2,}"' "$script" 2>/dev/null | tr -d '"' || true)
done < <(find . -name "init-firewall*" -o -name "firewall*.sh" -o -name "setup-network*.sh" -o -name "init-network*.sh" 2>/dev/null | grep -v ".git")

[[ ${#EXT_DOMAINS[@]} -gt 0 ]] && EXT_SOURCE="init-firewall.sh"

# Priority 2: context-aware scan — classify by file type and code context, no blocklist
# Docs (README/md) provide the owner's stated baseline; source code confirms runtime usage
if [[ ${#EXT_DOMAINS[@]} -eq 0 ]]; then
  while IFS= read -r domain; do
    [[ -n "$domain" ]] && EXT_DOMAINS+=("$domain")
  done < <(python3 << 'PYEOF_DOMAINS'
import re
from pathlib import Path

domain_re   = re.compile(r'https?://([a-z0-9][a-z0-9.-]+\.[a-z]{2,})', re.IGNORECASE)
badge_re    = re.compile(r'\[!\[')                         # [![alt](img)](url) badge lines
comment_re  = re.compile(r'^\s*(?://|#|\*|<!--)')          # comment lines in source files
code_fence  = re.compile(r'```[\s\S]*?```', re.DOTALL)     # fenced code blocks in markdown

SERVICE_KW  = {'api', 'service', 'endpoint', 'webhook', 'connect', 'host',
               'server', 'baseurl', 'base_url', 'origin', 'remote', 'backend'}
HTTP_CALL   = re.compile(
    r'(?:fetch|axios\s*\.\s*(?:get|post|put|delete|patch|request)'
    r'|requests\s*\.\s*(?:get|post|put|delete|patch|head)'
    r'|urllib(?:\.request)?\s*\.\s*(?:urlopen|Request)'
    r'|http(?:s)?\.(?:Get|Post|Do|NewRequest)'
    r'|grpc\.(?:Dial|NewClient)'
    r'|curl\b|wget\b'
    r')\s*[\s(\'"]', re.IGNORECASE
)

SKIP_DIRS   = {'.git', 'node_modules', 'vendor', '.venv', '__pycache__', 'gen', 'generated'}
SKIP_FILES  = {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
               'Cargo.lock', 'Gemfile.lock', 'composer.lock'}
ALWAYS_SKIP = re.compile(r'^(?:localhost|127\.|192\.168\.|10\.|0\.0\.0\.0|::1)')

domains_high   = set()  # source HTTP calls, config files, env files
domains_medium = set()  # README code blocks, service-keyword prose

for f in Path('.').rglob('*'):
    if not f.is_file():
        continue
    if any(d in SKIP_DIRS for d in f.parts):
        continue
    if f.name in SKIP_FILES or f.suffix == '.svg':
        continue

    try:
        content = f.read_text(errors='ignore')
    except Exception:
        continue

    # ── Markdown / docs: owner-stated baseline ──────────────────────────────
    if f.suffix in {'.md', '.rst', '.txt', '.adoc'}:
        # Code fences: owner demonstrated runtime usage → medium confidence
        for block in code_fence.findall(content):
            for m in domain_re.finditer(block):
                d = m.group(1).lower()
                if not ALWAYS_SKIP.match(d):
                    domains_medium.add(d)
        # Prose: lines with service-related keywords, skip badge lines
        prose = code_fence.sub('', content)
        for line in prose.splitlines():
            if badge_re.search(line):
                continue
            if any(kw in line.lower() for kw in SERVICE_KW):
                for m in domain_re.finditer(line):
                    d = m.group(1).lower()
                    if not ALWAYS_SKIP.match(d):
                        domains_medium.add(d)
        continue

    # ── Source code: only non-comment lines with HTTP call patterns ──────────
    if f.suffix in {'.py', '.ts', '.js', '.go', '.rs', '.sh', '.bash'}:
        for line in content.splitlines():
            if comment_re.match(line):
                continue
            if HTTP_CALL.search(line):
                for m in domain_re.finditer(line):
                    d = m.group(1).lower()
                    if not ALWAYS_SKIP.match(d):
                        domains_high.add(d)
        continue

    # ── Config / env files: all URLs are runtime config ─────────────────────
    if (f.suffix in {'.yml', '.yaml', '.toml', '.cfg', '.ini', '.conf'}
            or f.name.startswith('.env') or f.suffix == '.json'):
        for m in domain_re.finditer(content):
            d = m.group(1).lower()
            if not ALWAYS_SKIP.match(d):
                domains_high.add(d)

# Emit: high-confidence first, then medium; sorted, deduplicated
for d in sorted(domains_high | domains_medium):
    print(d)
PYEOF_DOMAINS
  )
fi

EXT_DOMAINS=($(printf '%s\n' "${EXT_DOMAINS[@]:-}" | sort -u))

# ============================================================================
# Credentials and auth requirements
# ============================================================================

echo "  → credentials..." >&2
CRED_API_KEYS=()
CRED_TOKENS=()
CRED_SSH=false
CRED_OTHER=()

# From .env.example and similar — exclusive routing: each var goes to exactly one bucket
for f in .env.example .env.sample .env.template .env.test .env.development; do
  [[ -f "$f" ]] && while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    if [[ "$key" =~ _KEY$|_SECRET$ ]]; then
      CRED_API_KEYS+=("$key")
    elif [[ "$key" =~ _TOKEN$|_PAT$ ]]; then
      CRED_TOKENS+=("$key")
    elif [[ "$key" =~ ^(DATABASE_URL|REDIS_URL|MONGODB_URI|POSTGRES|MYSQL|SMTP_|SENDGRID|TWILIO|STRIPE|DATADOG|SENTRY) ]]; then
      CRED_OTHER+=("$key")
    fi
  done < <(grep -oP '^[A-Z_][A-Z0-9_]*' "$f" 2>/dev/null || true)
done

# From GitHub Actions workflow secrets
while IFS= read -r secret; do
  [[ -n "$secret" ]] || continue
  if [[ "$secret" =~ _KEY$ ]]; then
    CRED_API_KEYS+=("$secret")
  elif [[ "$secret" =~ _TOKEN$|^GITHUB_TOKEN$ ]]; then
    CRED_TOKENS+=("$secret")
  else
    CRED_OTHER+=("$secret")
  fi
done < <(find . -path "*/.github/workflows/*.yml" -o -path "*/.github/workflows/*.yaml" 2>/dev/null \
  | xargs grep -h "secrets\." 2>/dev/null \
  | grep -oP '(?<=secrets\.)[A-Z_]+' | sort -u || true)

# From source code environment variable reads
# Exclude dependency trees — they contain env var patterns from unrelated packages
_EXCL="--exclude-dir=node_modules --exclude-dir=vendor --exclude-dir=.venv --exclude-dir=__pycache__"
while IFS= read -r var; do
  [[ -n "$var" ]] || continue
  [[ "$var" =~ _KEY$ ]] && CRED_API_KEYS+=("$var") || true
  [[ "$var" =~ _TOKEN$ ]] && CRED_TOKENS+=("$var") || true
done < <(
  grep -rh "process\.env\." . --include="*.ts" --include="*.js" $_EXCL 2>/dev/null \
    | grep -oP '(?<=process\.env\.)[A-Z_]+(?:KEY|TOKEN|SECRET|PAT)' || true
  grep -rh "os\.environ" . --include="*.py" $_EXCL 2>/dev/null \
    | grep -oP '(?<=os\.environ\.get\(.|os\.environ\[.)[A-Z_]+' || true
  grep -rh "os\.Getenv" . --include="*.go" $_EXCL 2>/dev/null \
    | grep -oP '(?<=os\.Getenv\(")[A-Z_]+' || true
)

# SSH detection — exclude dependency dirs and lock files to avoid false positives
if grep -rq "ssh\|id_rsa\|known_hosts\|ssh-keygen\|ssh-agent\|SSH_AUTH_SOCK" . \
    --include="*.sh" --include="*.ts" --include="*.js" --include="*.py" \
    --include="*.json" --include="*.yml" --include="*.yaml" \
    --exclude="package-lock.json" --exclude="yarn.lock" --exclude="pnpm-lock.yaml" \
    --exclude="Cargo.lock" --exclude="Gemfile.lock" --exclude="composer.lock" \
    $_EXCL 2>/dev/null; then
  CRED_SSH=true
fi
# SSH outbound port as strong signal too
echo "$INBOUND_PORTS_RAW $SYS_PACKAGES_RAW" | grep -q "openssh\|ssh " && CRED_SSH=true || true

# Deduplicate
CRED_API_KEYS=($(printf '%s\n' "${CRED_API_KEYS[@]:-}" | sort -u))
CRED_TOKENS=($(printf '%s\n' "${CRED_TOKENS[@]:-}" | sort -u))
CRED_OTHER=($(printf '%s\n' "${CRED_OTHER[@]:-}" | sort -u))

# ============================================================================
# MCP servers
# ============================================================================

echo "  → MCP servers..." >&2
MCP_SERVERS=()

# .mcp.json at root or .claude/
for f in .mcp.json .claude/mcp.json .claude/settings.json .claude/settings.local.json; do
  [[ -f "$f" ]] && while IFS= read -r srv; do
    [[ -n "$srv" ]] && MCP_SERVERS+=("$srv")
  done < <(python3 -c "
import json
d = json.load(open('$f'))
servers = d.get('mcpServers', {})
for name in servers.keys():
    print(name)
" 2>/dev/null || true)
done

# @modelcontextprotocol/* packages in package.json
if [[ -f "package.json" ]]; then
  while IFS= read -r pkg; do
    [[ -n "$pkg" ]] && MCP_SERVERS+=("$pkg")
  done < <(python3 -c "
import json
d = json.load(open('package.json'))
all_deps = {**d.get('dependencies',{}), **d.get('devDependencies',{})}
for k in all_deps:
    if '@modelcontextprotocol' in k or 'mcp-server' in k:
        print(k)
" 2>/dev/null || true)
fi

MCP_SERVERS=($(printf '%s\n' "${MCP_SERVERS[@]:-}" | sort -u))

# ============================================================================
# Claude plugins
# ============================================================================

echo "  → Claude plugins..." >&2
CLAUDE_PLUGINS=()

if [[ -f ".claude-plugin/marketplace.json" ]]; then
  while IFS= read -r plugin; do
    [[ -n "$plugin" ]] && CLAUDE_PLUGINS+=("$plugin")
  done < <(python3 -c "
import json
d = json.load(open('.claude-plugin/marketplace.json'))
for p in d.get('plugins', []):
    print(p.get('name',''))
" 2>/dev/null || true)
fi

# Count plugin directories too
plugin_count=$(find . -maxdepth 2 -name "SKILL.md" -o -name "PLUGIN.md" 2>/dev/null | wc -l | tr -d ' ')

# ============================================================================
# Env vars (combined: .env.example + devcontainer containerEnv + source patterns)
# ============================================================================

echo "  → env vars..." >&2
ENV_VARS_RAW=""
for f in .env.example .env.sample .env.template .env.test; do
  [[ -f "$f" ]] && ENV_VARS_RAW+=$(grep -oP '^[A-Z_][A-Z0-9_]*(?==)' "$f" 2>/dev/null | tr '\n' ' ' || true)
done

# Dockerfile ENV
ENV_VARS_RAW+=$(find . \( -name "Dockerfile" -o -name "Dockerfile.*" \) -not -path "./.git/*" 2>/dev/null \
  | xargs grep -h "^ENV " 2>/dev/null \
  | awk '{print $2}' | grep -oP '^[A-Z_][A-Z0-9_]*' | tr '\n' ' ' || true)

# containerEnv from devcontainer
ENV_VARS_RAW+=$(echo "$DC_CONTAINER_ENV" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(' '.join(d.keys()))
" 2>/dev/null || echo "")

ENV_VARS=$(echo "$ENV_VARS_RAW" | tr ' ' '\n' \
  | { grep -E '^[A-Z_][A-Z0-9_]{1,}$' || true; } | sort -u \
  | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" \
  2>/dev/null || echo "[]")

# ============================================================================
# Browser / test tools
# ============================================================================

echo "  → browser tools..." >&2
BROWSER_TOOLS=()
ALL_TEXT=$(cat package.json requirements.txt Pipfile pyproject.toml go.mod 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
echo "$ALL_TEXT" | grep -q "playwright"  && BROWSER_TOOLS+=("playwright")
echo "$ALL_TEXT" | grep -q "puppeteer"   && BROWSER_TOOLS+=("puppeteer")
echo "$ALL_TEXT" | grep -q "selenium"    && BROWSER_TOOLS+=("selenium")
echo "$ALL_TEXT" | grep -q "cypress"     && BROWSER_TOOLS+=("cypress")

# ============================================================================
# Source-code inference: tools/commands used in repo files
# Runs always; critical when no Dockerfile is present
# ============================================================================

echo "  → source inference..." >&2

INFERRED_SOURCE=$(python3 << 'PYEOF'
import re, subprocess, sys, sysconfig, pkgutil, json, os
from pathlib import Path

# ── Shell builtins + keywords — queried from bash, not hardcoded ─────────────
try:
    _builtins_raw = subprocess.check_output(
        ['bash', '-c', 'compgen -b; compgen -k'],
        text=True, stderr=subprocess.DEVNULL)
    SHELL_BUILTINS = set(_builtins_raw.split())
except Exception:
    SHELL_BUILTINS = {'if','then','else','elif','fi','for','while','until',
                      'do','done','case','esac','in','function','time',
                      'echo','cd','export','source','read','return','exit',
                      'break','continue','eval','exec','set','unset','local',
                      'declare','typeset','readonly','shift','getopts','trap',
                      'wait','jobs','fg','bg','kill','umask','ulimit','alias',
                      'unalias','hash','help','let','printf','test','true','false'}

# Words that appear in command position but are not installable tools
NOISE = {'true','false','null','yes','no','on','off','ok','all','none',
         'default','main','not','new','get','set','add','push','pull',
         'run','build','test','clean','init','use','with','from','to',
         'at','by','as','of','is','it','do','done','pass','fail','skip',
         'start','stop','restart','status','check','list','show','help',
         'version','install','uninstall','update','upgrade','config',
         'create','delete','remove','apply','deploy','release','tag'}

DELIMITERS_RE   = re.compile(
    r'(?:^|[;|&({`\n])\s*(?:sudo\s+|env\s+(?:[A-Z_]+=\S+\s+)*)?'
    r'([a-zA-Z][a-zA-Z0-9_.-]*)',
    re.MULTILINE)
EXPLICIT_DEP_RE = re.compile(r'(?:command\s+-[vV]|which|type)\s+([a-zA-Z][a-zA-Z0-9_.-]*)')
SHEBANG_RE      = re.compile(r'#!/usr/bin/env\s+([a-zA-Z][a-zA-Z0-9_.-]*)')
COMMENT_RE      = re.compile(r'^\s*#')

def extract_commands(content):
    lines = [l for l in content.splitlines() if not COMMENT_RE.match(l)]
    clean = '\n'.join(lines)
    cmds = set()
    for m in DELIMITERS_RE.finditer(clean):
        cmd = m.group(1)
        if (cmd and len(cmd) > 1
                and cmd not in SHELL_BUILTINS
                and cmd not in NOISE
                and not cmd.isupper()
                and '/' not in cmd
                and not cmd[0].isdigit()):
            cmds.add(cmd)
    for m in EXPLICIT_DEP_RE.finditer(clean):
        cmd = m.group(1)
        if cmd and len(cmd) > 1 and cmd not in SHELL_BUILTINS:
            cmds.add(cmd)
    return cmds

# ── Collect shell script files ────────────────────────────────────────────────
SKIP_DIRS = {'.git', 'node_modules', 'vendor', '.venv', '__pycache__'}
shell_files = []
for f in Path('.').rglob('*'):
    if not f.is_file() or any(d in SKIP_DIRS for d in f.parts):
        continue
    if f.suffix in {'.sh', '.bash'}:
        shell_files.append(f)
    elif not f.suffix:
        try:
            hdr = f.read_bytes()[:100]
            if any(s in hdr for s in [b'#!/bin/bash', b'#!/bin/sh',
                                       b'#!/usr/bin/env bash', b'#!/usr/bin/env sh']):
                shell_files.append(f)
        except Exception:
            pass

task_files = [Path(n) for n in
              ['Makefile','makefile','GNUmakefile','Taskfile.yml','Taskfile.yaml',
               'justfile','Justfile']
              if Path(n).exists()]

MAKEFILE_NAMES = {'Makefile', 'makefile', 'GNUmakefile'}

def makefile_recipes_only(content):
    """Return only tab-indented recipe lines from a Makefile.
    Target lines (start at column 0 before ':') are not installable tools;
    only the shell commands they invoke (indented with TAB) are.
    """
    return '\n'.join(l for l in content.splitlines() if l.startswith('\t'))

# ── Dynamic tool extraction ───────────────────────────────────────────────────
tools_found = set()
for f in shell_files + task_files:
    try:
        content = f.read_text(errors='ignore')
        parse_content = makefile_recipes_only(content) if f.name in MAKEFILE_NAMES else content
        tools_found |= extract_commands(parse_content)
        for m in SHEBANG_RE.finditer(content):
            cmd = m.group(1)
            if cmd not in SHELL_BUILTINS:
                tools_found.add(cmd)
    except Exception:
        pass

# ── CI workflows: uses: actions + run: blocks ─────────────────────────────────
ci_tools = set()
STRIP_RE = re.compile(r'^(?:setup|install|action|run)-|-(?:action|toolchain|cache|setup|runner|builder)$')
for wf in Path('.').rglob('*.yml'):
    if '.github' not in str(wf) or any(d in SKIP_DIRS for d in wf.parts):
        continue
    try:
        content = wf.read_text(errors='ignore')
        # Derive tool name dynamically from action name
        for m in re.finditer(r'uses:\s*([^\s@\n]+)', content):
            parts = m.group(1).lower().split('/')
            if len(parts) >= 2:
                tool = STRIP_RE.sub('', parts[1]).strip('-')
                if tool and len(tool) > 1 and re.match(r'^[a-z][a-z0-9_.-]+$', tool):
                    ci_tools.add(tool)
        # Extract commands from run: blocks.
        # Strip ${{ ... }} GitHub Actions expressions first — they contain
        # context variable paths (github.event.issue.body, secrets.TOKEN) that
        # look like command tokens to the delimiter regex but are not shell.
        for m in re.finditer(r'^\s+run:\s*[|>]?\s*\n((?:[ \t]+.+\n?)*)', content, re.MULTILINE):
            run_content = re.sub(r'\$\{\{[^}]*\}\}', ' __EXPR__ ', m.group(1))
            # Only keep simple lowercase shell-style tokens (hyphens ok, no dots, no mixed caps)
            ci_tools |= {t for t in extract_commands(run_content)
                         if re.match(r'^[a-z][a-z0-9_-]+$', t)}
    except Exception:
        pass

# ── Python imports — stdlib from Python itself, not a hardcoded list ──────────
stdlib_py = frozenset(getattr(sys, 'stdlib_module_names', frozenset()))
if not stdlib_py:
    try:
        stdlib_path = sysconfig.get_python_lib(standard_lib=True)
        stdlib_py = frozenset(m.name for m in pkgutil.iter_modules([stdlib_path]))
    except Exception:
        stdlib_py = frozenset()
    stdlib_py = stdlib_py | frozenset(sys.builtin_module_names)

LOCAL_MODULES = (
    {p.name for p in Path('.').iterdir() if p.is_dir() and not p.name.startswith('.')}
    | {p.stem for p in Path('.').glob('*.py')}
)

py_imports_found = set()
for py in Path('.').rglob('*.py'):
    if any(d in SKIP_DIRS for d in py.parts):
        continue
    try:
        content = py.read_text(errors='ignore')
        for m in re.finditer(r'^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)', content, re.MULTILINE):
            pkg = m.group(1).split('.')[0]
            if pkg and pkg not in stdlib_py and not pkg.startswith('_') and pkg not in LOCAL_MODULES:
                py_imports_found.add(pkg)
    except Exception:
        pass

# ── TS/JS imports — Node builtins from Node itself, not a hardcoded list ──────
try:
    node_builtins_raw = os.environ.get('AP_NODE_BUILTINS', '[]')
    _node_list = json.loads(node_builtins_raw)
    node_builtins = frozenset(m.replace('node:', '') for m in _node_list)
except Exception:
    node_builtins = frozenset()

ts_imports_found = set()
for tsf in list(Path('.').rglob('*.ts')) + list(Path('.').rglob('*.js')):
    if any(d in SKIP_DIRS for d in tsf.parts):
        continue
    try:
        content = tsf.read_text(errors='ignore')
        for m in re.finditer(r'''(?:import|require)\s*(?:\(['"]|from\s+['"])([@a-zA-Z][^'"]+)['"]''', content):
            pkg = m.group(1).split('/')[0]
            if pkg and not pkg.startswith('.') and pkg not in node_builtins:
                ts_imports_found.add(pkg)
    except Exception:
        pass

# ── Emit ──────────────────────────────────────────────────────────────────────
for t in sorted(tools_found):
    print('TOOL:' + t)
for p in sorted(py_imports_found):
    print('PYIMP:' + p)
for t in sorted(ts_imports_found):
    print('TSIMP:' + t)
for t in sorted(ci_tools):
    print('CITOOL:' + t)
PYEOF
)

INFERRED_TOOLS=()
INFERRED_PY_IMPORTS=()
INFERRED_TS_IMPORTS=()
INFERRED_CI_TOOLS=()

while IFS= read -r line; do
  case "$line" in
    TOOL:*)   INFERRED_TOOLS+=("${line#TOOL:}") ;;
    PYIMP:*)  INFERRED_PY_IMPORTS+=("${line#PYIMP:}") ;;
    TSIMP:*)  INFERRED_TS_IMPORTS+=("${line#TSIMP:}") ;;
    CITOOL:*) INFERRED_CI_TOOLS+=("${line#CITOOL:}") ;;
  esac
done <<< "$INFERRED_SOURCE"

# ============================================================================
# GitHub API usage
# ============================================================================

GITHUB_API="false"
if grep -rq "@octokit\|PyGithub\|go-github\|Octokit\|github\.rest\.\|gh api " . \
    --include="*.json" --include="*.txt" --include="*.py" \
    --include="*.go" --include="*.ts" --include="*.js" --include="*.sh" \
    $_EXCL 2>/dev/null; then
  GITHUB_API="true"
fi

# ============================================================================
# Firewall requirements
# ============================================================================

FIREWALL_REQUIRED="false"
if [[ -n "$(find . -name "init-firewall*" -o -name "firewall*.sh" 2>/dev/null | head -1)" ]]; then
  FIREWALL_REQUIRED="true"
fi
echo "$DC_CAPABILITIES" | grep -qi "NET_ADMIN\|NET_RAW" && FIREWALL_REQUIRED="true" || true

# ============================================================================
# Suggested stack settings
# ============================================================================

# Layer 1 variant (our GHCR image tags): latest | playwright_with_chromium
SUGGESTED_BASE="latest"
[[ ${#BROWSER_TOOLS[@]} -gt 0 ]] && SUGGESTED_BASE="playwright_with_chromium"

# Ideal Dockerfile FROM when creating a dedicated stack for this project
SUGGESTED_DOCKERFILE_FROM="${DOCKERFILE_BASE:-}"
if [[ -z "$SUGGESTED_DOCKERFILE_FROM" ]]; then
  if printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^rust$"; then
    SUGGESTED_DOCKERFILE_FROM="rust:${RUST_VER:-latest}"
  elif printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^go$"; then
    SUGGESTED_DOCKERFILE_FROM="${GO_VER:+golang:${GO_VER}}"; SUGGESTED_DOCKERFILE_FROM="${SUGGESTED_DOCKERFILE_FROM:-golang:latest}"
  elif printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^python$"; then
    SUGGESTED_DOCKERFILE_FROM="${PYTHON_VER:+python:${PYTHON_VER}}"; SUGGESTED_DOCKERFILE_FROM="${SUGGESTED_DOCKERFILE_FROM:-python:3}"
  elif printf '%s\n' "${LANGUAGES[@]:-}" | grep -q "^node$"; then
    SUGGESTED_DOCKERFILE_FROM="${NODE_VER:+node:${NODE_VER}}"; SUGGESTED_DOCKERFILE_FROM="${SUGGESTED_DOCKERFILE_FROM:-node:lts}"
  fi
fi

# ============================================================================
# Serialize to JSON + Markdown
# ============================================================================

echo "" >&2
echo "Generating report..." >&2

mkdir -p "${BUILDS_DIR}/${REPO_OWNER}/${REPO_NAME}"
JSON_FILE="${BUILDS_DIR}/${REPO_OWNER}/${REPO_NAME}/analysis.json"
MD_FILE="${BUILDS_DIR}/${REPO_OWNER}/${REPO_NAME}/analysis.md"
TODAY=$(date +%Y-%m-%d)

# Serialize bash arrays to JSON
_to_json_arr() {
  printf '%s\n' "$@" | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" 2>/dev/null || echo "[]"
}

LANGS_JSON=$(_to_json_arr "${LANGUAGES[@]:-}" )
RUNTIME_EXTRAS_JSON=$(_to_json_arr "${RUNTIME_EXTRAS[@]:-}")
EXT_DOMAINS_JSON=$(_to_json_arr "${EXT_DOMAINS[@]:-}")
CRED_KEYS_JSON=$(_to_json_arr "${CRED_API_KEYS[@]:-}")
CRED_TOKENS_JSON=$(_to_json_arr "${CRED_TOKENS[@]:-}")
CRED_OTHER_JSON=$(_to_json_arr "${CRED_OTHER[@]:-}")
MCP_JSON=$(_to_json_arr "${MCP_SERVERS[@]:-}")
CLAUDE_PLUGINS_JSON=$(_to_json_arr "${CLAUDE_PLUGINS[@]:-}")
BROWSER_JSON=$(_to_json_arr "${BROWSER_TOOLS[@]:-}")
EXTRA_BIN_JSON=$(_to_json_arr "${EXTRA_BINARIES[@]:-}")
INFERRED_TOOLS_JSON=$(_to_json_arr "${INFERRED_TOOLS[@]:-}")
INFERRED_PY_JSON=$(_to_json_arr "${INFERRED_PY_IMPORTS[@]:-}")
INFERRED_TS_JSON=$(_to_json_arr "${INFERRED_TS_IMPORTS[@]:-}")
INFERRED_CI_TOOLS_JSON=$(_to_json_arr "${INFERRED_CI_TOOLS[@]:-}")

export AP_SKILL_DIR="$SKILL_DIR"
export AP_REPO="$REPO" AP_PROJECT="$REPO_NAME" AP_TODAY="$TODAY"
export AP_PURPOSE="$PURPOSE" AP_REPO_LANG="$REPO_LANG"
export AP_DOCKERFILE_BASE="$DOCKERFILE_BASE"
export AP_LANGS="$LANGS_JSON" AP_RUNTIME_EXTRAS="$RUNTIME_EXTRAS_JSON"
export AP_NODE_VER="$NODE_VER" AP_GO_VER="$GO_VER" AP_PYTHON_VER="$PYTHON_VER"
export AP_SYS_PKGS="$SYS_PACKAGES" AP_EXTRA_BINS="$EXTRA_BIN_JSON"
export AP_NODE_LIBS="$NODE_LIBS" AP_PYTHON_LIBS="$PYTHON_LIBS" AP_GO_LIBS="$GO_LIBS"
export AP_INBOUND_PORTS="$INBOUND_PORTS"
export AP_EXT_DOMAINS="$EXT_DOMAINS_JSON" AP_EXT_SOURCE="$EXT_SOURCE"
export AP_ENV_VARS="$ENV_VARS"
export AP_BROWSER="$BROWSER_JSON" AP_GITHUB_API="$GITHUB_API"
export AP_FIREWALL_REQUIRED="$FIREWALL_REQUIRED"
export AP_DC_CAPS="$DC_CAPABILITIES" AP_DC_VOLUMES="$DC_VOLUMES"
export AP_DC_CONTAINER_ENV="$DC_CONTAINER_ENV"
export AP_DC_POST_START="$DC_POST_START" AP_DC_POST_CREATE="$DC_POST_CREATE"
export AP_DC_EXTENSIONS="$DC_EXTENSIONS" AP_DC_REMOTE_USER="$DC_REMOTE_USER"
export AP_CRED_KEYS="$CRED_KEYS_JSON" AP_CRED_TOKENS="$CRED_TOKENS_JSON"
export AP_CRED_SSH="$CRED_SSH" AP_CRED_OTHER="$CRED_OTHER_JSON"
export AP_MCP_SERVERS="$MCP_JSON" AP_CLAUDE_PLUGINS="$CLAUDE_PLUGINS_JSON"
export AP_PLUGIN_COUNT="$plugin_count"
export AP_BASE="$SUGGESTED_BASE"
export AP_INFERRED_TOOLS="$INFERRED_TOOLS_JSON"
export AP_INFERRED_PY="$INFERRED_PY_JSON"
export AP_INFERRED_TS="$INFERRED_TS_JSON"
export AP_INFERRED_CI_TOOLS="$INFERRED_CI_TOOLS_JSON"
export AP_RUST_LIBS="$RUST_LIBS" AP_RUST_VER="$RUST_VER"
export AP_SUGGESTED_DOCKERFILE_FROM="$SUGGESTED_DOCKERFILE_FROM"
export AP_JSON_FILE="$JSON_FILE" AP_MD_FILE="$MD_FILE"

python3 << 'PYEOF'
import json, os, subprocess

def e(key, fallback="[]"):   return json.loads(os.environ.get(key, fallback))
def s(key, fallback=""):     return os.environ.get(key, fallback)
def b(key):                  return os.environ.get(key, "false") == "true"

# ── Dependency resolution: map discovered tools → apt packages ────────────────
# Uses tool-deps.json as a persistent cache alongside the skill to avoid
# re-querying apt on every run.
skill_dir = s("AP_SKILL_DIR")
tool_deps_path = os.path.join(skill_dir, "tool-deps.json") if skill_dir else None

tool_deps_cache = {}
if tool_deps_path and os.path.exists(tool_deps_path):
    try:
        tool_deps_cache = json.load(open(tool_deps_path))
    except Exception:
        pass

all_tools = set(e("AP_INFERRED_TOOLS") + e("AP_INFERRED_CI_TOOLS"))

def _apt_resolve(tool):
    """Return {'apt_package': str|None, 'apt_depends': [str]} for a tool name."""
    try:
        r = subprocess.run(['apt-cache', 'show', tool],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            deps = []
            for line in r.stdout.splitlines():
                if line.startswith('Depends:'):
                    for dep in line[len('Depends:'):].strip().split(','):
                        name = dep.strip().split()[0].rstrip(',')
                        if name and not name.startswith('$') and '|' not in name:
                            deps.append(name)
            return {'apt_package': tool, 'apt_depends': deps}
        # Not a direct package name — try to find what provides the binary
        r2 = subprocess.run(['dpkg', '-S', f'*/bin/{tool}'],
                            capture_output=True, text=True, timeout=5)
        if r2.returncode == 0:
            pkg = r2.stdout.split(':')[0].strip()
            return {'apt_package': pkg, 'apt_depends': []}
    except Exception:
        pass
    return {'apt_package': None, 'apt_depends': []}

cache_updated = False
for tool in sorted(all_tools):
    if tool not in tool_deps_cache:
        tool_deps_cache[tool] = _apt_resolve(tool)
        cache_updated = True

if cache_updated and tool_deps_path:
    try:
        with open(tool_deps_path, 'w') as f:
            json.dump(tool_deps_cache, f, indent=2, sort_keys=True)
    except Exception:
        pass

# Build system_deps: only tools that resolved to a known apt package
system_deps = {t: tool_deps_cache[t] for t in sorted(all_tools)
               if tool_deps_cache.get(t, {}).get('apt_package')}

rv = {}
for lang, vk in [("node", "AP_NODE_VER"), ("go", "AP_GO_VER"), ("python", "AP_PYTHON_VER"), ("rust", "AP_RUST_VER")]:
    v = s(vk)
    if v: rv[lang] = v

data = {
    "repo":             s("AP_REPO"),
    "project":          s("AP_PROJECT"),
    "analyzed_at":      s("AP_TODAY"),
    "purpose":          s("AP_PURPOSE"),
    "primary_language": s("AP_REPO_LANG"),
    "languages":        e("AP_LANGS"),
    "runtime_extras":   e("AP_RUNTIME_EXTRAS"),
    "runtime_versions": rv,
    "dockerfile_base":  s("AP_DOCKERFILE_BASE"),
    "system_packages":  e("AP_SYS_PKGS"),
    "extra_binaries":   e("AP_EXTRA_BINS"),
    "libraries": {
        "node":   e("AP_NODE_LIBS"),
        "python": e("AP_PYTHON_LIBS"),
        "go":     e("AP_GO_LIBS"),
        "rust":   e("AP_RUST_LIBS"),
    },
    "ports": {
        "inbound":  e("AP_INBOUND_PORTS"),
    },
    "external_services": {
        "domains": e("AP_EXT_DOMAINS"),
        "source":  s("AP_EXT_SOURCE"),
    },
    "env_vars":          e("AP_ENV_VARS"),
    "browser_tools":     e("AP_BROWSER"),
    "github_api_usage":  b("AP_GITHUB_API"),
    "firewall_required": b("AP_FIREWALL_REQUIRED"),
    "container": {
        "capabilities":  e("AP_DC_CAPS"),
        "volumes":       e("AP_DC_VOLUMES"),
        "env":           e("AP_DC_CONTAINER_ENV", "{}"),
        "remote_user":   s("AP_DC_REMOTE_USER"),
        "post_start":    s("AP_DC_POST_START"),
        "post_create":   s("AP_DC_POST_CREATE"),
        "extensions":    e("AP_DC_EXTENSIONS"),
    },
    "credentials_required": {
        "api_keys": e("AP_CRED_KEYS"),
        "tokens":   e("AP_CRED_TOKENS"),
        "ssh":      b("AP_CRED_SSH"),
        "other":    e("AP_CRED_OTHER"),
    },
    "mcp_servers":    e("AP_MCP_SERVERS"),
    "claude_plugins": e("AP_CLAUDE_PLUGINS"),
    "inferred": {
        "tools":      e("AP_INFERRED_TOOLS"),
        "py_imports": e("AP_INFERRED_PY"),
        "ts_imports": e("AP_INFERRED_TS"),
        "ci_tools":   e("AP_INFERRED_CI_TOOLS"),
    },
    "system_deps":   system_deps,
    "suggested": {
        "base_image":       s("AP_BASE"),
        "dockerfile_from":  s("AP_SUGGESTED_DOCKERFILE_FROM"),
        "ai_install":       "claude",
        "plugin_layer":     "",
    }
}

# Dedup: compute which inferred tools are already covered by explicit Dockerfile packages
explicit_pkgs = set(data['system_packages'])
inferred_tools = set(data['inferred']['tools'])
data['inferred']['tools_new'] = sorted(inferred_tools - explicit_pkgs)  # net-new only
data['inferred']['tools_confirmed'] = sorted(inferred_tools & explicit_pkgs)  # already explicit

with open(os.environ["AP_JSON_FILE"], "w") as f:
    json.dump(data, f, indent=2)

# ---- Markdown report ----
def fmt(items, empty="none detected"):
    return ", ".join(str(i) for i in items) if items else empty

def fmt_creds(c):
    parts = []
    if c.get("api_keys"):   parts.append(f"API keys: {', '.join(c['api_keys'])}")
    if c.get("tokens"):     parts.append(f"Tokens: {', '.join(c['tokens'])}")
    if c.get("ssh"):        parts.append("SSH key required")
    if c.get("other"):      parts.append(f"Other: {', '.join(c['other'])}")
    return "\n".join(f"  - {p}" for p in parts) if parts else "  none detected"

def fmt_container(c):
    lines = []
    if c.get("capabilities"):  lines.append(f"  - Docker caps: {', '.join(c['capabilities'])}")
    if c.get("remote_user"):   lines.append(f"  - User: {c['remote_user']}")
    if c.get("post_start"):    lines.append(f"  - postStartCommand: `{c['post_start']}`")
    if c.get("post_create"):   lines.append(f"  - postCreateCommand: `{c['post_create']}`")
    if c.get("volumes"):
        for v in c["volumes"]:
            lines.append(f"  - Volume: `{v.get('name','')}` → `{v.get('target','')}`")
    if c.get("env"):
        for k in c["env"]:
            lines.append(f"  - ENV: `{k}`")
    return "\n".join(lines) if lines else "  standard (no special requirements)"

md = f"""# Dependency Analysis: {data['project']}

**Repo:** {data['repo']}
**Analyzed:** {data['analyzed_at']}
**Purpose:** {data['purpose'] or 'see README'}

---

## Languages & Runtimes
- Languages: {fmt(data['languages'])}
- Runtime extras: {fmt(data['runtime_extras'])}
- Versions: {fmt(list(f'{k} {v}' for k,v in data['runtime_versions'].items()))}
- Base image: `{data['dockerfile_base'] or 'not specified'}`

## System Packages
{fmt(data['system_packages'])}

## Libraries
"""
for lang, libs in data["libraries"].items():
    if libs:
        preview = libs[:12]
        more = f" ... ({len(libs)-12} more)" if len(libs) > 12 else ""
        md += f"  - **{lang}**: {', '.join(str(x) for x in preview)}{more}\n"
if not any(data["libraries"].values()):
    md += "  none detected\n"

md += f"""
## Ports
- Inbound: {fmt([str(p) for p in data['ports']['inbound']])}

## External Services *(source: {data['external_services']['source']})*
{fmt(data['external_services']['domains'])}

## Environment Variables
{fmt(data['env_vars'])}

## Container Requirements
{fmt_container(data['container'])}

## Credentials Required
{fmt_creds(data['credentials_required'])}

## MCP Servers
{fmt(data['mcp_servers'])}

## Claude Plugins
{fmt(data['claude_plugins'])}

## Browser / Test Tools
{fmt(data['browser_tools'])}

## GitHub API Usage
{'Yes' if data['github_api_usage'] else 'No'}

## Firewall Required
{'Yes — NET_ADMIN/NET_RAW capabilities needed' if data['firewall_required'] else 'No'}

## Inferred from Source *(tools/commands found in repo files)*
"""
inf = data['inferred']
has_inferred = inf['tools_new'] or inf['py_imports'] or inf['ts_imports'] or inf.get('ci_tools')
if has_inferred:
    if inf['tools_new']:
        md += f"  - **Tools/binaries (not in Dockerfile)**: {fmt(inf['tools_new'])}\n"
    if inf['tools_confirmed']:
        md += f"  - **Confirmed by Dockerfile**: {fmt(inf['tools_confirmed'])}\n"
    if inf.get('ci_tools'):
        md += f"  - **CI toolchain (GitHub Actions)**: {fmt(inf['ci_tools'])}\n"
    if inf['py_imports']:
        md += f"  - **Python imports**: {fmt(inf['py_imports'])}\n"
    if inf['ts_imports']:
        md += f"  - **TS/JS imports**: {fmt(inf['ts_imports'])}\n"
elif inf['tools_confirmed']:
    md += f"  - all detected tools already declared in Dockerfile: {fmt(inf['tools_confirmed'])}\n"
else:
    md += "  none detected\n"

sys_deps = data.get('system_deps', {})
if sys_deps:
    md += "\n## System Dependencies *(tools → apt packages, via tool-deps.json cache)*\n"
    for tool, info in sys_deps.items():
        pkg = info.get('apt_package', tool)
        deps = info.get('apt_depends', [])
        dep_str = f" (needs: {', '.join(deps[:5])})" if deps else ""
        md += f"  - `{tool}` → `{pkg}`{dep_str}\n"

dockerfile_from = data['suggested'].get('dockerfile_from') or ''
stack_rows = [
    f"| Base image (layer1 variant) | `{data['suggested']['base_image']}` |",
]
if dockerfile_from:
    stack_rows.append(f"| Dockerfile FROM | `{dockerfile_from}` |")
stack_rows += [
    f"| AI CLI | `{data['suggested']['ai_install']}` |",
    f"| Plugin layer | {data['suggested']['plugin_layer'] or '(query dynamically at build time)'} |",
]
md += "\n## Suggested Stack\n| Setting | Value |\n|---|---|\n" + "\n".join(stack_rows) + "\n"

with open(os.environ["AP_MD_FILE"], "w") as f:
    f.write(md)

print(md)
PYEOF

echo "" >&2
echo -e "${GREEN}✓ Saved:${NC}" >&2
echo -e "  JSON: ${JSON_FILE}" >&2
echo -e "  MD:   ${MD_FILE}" >&2
echo "" >&2

echo "$JSON_FILE"
