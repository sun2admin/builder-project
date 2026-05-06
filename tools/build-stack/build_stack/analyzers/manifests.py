"""Language manifest parsers + repo-purpose extraction.

Populates these schema fields:
    purpose, languages, runtime_extras, runtime_versions,
    libraries.{node,python,go,rust}, browser_tools

Source files scanned (per analyze-repo SKILL.md):
    README.md (purpose)
    package.json, requirements.txt, Pipfile, pyproject.toml, setup.py,
    Gemfile, go.mod, Cargo.toml (workspace + members), pom.xml,
    build.gradle, build.gradle.kts, composer.json, .nvmrc, .node-version,
    bun.lockb / bun.lock, deno.json/c, deno.lock, pnpm-lock.yaml, yarn.lock

Mirrors detection rules from `analyze-repo.sh` lines 100-198 + 600-674
+ 1007-1017. Idiomatic Python port (sub-plan OQ3 = (b)).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import AnalysisResult


# Cargo.toml [section] names that aren't dependencies
_CARGO_SECTIONS = {
    "workspace", "package", "lib", "bin", "features", "profile",
    "patch", "replace", "badges", "lints",
}

# Files signalling JS package managers / alt runtimes
_RUNTIME_EXTRA_FILES = {
    "bun.lockb": "bun",
    "bun.lock": "bun",
    "deno.json": "deno",
    "deno.jsonc": "deno",
    "deno.lock": "deno",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
}

_BROWSER_TOOLS = ("playwright", "puppeteer", "selenium", "cypress")


# ─── purpose ──────────────────────────────────────────────────────────────────

def _extract_purpose(readme_text: str) -> str:
    """First substantive paragraph from README, badges/HTML stripped.

    Mirrors bash skill lines 107-129. Returns up to 300 chars.
    """
    paras: list[str] = []
    buf: list[str] = []
    for raw_line in readme_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if buf:
                paras.append(" ".join(buf))
                buf = []
            continue
        if stripped.startswith(("#", "!", "<", "|", "[", ">")):
            continue
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        clean = re.sub(r"[*_`]", "", clean)
        clean = re.sub(r"<[^>]+>", "", clean)
        if len(clean) > 20:
            buf.append(clean)
    if buf:
        paras.append(" ".join(buf))
    return next((p for p in paras if len(p) > 30), "")[:300]


def _detect_purpose(repo_path: Path, repo_description: str) -> str:
    """Purpose from README first; fall back to repo description if README
    yields <80 chars (likely a dialogue fragment, not a real description).
    """
    readme = repo_path / "README.md"
    purpose = ""
    if readme.is_file():
        try:
            purpose = _extract_purpose(readme.read_text(errors="ignore"))
        except Exception:
            pass
    if (not purpose or len(purpose) < 80) and repo_description:
        purpose = repo_description
    return purpose


# ─── languages + runtime extras ───────────────────────────────────────────────

def _detect_languages(repo_path: Path) -> tuple[list[str], list[str]]:
    """Return (languages, runtime_extras), both sorted-unique.

    Languages keyed off manifest presence. File-scan fallback when a
    language has no manifest but >2 source files (avoids false positives
    from single utility scripts).
    """
    langs: set[str] = set()
    if (repo_path / "package.json").is_file():
        langs.add("node")
    if any((repo_path / f).is_file() for f in
           ("requirements.txt", "setup.py", "Pipfile", "pyproject.toml")):
        langs.add("python")
    if (repo_path / "Gemfile").is_file():
        langs.add("ruby")
    if (repo_path / "go.mod").is_file():
        langs.add("go")
    if (repo_path / "Cargo.toml").is_file():
        langs.add("rust")
    if any((repo_path / f).is_file() for f in
           ("pom.xml", "build.gradle", "build.gradle.kts")):
        langs.add("java")
    if (repo_path / "composer.json").is_file():
        langs.add("php")
    if any(repo_path.rglob("*.sh")):
        langs.add("shell")

    # Runtime extras: alt JS package managers + Deno
    extras: set[str] = set()
    for fname, label in _RUNTIME_EXTRA_FILES.items():
        if (repo_path / fname).is_file():
            extras.add(label)
    # Bun via shebang scan
    if _has_bun_shebang(repo_path):
        extras.add("bun")
    # bun implies node
    if "bun" in extras:
        langs.add("node")

    # File-scan fallback for secondary languages (>2 files threshold)
    if "python" not in langs and _count_files(repo_path, "*.py", excludes=("node_modules", ".venv")) > 2:
        langs.add("python")
    if "node" not in langs and _count_files(repo_path, ("*.ts", "*.js"), excludes=("node_modules",)) > 2:
        langs.add("node")
    if "go" not in langs and _count_files(repo_path, "*.go") > 2:
        langs.add("go")

    return sorted(langs), sorted(extras)


def _has_bun_shebang(repo_path: Path) -> bool:
    """True if any .ts/.js/.sh file contains `#!/usr/bin/env bun`.

    Bash uses `grep -rl` which matches anywhere in the file — so a literal
    occurrence in a comment or quoted string also counts. We mirror that.
    """
    for ext in ("*.ts", "*.js", "*.sh"):
        for p in repo_path.rglob(ext):
            if ".git" in p.parts:
                continue
            try:
                if "#!/usr/bin/env bun" in p.read_text(errors="ignore"):
                    return True
            except Exception:
                continue
    return False


def _count_files(repo_path: Path, patterns, *, excludes: tuple[str, ...] = ()) -> int:
    """Count files matching pattern(s), excluding paths containing any of `excludes`."""
    if isinstance(patterns, str):
        patterns = (patterns,)
    count = 0
    for pat in patterns:
        for p in repo_path.rglob(pat):
            parts = set(p.parts)
            if ".git" in parts:
                continue
            if any(ex in p.parts for ex in excludes):
                continue
            count += 1
    return count


# ─── runtime versions ─────────────────────────────────────────────────────────

def _detect_versions(repo_path: Path) -> dict[str, str]:
    """{lang: version} from manifests + version-pin files."""
    versions: dict[str, str] = {}

    # Node: package.json engines.node, fall back to .nvmrc / .node-version
    pkg = repo_path / "package.json"
    if pkg.is_file():
        try:
            pkg_data = json.loads(pkg.read_text())
            ver = (pkg_data.get("engines") or {}).get("node", "")
            if ver:
                versions["node"] = ver
        except Exception:
            pass
    if "node" not in versions:
        for fn in (".nvmrc", ".node-version"):
            f = repo_path / fn
            if f.is_file():
                try:
                    raw = f.read_text().strip().lstrip("v").strip()
                    if raw:
                        versions["node"] = raw
                        break
                except Exception:
                    continue

    # Go: first `^go ` line in go.mod
    gomod = repo_path / "go.mod"
    if gomod.is_file():
        try:
            for line in gomod.read_text().splitlines():
                if line.startswith("go "):
                    parts = line.split()
                    if len(parts) >= 2:
                        versions["go"] = parts[1]
                        break
        except Exception:
            pass

    # Rust version is captured during library scan (rust-version field)
    return versions


# ─── libraries ────────────────────────────────────────────────────────────────

def _detect_libraries(repo_path: Path) -> tuple[dict, str]:
    """Return (libraries dict, rust_version).

    libraries = {node: [...], python: [...], go: [...], rust: [...]}
    Each list capped at 60 entries (80 for rust) — matches bash skill caps.
    """
    libs = {"node": [], "python": [], "go": [], "rust": []}
    rust_version = ""

    # Node
    pkg = repo_path / "package.json"
    if pkg.is_file():
        try:
            d = json.loads(pkg.read_text())
            deps = list((d.get("dependencies") or {}).keys()) + \
                   list((d.get("devDependencies") or {}).keys())
            libs["node"] = deps[:60]
        except Exception:
            pass

    # Python: requirements.txt only (Pipfile/pyproject TODO if needed for parity)
    req = repo_path / "requirements.txt"
    if req.is_file():
        try:
            entries: list[str] = []
            for raw in req.read_text().splitlines():
                line = raw.strip().lower()
                if not line or line.startswith(("#", "-")):
                    continue
                # Strip version specs and markers
                pkg_name = re.split(r"[>=<!=;\[]", line, maxsplit=1)[0].strip()
                if pkg_name:
                    entries.append(pkg_name)
            libs["python"] = entries[:60]
        except Exception:
            pass

    # Go
    gomod = repo_path / "go.mod"
    if gomod.is_file():
        try:
            entries = []
            for raw in gomod.read_text().splitlines():
                # Bash: `^\s` + first whitespace-delimited word + must contain /
                if not raw[:1].isspace():
                    continue
                stripped = raw.strip()
                first = stripped.split(maxsplit=1)[0] if stripped else ""
                if "/" in first:
                    entries.append(first)
            libs["go"] = entries[:60]
        except Exception:
            pass

    # Rust: scan all Cargo.toml (workspace + member crates)
    rust_deps: set[str] = set()
    for cargo in repo_path.rglob("Cargo.toml"):
        if ".git" in cargo.parts:
            continue
        try:
            content = cargo.read_text(errors="ignore")
            if not rust_version:
                m = re.search(r'rust-version\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    rust_version = m.group(1)
            # name = "version" or name = { version = ...}
            for m in re.finditer(r'^([a-z][a-z0-9_-]+)\s*=\s*[\{"\'0-9]', content, re.MULTILINE):
                name = m.group(1)
                if name not in _CARGO_SECTIONS:
                    rust_deps.add(name)
            # [dependencies.name] / [dev-dependencies.name] / [build-dependencies.name]
            for m in re.finditer(
                r'^\[(?:workspace\.)?(?:dev-|build-)?dependencies\.([a-z][a-z0-9_-]+)\]',
                content, re.MULTILINE,
            ):
                rust_deps.add(m.group(1))
        except Exception:
            continue
    libs["rust"] = sorted(rust_deps)[:80]

    return libs, rust_version


# ─── browser tools ────────────────────────────────────────────────────────────

def _detect_browser_tools(repo_path: Path) -> list[str]:
    """Browser-test tool detection by lowercase substring match across
    common manifest files. Mirrors bash skill lines 1011-1017.
    """
    text_buf: list[str] = []
    for fname in ("package.json", "requirements.txt", "Pipfile",
                  "pyproject.toml", "go.mod"):
        f = repo_path / fname
        if f.is_file():
            try:
                text_buf.append(f.read_text(errors="ignore").lower())
            except Exception:
                continue
    blob = "\n".join(text_buf)
    return [t for t in _BROWSER_TOOLS if t in blob]


# ─── orchestrator ─────────────────────────────────────────────────────────────

def detect(repo_path: Path, result: AnalysisResult, *,
           repo_description: str = "") -> None:
    """Mutate `result` in place with manifest-derived fields.

    `repo_description` is the GitHub repo description (passed by the
    orchestrator via `gh api`); used as fallback when README purpose is
    short or absent.
    """
    result.purpose = _detect_purpose(repo_path, repo_description)
    result.languages, result.runtime_extras = _detect_languages(repo_path)
    result.runtime_versions = _detect_versions(repo_path)

    libs, rust_ver = _detect_libraries(repo_path)
    result.libraries.node = libs["node"]
    result.libraries.python = libs["python"]
    result.libraries.go = libs["go"]
    result.libraries.rust = libs["rust"]
    if rust_ver:
        result.runtime_versions["rust"] = rust_ver

    result.browser_tools = _detect_browser_tools(repo_path)
