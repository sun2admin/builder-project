# deploy-stack — Plan Stub

**Status:** Bookmarked. Sub-plan of `build-workflow-stack-composition.md`.
**Skill path (planned):** `.claude/skills/deploy-stack/`
**Trigger:** `/deploy-stack` (invoked from `/build-stack` handoff or `/manage-rec-plugins` end prompt, also standalone).

## Scope (responsibilities)

`/deploy-stack` owns every action that turns a `build.json` (or recommended-plugins delta) into running infrastructure:

1. **L3 recommended image — create / update / rebuild.**
   - First-run: create `sun2admin/claude-plugins-recommended` GitHub repo (currently does not exist; `select.py` references it as phantom). Generate Dockerfile + GHA workflow from `recommended-plugins.json`.
   - Subsequent runs: regenerate Dockerfile when `recommended-plugins.json` changes; push; trigger GHA build → publish `ghcr.io/sun2admin/claude-plugins-recommended:latest` (private, OCI source label required).
   - Replaces any need for a manual "create the recommended L3 image" step on the build-stack plan.
2. **Per-build L3 image (non-recommended path)** — when `use_recommended_l3: false`, build/publish the per-build plugin image from staged Dockerfile.
3. **L1/L2 image rebuilds** — when capability cover or AI-CLI variant changes vs published tag.
4. **Plugin source-repo creation** for plugins picked via free entry that lack an existing GHCR image.
5. **Devcontainer rebuild trigger** — VS Code "Rebuild Container" hint or CLI equivalent after image refresh.
6. **OCI source-label backfill** — verify `org.opencontainers.image.source` on every pushed image; warn + offer one-line CI patch when missing (per L3 CLAUDE.md backfill list).

## Inputs

- `builds/<category>/<project>/build.json` (from `/build-stack`) — primary path.
- `recommended-plugins.json` delta (from `/manage-rec-plugins`) — fast path: only step 1 fires.
- Standalone repo path — full pipeline.

## Out of scope

- Plugin selection / recommendation curation (lives in `/manage-rec-plugins`).
- Stack composition / aggregation (lives in `/build-stack` + `tools/build-stack/`).
- Marketplace registry edits (lives in `/manage-known-marketplaces`).

## Open questions

- Build orchestration: local Docker build vs GHA-only (push-and-wait)?
- Idempotency: detect "no change since last deploy" to skip no-op rebuilds.
- Concurrency / lock when multiple deploys race on same image tag.
- Failure recovery: partial deploy (L1 ✓, L3 ✗) — rollback strategy.
- Tag policy: `:latest` always, or content-hash tags + `:latest` alias.

## Resume conditions

Pick up after parent plan steps 7-8 land (compose pipeline + skill body validated end-to-end). `/deploy-stack` should not begin until at least one full `build.json` has produced staged outputs.
