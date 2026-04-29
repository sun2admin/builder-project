#!/bin/bash
[ -n "$CLAUDE_ENV_FILE" ] && echo "export PATH=\"${CLAUDE_PROJECT_DIR}/scripts/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
exit 0
