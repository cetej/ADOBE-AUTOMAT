#!/bin/bash
# stop-failure.sh — Error recovery guidance when API errors kill a turn
# Hook event: StopFailure
# Logs the failure and suggests recovery steps

BUDGET_FILE=".claude/memory/budget.md"
CHECKPOINT_FILE=".claude/memory/checkpoint.md"

echo "Session stopped due to API error."

# Check if there's active budget (task in progress)
if [ -f "$BUDGET_FILE" ] && grep -q "in_progress\|standard\|deep\|light" "$BUDGET_FILE" 2>/dev/null; then
    echo "Active task detected. Consider running /checkpoint save before retrying."
fi

# Check if checkpoint exists
if [ -f "$CHECKPOINT_FILE" ] && [ -s "$CHECKPOINT_FILE" ]; then
    echo "Checkpoint exists — next session can resume from where you left off."
fi
