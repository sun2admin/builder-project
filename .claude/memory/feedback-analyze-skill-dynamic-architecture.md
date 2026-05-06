---
name: analyze-repo dynamic architecture principle
description: Core design rule for analyze-repo skill — dynamic context-aware detection, never hardcoded filter lists. Includes noise-reduction patterns from gstack testing.
type: feedback
originSessionId: 2e9e7091-4fd0-4a26-8cf6-f6d5cb3e6087
---
**Authoritative reference:** `.claude/skills/analyze-repo/DETECTION_PRINCIPLES.md` in builder-project repo. Always read that file before modifying skill detection logic. This memory is a summary; that file is canonical and version-controlled with the skill.

Never use hardcoded filter/comparison lists in analyze-repo skill. Use dynamic, context-aware detection instead.

**Why:** Hardcoded lists (domain blocklists, KNOWN_TOOLS, STDLIB_PY, etc.) grow forever, miss novel cases, and encode assumptions that belong to the repo being analyzed — not the skill itself. The skill should determine what a repo has, not compare against pre-judged lists.

**How to apply:**

**Domains/external services:** Classify by WHERE the URL appears (file type + code context), not WHAT the domain is.
- Source code HTTP call patterns (fetch, requests.get, curl, http.Get) → high confidence
- Config/env files (.env.example, docker-compose) → high confidence
- Firewall scripts → confirmed
- README code fences → medium (owner documented usage)
- README service-keyword prose → medium
- README badge lines ([![...]) → skip (not a runtime service)
- No blocklist. Localhost/internal IPs (127.*, 0.0.0.0) are the only always-skip items.

**Tool detection:** Use dynamic command extraction from shell AST patterns instead of KNOWN_TOOLS list.
- Get bash builtins + keywords from `bash -c 'compgen -b; compgen -k'` at runtime
- Extract first token after delimiters (;, |, &&, ||, (, {, newline) in script files
- Detect `command -v X`, `which X`, `type X` patterns (explicit dependency checks)
- Detect shebangs `#!/usr/bin/env X`
- For CI: parse `uses:` action names dynamically — strip setup-/install- prefixes and -action/-toolchain/-cache suffixes to derive tool name
- For CI run: blocks: extract command tokens from the run content

**Python stdlib:** Use `sys.stdlib_module_names` (Python 3.10+) or `pkgutil.iter_modules([stdlib_path])` fallback. Never hardcode.

**Node stdlib:** Use `node -e "require('module').builtinModules"` at runtime. Never hardcode.

**Reference file:** `tool-deps.json` lives alongside the skill and caches tool → system dependency mappings discovered via `apt-cache show`. The skill reads and writes this file. Cache avoids re-querying apt on every run.

**Noise reduction rules (all verified against gstack):**
- **No dots in DELIMITERS_RE character class** — Linux shell commands never contain dots. Allowing dots causes JS property access (`JSON.parse`, `j.category`), Go methods, and Python attributes to match as commands.
- **Uppercase-first filter** — `not cmd[0].isupper()` eliminates Python class names, TypeScript interfaces, and proper nouns. The existing `not cmd.isupper()` only caught ALL-CAPS constants.
- **Makefile recipe-only filter** — only TAB-indented lines contain shell commands. Target definition lines at column 0 are labels, not tools. Use `makefile_recipes_only()` before passing to `extract_commands`.
- **GitHub Actions `${{ }}` stripping** — strip context expressions before extracting from `run:` blocks; they look like dotted command tokens to the delimiter regex.
- **Inline interpreter script stripping** — strip `node/bun/deno/python3?/ruby/perl -e "..."` inline scripts before extracting CI commands. Inline JS/Python keywords (`await`, `const`, `console`) are not shell tools. Pattern: `re.sub(r'(?:node|bun|deno|python3?|ruby|perl)\s+(?:-\w+\s+)*-[ec]\s+(?:"[^"]*"|\'[^\']*\')', ' __INLINE_SCRIPT__ ', run_content)`
- **EXPLICIT_DEP_RE len check** — apply `len(cmd) > 1` guard to `command -v / which / type` matches, same as DELIMITERS_RE path.

**Acceptable residual noise:** Complex repos (like gstack) with heavy embedded scripting will still have many false positives in `inferred.tools`. This is acceptable because all false positives resolve to `apt_package: null` in tool-deps.json and never reach the actionable `system_deps` output. The noise is visual clutter only.

**Legitimate hardcoding (not a violation):**
- `CRED_*` routing suffixes (`_KEY$`, `_SECRET$`, `_TOKEN$`, `_PAT$`) — industry standard naming conventions, not filter lists
- `TOML_SECTIONS` for Cargo — defined by Cargo's fixed schema spec
- Localhost/127.*/0.0.0.0 for domain skip — always-true network addresses, not domain opinions
