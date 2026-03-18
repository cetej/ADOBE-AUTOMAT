#!/usr/bin/env bash
# Stop hook: remind about /scribe if there's an active task
# Only outputs if state.md has an active task (not placeholder)

STATE=".claude/memory/state.md"

if [ ! -f "$STATE" ]; then
  exit 0
fi

# Check if state has an active task (not just "No active task")
if grep -q "Status: in_progress\|Status: active\|## Current Task" "$STATE" 2>/dev/null; then
  if ! grep -q "No active task\|_No active" "$STATE" 2>/dev/null; then
    # Output to stderr → shown as hook feedback (not injected as context)
    echo "Reminder: Aktivní task detekován. Zapiš rozhodnutí/poznatky pomocí /scribe." >&2
  fi
fi

exit 0
