# Dependency Analysis: career-ops

**Repo:** santifer/career-ops
**Analyzed:** 2026-05-01
**Purpose:** Companies use AI to filter candidates. I just gave candidates AI to choose companies.

---

## Languages & Runtimes
- Languages: node, shell
- Runtime extras: none detected
- Versions: none detected
- Base image: `not specified`

## System Packages
none detected

## Libraries
  - **node**: @google/generative-ai, dotenv, js-yaml, playwright

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
apply.workable.com, boards-api.greenhouse.io, careers.cognigy.com, careers.mastercard.com, careers.salesforce.com, janesmith.dev, job-boards.eu.greenhouse.io, job-boards.greenhouse.io, jobs.ashbyhq.com, jobs.lever.co, langfuse.com, liveperson.com, mastercard.wd1.myworkdayjobs.com, openai.com, retool.com, santifer.io, www.canva.com, www.dialpad.com, www.genesys.com, www.getmaxim.ai, www.getzep.com, www.gong.io, www.make.com, www.talkdesk.com, www.twilio.com

## Environment Variables
GEMINI_API_KEY

## Container Requirements
  standard (no special requirements)

## Credentials Required
  - API keys: GEMINI_API_KEY
  - Tokens: GITHUB_TOKEN

## MCP Servers
none detected

## Claude Plugins
career-ops

## Browser / Test Tools
playwright

## GitHub API Usage
No

## Firewall Required
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: just, node, parallel

## Suggested Stack
| Setting | Value |
|---|---|
| Base image (layer1 variant) | `playwright_with_chromium` |
| Dockerfile FROM | `node:lts` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
