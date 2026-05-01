#!/bin/bash
# analyze-project: Scan a GitHub repo for container stack dependencies
# Usage: analyze-project.sh [owner/repo]
# stdout: path to builds/<project>/analysis.json
# exit 0=success, 1=error

set -euo pipefail

source "$(dirname "$0")/../build-workspace/lib.sh"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
BUILDS_DIR="${REPO_ROOT}/builds"

# Guaranteed temp dir cleanup
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

PROJECT="${REPO##*/}"

# ============================================================================
# Clone
# ============================================================================

echo -e "\n${BLUE}=== analyze-project: ${REPO} ===${NC}" >&2
echo "" >&2
echo "Cloning (shallow)..." >&2

TEMP_DIR=$(mktemp -d "/tmp/analyze-${PROJECT}-XXXXX")

if ! gh repo clone "$REPO" "$TEMP_DIR" -- --depth=1 --quiet 2>/dev/null; then
  echo -e "${RED}✘ Clone failed. Check repo name and that you have access.${NC}" >&2
  exit 1
fi

echo -e "${GREEN}✓ Cloned${NC}" >&2
echo "Scanning..." >&2

cd "$TEMP_DIR"

# ============================================================================
# Detect languages
# ============================================================================

LANGUAGES=()
[[ -f "package.json" ]]                                                                 && LANGUAGES+=("node")
[[ -f "requirements.txt" || -f "setup.py" || -f "Pipfile" || -f "pyproject.toml" ]]    && LANGUAGES+=("python")
[[ -f "Gemfile" ]]                                                                       && LANGUAGES+=("ruby")
[[ -f "go.mod" ]]                                                                        && LANGUAGES+=("go")
[[ -f "Cargo.toml" ]]                                                                    && LANGUAGES+=("rust")
[[ -f "pom.xml" || -f "build.gradle" || -f "build.gradle.kts" ]]                       && LANGUAGES+=("java")
[[ -f "composer.json" ]]                                                                 && LANGUAGES+=("php")

# Runtime versions (best-effort)
NODE_VER=""
GO_VER=""
PYTHON_VER=""
if [[ -f "package.json" ]]; then
  NODE_VER=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('engines',{}).get('node',''))" 2>/dev/null || true)
fi
if [[ -f "go.mod" ]]; then
  GO_VER=$(grep "^go " go.mod 2>/dev/null | awk '{print $2}' | head -1 || true)
fi
if [[ -f "pyproject.toml" ]]; then
  PYTHON_VER=$(grep "python_requires\|python-requires" pyproject.toml 2>/dev/null | grep -oP '[\d.]+' | head -1 || true)
fi

# ============================================================================
# Detect libraries
# ============================================================================

NODE_LIBS="[]"
PYTHON_LIBS="[]"
GO_LIBS="[]"

if [[ -f "package.json" ]]; then
  NODE_LIBS=$(python3 -c "
import json, sys
try:
  d = json.load(open('package.json'))
  deps = list((d.get('dependencies') or {}).keys()) + list((d.get('devDependencies') or {}).keys())
  print(json.dumps(deps[:50]))
except Exception as e:
  print('[]')
" 2>/dev/null || echo "[]")
fi

if [[ -f "requirements.txt" ]]; then
  PYTHON_LIBS=$(grep -v "^#\|^$\|^-" requirements.txt 2>/dev/null \
    | sed 's/[>=<!=;].*//' \
    | tr '[:upper:]' '[:lower:]' \
    | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines[:50]))" \
    2>/dev/null || echo "[]")
fi

if [[ -f "go.mod" ]]; then
  GO_LIBS=$(grep "^\s" go.mod 2>/dev/null \
    | awk '{print $1}' \
    | grep "/" \
    | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines[:50]))" \
    2>/dev/null || echo "[]")
fi

# ============================================================================
# Detect system packages
# ============================================================================

SYS_PKGS_RAW=""
while IFS= read -r dockerfile; do
  SYS_PKGS_RAW+=$(grep -h "RUN.*apt-get install\|RUN.*apt install\|RUN.*apk add" "$dockerfile" 2>/dev/null \
    | sed 's/.*install[[:space:]]*//' \
    | sed 's/&&.*//' \
    | sed 's/\\$//' \
    | tr ' ' '\n' \
    | grep -v "^-\|^$\|=\|RUN\|apt\|apk" \
    | tr '\n' ' ' || true)
