#!/bin/bash
# task-completed.sh — Auto-scribe when a task finishes
# Hook event: TaskCompleted
# Reminds to record learnings after agent/skill task completion

STATE_FILE=".claude/memory/state.md"

if [ -f "$STATE_FILE" ]; then
    # Check if there's an active task with done subtasks
    if grep -q "in_progress\|done" "$STATE_FILE" 2>/dev/null; then
        echo "Task completed. Remember to record learnings with /scribe if significant patterns emerged."
    fi
fi
