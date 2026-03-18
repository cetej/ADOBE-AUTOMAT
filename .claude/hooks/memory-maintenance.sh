#!/usr/bin/env bash
# SessionStart hook: check memory file sizes and warn if maintenance needed
# Threshold: 100 lines (warn), 500 lines (circuit breaker per CLAUDE.md)

MEMORY_DIR=".claude/memory"
WARN_THRESHOLD=100
CRITICAL_THRESHOLD=500
warnings=""

if [ ! -d "$MEMORY_DIR" ]; then
  exit 0
fi

for file in "$MEMORY_DIR"/decisions.md "$MEMORY_DIR"/learnings.md "$MEMORY_DIR"/budget.md "$MEMORY_DIR"/state.md; do
  [ -f "$file" ] || continue
  lines=$(wc -l < "$file" 2>/dev/null | tr -d ' ')
  name=$(basename "$file")

  if [ "$lines" -ge "$CRITICAL_THRESHOLD" ]; then
    warnings="${warnings}[CRITICAL] $name has $lines lines (limit: $CRITICAL_THRESHOLD). Run /scribe maintenance before continuing.\n"
  elif [ "$lines" -ge "$WARN_THRESHOLD" ]; then
    warnings="${warnings}[WARN] $name has $lines lines. Consider running /scribe maintenance soon.\n"
  fi
done

if [ -n "$warnings" ]; then
  echo "=== MEMORY MAINTENANCE NEEDED ==="
  echo -e "$warnings"
fi

exit 0
