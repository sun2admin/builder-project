---
name: Finalized plugin lists per container layer
description: Which Anthropic plugins go in base vs coding layers of the plugin container stack
type: project
---

## claude-anthropic-base-plugins-container

General-purpose plugins useful for any Claude project:

- `claude-code-setup`
- `claude-md-management`
- `explanatory-output-style`
- `hookify`
- `learning-output-style`
- `math-olympiad`
- `playground`
- `ralph-loop`
- `session-report`
- `skill-creator`

**Why hookify is in base (not coding):** Useful for any project to configure behavioral guardrails. Python 3.7+ stdlib only, no external dependencies.

## claude-anthropic-coding-plugins-container

Software development focused plugins (extends base):

**Code flow:**
- `code-review`
- `code-simplifier`
- `commit-commands`
- `feature-dev`
- `pr-review-toolkit`
- `security-guidance`

**Dev tooling:**
- `agent-sdk-dev`
- `frontend-design`
- `mcp-server-dev`
- `plugin-dev`

**LSP (language servers):**
- `clangd-lsp`
- `csharp-lsp`
- `gopls-lsp`
- `jdtls-lsp`
- `kotlin-lsp`
- `lua-lsp`
- `php-lsp`
- `pyright-lsp`
- `ruby-lsp`
- `rust-analyzer-lsp`
- `swift-lsp`
- `typescript-lsp`

**Note on LSP plugins:** These may download language server binaries at install time — verify sizes before baking into the image.

## claude-anthropic-ext-plugins-container

Third-party external plugins (extends base). All from `external_plugins/` in claude-plugins-official:
asana, context7, discord, fakechat, firebase, github, gitlab, greptile, imessage, laravel-boost, linear, playwright, serena, telegram, terraform

**Why excluded from base:** Third-party, not Anthropic-controlled. Some (imessage, telegram, discord) have messaging platform access.

## claude-anthropic-all-plugins-container

Extends coding layer + adds all external plugins.

**How to apply:** Use these lists when writing the Dockerfile `claude plugin install` commands for each repo.