done < <(find . -name "Dockerfile" -o -name "Dockerfile.*" -o -name "*.dockerfile" 2>/dev/null)

SYS_PACKAGES=$(echo "$SYS_PKGS_RAW" | tr ' ' '\n' | sort -u \
  | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" \
  2>/dev/null || echo "[]")

# ============================================================================
# Detect ports
# ============================================================================

PORTS_RAW=""
# Dockerfile EXPOSE
PORTS_RAW+=$(find . -name "Dockerfile" -o -name "Dockerfile.*" 2>/dev/null \
  | xargs grep -h "^EXPOSE" 2>/dev/null \
  | grep -oP '\d+' || true)
PORTS_RAW+=" "
# docker-compose ports
PORTS_RAW+=$(find . -name "docker-compose*.yml" -o -name "docker-compose*.yaml" 2>/dev/null \
  | xargs grep -h "^\s*-\s*['\"]?[0-9]*:[0-9]" 2>/dev/null \
  | grep -oP '(?<=- ['"'"'"]?)\d+' || true)

PORTS=$(echo "$PORTS_RAW" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -un \
  | python3 -c "import sys,json; print(json.dumps([int(l) for l in sys.stdin if l.strip()]))" \
  2>/dev/null || echo "[]")

# ============================================================================
# Detect env vars
# ============================================================================

ENV_VARS_RAW=""
for f in .env.example .env.sample .env.template .env.test .env.development; do
  [[ -f "$f" ]] && ENV_VARS_RAW+=$(grep -oP '^[A-Z_][A-Z0-9_]*(?==)' "$f" 2>/dev/null | tr '\n' ' ' || true)
done

# Dockerfile ENV
ENV_VARS_RAW+=$(find . -name "Dockerfile" -o -name "Dockerfile.*" 2>/dev/null \
  | xargs grep -h "^ENV " 2>/dev/null \
  | awk '{print $2}' \
  | grep -oP '^[A-Z_][A-Z0-9_]*' \
  | tr '\n' ' ' || true)

ENV_VARS=$(echo "$ENV_VARS_RAW" | tr ' ' '\n' | grep -E '^[A-Z_][A-Z0-9_]+$' | sort -u \
  | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" \
  2>/dev/null || echo "[]")

# ============================================================================
# Detect browser tools + GitHub API usage
# ============================================================================

BROWSER_TOOLS=()
ALL_TEXT=$(cat package.json requirements.txt Pipfile pyproject.toml go.mod Cargo.toml 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
echo "$ALL_TEXT" | grep -q "playwright"  && BROWSER_TOOLS+=("playwright")
echo "$ALL_TEXT" | grep -q "puppeteer"   && BROWSER_TOOLS+=("puppeteer")
echo "$ALL_TEXT" | grep -q "selenium"    && BROWSER_TOOLS+=("selenium")
echo "$ALL_TEXT" | grep -q "cypress"     && BROWSER_TOOLS+=("cypress")

GITHUB_API="false"
if grep -rq "@octokit\|PyGithub\|go-github\|Octokit\|github\.rest\." . \
    --include="*.json" --include="*.txt" --include="*.py" \
    --include="*.go" --include="*.ts" --include="*.js" \
    --include="*.rb" --include="*.toml" 2>/dev/null; then
  GITHUB_API="true"
fi

# ============================================================================
# Derive suggested settings
# ============================================================================

SUGGESTED_BASE="latest"
[[ ${#BROWSER_TOOLS[@]} -gt 0 ]] && SUGGESTED_BASE="playwright_with_chromium"

# ============================================================================
# Serialize to JSON + Markdown
# ============================================================================

mkdir -p "${BUILDS_DIR}/${PROJECT}"
JSON_FILE="${BUILDS_DIR}/${PROJECT}/analysis.json"
MD_FILE="${BUILDS_DIR}/${PROJECT}/analysis.md"
TODAY=$(date +%Y-%m-%d)

BROWSER_JSON=$(printf '%s\n' "${BROWSER_TOOLS[@]:-}" \
  | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" \
  2>/dev/null || echo "[]")

LANGS_JSON=$(printf '%s\n' "${LANGUAGES[@]:-}" \
  | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin if l.strip()]; print(json.dumps(lines))" \
  2>/dev/null || echo "[]")

export AP_REPO="$REPO"
export AP_PROJECT="$PROJECT"
export AP_TODAY="$TODAY"
export AP_LANGS="$LANGS_JSON"
export AP_SYS_PKGS="$SYS_PACKAGES"
export AP_PORTS="$PORTS"
export AP_ENV_VARS="$ENV_VARS"
export AP_BROWSER="$BROWSER_JSON"
export AP_GITHUB_API="$GITHUB_API"
export AP_NODE_LIBS="$NODE_LIBS"
export AP_PYTHON_LIBS="$PYTHON_LIBS"
export AP_GO_LIBS="$GO_LIBS"
export AP_NODE_VER="$NODE_VER"
export AP_GO_VER="$GO_VER"
export AP_PYTHON_VER="$PYTHON_VER"
export AP_BASE="$SUGGESTED_BASE"
export AP_JSON_FILE="$JSON_FILE"
export AP_MD_FILE="$MD_FILE"

python3 << 'PYEOF'
import json, os

def env(key, fallback="[]"):
    return json.loads(os.environ.get(key, fallback))

def env_str(key, fallback=""):
    return os.environ.get(key, fallback)

def env_bool(key):
    return os.environ.get(key, "false") == "true"

rv = {}
for lang, ver_key in [("node", "AP_NODE_VER"), ("go", "AP_GO_VER"), ("python", "AP_PYTHON_VER")]:
    v = env_str(ver_key)
    if v:
        rv[lang] = v

data = {
    "repo":             env_str("AP_REPO"),
    "project":          env_str("AP_PROJECT"),
    "analyzed_at":      env_str("AP_TODAY"),
    "languages":        env("AP_LANGS"),
    "system_packages":  env("AP_SYS_PKGS"),
    "runtime_versions": rv,
    "libraries": {
        "node":   env("AP_NODE_LIBS"),
        "python": env("AP_PYTHON_LIBS"),
        "go":     env("AP_GO_LIBS"),
    },
    "ports":             env("AP_PORTS"),
    "env_vars":          env("AP_ENV_VARS"),
    "browser_tools":     env("AP_BROWSER"),
    "github_api_usage":  env_bool("AP_GITHUB_API"),
    "suggested": {
        "base_image":   env_str("AP_BASE"),
        "ai_install":   "claude",
        "plugin_layer": "",
    }
}

with open(env_str("AP_JSON_FILE"), "w") as f:
    json.dump(data, f, indent=2)

# ---- Markdown ----
def fmt(items, empty="none detected"):
    return ", ".join(str(i) for i in items) if items else empty

def fmt_libs(libs):
    lines = []
    for lang, pkgs in libs.items():
        if pkgs:
            preview = pkgs[:10]
            more = f" ... ({len(pkgs) - 10} more)" if len(pkgs) > 10 else ""
            lines.append(f"  - **{lang}**: {', '.join(preview)}{more}")
    return "\n".join(lines) if lines else "  none detected"

rv_str = ", ".join(f"{k} {v}" for k,v in data["runtime_versions"].items()) or "none detected"

md = f"""# Dependency Analysis: {data['project']}

**Repo:** {data['repo']}
**Analyzed:** {data['analyzed_at']}

## Languages
{fmt(data['languages'])}

## Runtime Versions
{rv_str}

## System Packages
{fmt(data['system_packages'])}

## Libraries
{fmt_libs(data['libraries'])}

## Ports
{fmt([str(p) for p in data['ports']])}

## Environment Variables
{fmt(data['env_vars'])}

## Browser / Test Tools
{fmt(data['browser_tools'])}

## GitHub API Usage
{'Yes' if data['github_api_usage'] else 'No'}

## Suggested Stack
| Setting | Value |
|---|---|
| Base image | `{data['suggested']['base_image']}` |
| AI CLI | `{data['suggested']['ai_install']}` |
| Plugin layer | {data['suggested']['plugin_layer'] or '(query dynamically at build time)'} |
"""

with open(env_str("AP_MD_FILE"), "w") as f:
    f.write(md)

print(md)
PYEOF

echo "" >&2
echo -e "${GREEN}✓ Analysis saved:${NC}" >&2
echo -e "  JSON: ${JSON_FILE}" >&2
echo -e "  MD:   ${MD_FILE}" >&2
echo "" >&2

# Echo JSON path to stdout for skill-to-skill consumption
echo "$JSON_FILE"
