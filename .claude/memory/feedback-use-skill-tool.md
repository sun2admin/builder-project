---
name: Always use Skill tool to invoke skills
description: When user invokes a skill with /skillname, use the Skill tool instead of manually implementing the flow
type: feedback
originSessionId: e6384b3e-ac51-4f33-8f44-0569a8ce8ee7
---
When users invoke a skill with `/skillname` syntax, always use the Skill tool to invoke it. Do NOT manually re-implement the skill's interactive flow yourself.

**Why:** Skills are available as executable tools. Manually re-implementing them is redundant, ignores bug fixes/updates in the actual skill, and makes me overlook obvious solutions.

**How to apply:** 
- User types: `/new-plugin-layer`
- I call: `Skill("new-plugin-layer")`
- The skill executes and handles all interaction

This applies to ALL skills that are invoked with `/` syntax. Never manually implement a skill's menu flow.