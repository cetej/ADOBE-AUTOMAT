#!/usr/bin/env bash
# SessionStart hook: inject active checkpoint into context
# Works with relative paths — portable across synced projects

CHECKPOINT=".claude/memory/checkpoint.md"

if [ ! -f "$CHECKPOINT" ]; then
  exit 0
fi

content=$(cat "$CHECKPOINT" 2>/dev/null)

# Skip if empty or placeholder
if [ -z "$content" ] || echo "$content" | grep -q "No active checkpoint"; then
  exit 0
fi

# Output to stdout → injected into Claude's context
echo "=== ACTIVE CHECKPOINT ==="
echo "$content"
echo "=== Nabídni uživateli pokračování z checkpointu ==="
