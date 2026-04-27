---
name: claude-code-action and claude-code-security-review placement
description: These are GitHub Actions, not container config — they belong in project repo workflow files, not in any container image layer
type: project
---

`anthropics/claude-code-action` and `anthropics/claude-code-security-review` are GitHub Actions that run in GitHub's CI infrastructure. They are NOT installed into or configured inside a container — they live as workflow YAML files in `.github/workflows/` of a project repo.

They are coding/development specific: automated PR review and security scanning of code changes.

**Why:** They don't belong in any container layer because they're a CI concern, not a container concern.

**How to apply:** Omit from all container layers. Add directly to software dev project repos via the `/new-code-prj` scaffolding skill, which automatically adds both workflow files. General-purpose projects (scaffolded via `/new-general-prj`) do not get these workflows.