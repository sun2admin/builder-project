"""Extract most-recent assistant usage tokens from a Claude Code transcript JSONL.

Usage: python3 tokens.py <transcript_path>
Stdout: three space-separated integers — cache_read cache_creation input_tokens

Returns "0 0 0" when:
  * no path argument is given,
  * the file is missing or unreadable,
  * no `message.usage` entries are found.

Tracks the LAST entry, not the max. /compact's own summarization API call
records the full pre-compact context as one entry; a max-tracker would lock
that as a watermark and never recover after the conversation actually shrinks.
Shared by .claude/hooks/context-warn.sh (uses cache_read only) and
.claude/hooks/statusline.sh (sums all three).
"""
from __future__ import annotations

import json
import sys


def extract(path: str) -> tuple[int, int, int]:
    cr = cc = it = 0
    try:
        with open(path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                msg = d.get("message")
                if not isinstance(msg, dict):
                    continue
                u = msg.get("usage")
                if isinstance(u, dict):
                    cr = u.get("cache_read_input_tokens", 0) or 0
                    cc = u.get("cache_creation_input_tokens", 0) or 0
                    it = u.get("input_tokens", 0) or 0
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        pass
    return cr, cc, it


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1]:
        print("0 0 0")
        sys.exit(0)
    print("%d %d %d" % extract(sys.argv[1]))
