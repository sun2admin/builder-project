# analyze-project — Testing Strategy

**Read this when changing detection logic, validating gap fixes, or adding
new categories.** Sibling to `DETECTION_PRINCIPLES.md` and `DATA_SCHEMA.md`.

## Test Repo Corpus

Cover diverse repo profiles. Each repo exercises specific failure modes
caught during prior development. Treat as a regression suite.

| Repo | Profile | What it verifies |
|---|---|---|
| `anthropics/claude-code` | Node/bun, Dockerfile, firewall, plugins | System pkgs, domains, capabilities, plugin detection |
| `sun2admin/build-containers-with-claude` | Shell-only, no Dockerfile, credential mounts | Inference path, SSH detection, volume parsing |
| `sun2admin/builder-project` | Multi-layer, mixed shell+YAML | Cross-file inference, layer-aware paths |
| `anthropics/connect-rust` | Rust, Cargo workspace, Taskfile, no Dockerfile | Rust libs (workspace `rglob`), CI tools, suggested FROM |
| `santifer/career-ops` | Node, Playwright, .env.example, data-file URLs | HTML purpose strip, credential dedup, `.nvmrc` |
| `danielrosehill/claude-code-projects-index` | Astro static site, large `package-lock.json` | `node_modules` exclusion, lock-file URL noise filter |
| `anthropics/claude-code-security-review` | GitHub Action, Python+bun, no root manifests | TS stdlib filter, language file-scan fallback |
| `peterkrueck/claude-code-development-kit` | Shell+Python utilities, no manifests | Unconditional language file-scan branch |
| `hesreallyhim/awesome-claude-code` | Python automation, awesome-list README | Blockquote skip, README short-snippet fallback, local module filter |

## Verification Protocol

For each test repo:

1. **Run cleanly:** `bash analyze-project.sh <owner>/<repo>` — exit 0, no errors
2. **JSON parses:** `jq . builds/<owner>/<repo>/analysis.json >/dev/null`
3. **Known facts present:** every fact known by manual inspection appears
   in the right field (not lost, not in wrong category)
4. **No false positives:** no comment text, no string-literal tokens, no
   markdown badges, no lock-file URLs in detected output
5. **Diff vs prior run:** when iterating, `git diff builds/.../analysis.json`
   shows only intended changes — anything else is regression

## Adding New Test Repos

Add a repo when:
- It has a profile combination not yet covered (e.g., first PHP repo, first
  Java repo, first Bazel build, first multi-language monorepo)
- A user-reported bug only reproduces on a specific repo shape — capture it

When adding, append a row to the corpus table with:
- Profile column: terse comma-list of distinguishing features
- Verifies column: which detector code path or noise-reduction guard it
  exercises that no other repo does

## Testing Gap Fixes

Per-gap regression workflow:

1. **Run baseline:** capture `analysis.json` from a repo where the gap is
   reproducible
2. **Apply fix**
3. **Re-run:** diff against baseline. New field/value appears, nothing else
   changes
4. **Run full corpus:** ensure no other test repo's output drifted
5. **Add fixture if needed:** if no existing repo exercises the gap, add a
   minimal fixture under `/tmp/ap-test-<gap>/` and document the input shape
   in the gap's plan entry

## Noise Floor (Acceptable)

`inferred.tools` will always have residual false positives in source-heavy
repos (e.g., gstack). Accept this when:
- All false positives resolve to `apt_package: null` in `tool-deps.json`
- Therefore none reach `system_deps` (the actionable output)
- Visual clutter only, no downstream consumer impact

If a false positive **does** reach `system_deps`, that's a bug in shape
filtering or extraction — fix per `DETECTION_PRINCIPLES.md` noise-reduction
rules.

## Performance Sanity

Corpus run should complete in:
- Per-repo (already-cached tools): < 30s
- Per-repo (cold tool-deps cache): < 2min (apt-cache queries dominate)
- `tool-deps.json` growth: < 50 new entries per unfamiliar repo

Slowdowns past these floors usually indicate:
- New `find` pattern without `-not -path` exclusions (scanning node_modules)
- New `grep -r` without `--exclude-dir` (scanning vendor/.venv)
- Duplicate apt-cache queries (cache write-flag not set correctly)
