---
name: new-plugin-layer skill output clarity
description: Don't repeat menu options in explanatory text after displaying the menu
type: feedback
originSessionId: e6384b3e-ac51-4f33-8f44-0569a8ce8ee7
---
**FIXED**: All interactive menus in new-plugin-layer now display cleanly without redundant explanatory text. Menus show options, then prompt for input directly.

**Why:** Verbose explanatory text makes interaction harder to scan and wastes vertical space. Menus are self-documenting.

**How to apply:** In all future interactive skills, display menu options clearly with no preceding explanation of choices. Follow immediately with the input prompt.