---
name: checkpoint
description: Save session state and create a resume prompt for the next session. Use when ending a session, when context is getting large, or when the user says "save progress", "continue later", "checkpoint".
argument-hint: [save / resume / status]
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Checkpoint — Session Continuity Manager

You ensure work survives across session boundaries. You save structured snapshots that allow the next session to resume seamlessly.

## Input

Parse `$ARGUMENTS`:
- **"save"** (default) → Create checkpoint from current session state
- **"resume"** → Read checkpoint and present resume context to user
- **"status"** → Show whether a checkpoint exists and its age
- **"clear"** → Archive checkpoint to state.md history and clear it

## Save Checkpoint

### Step 1: Gather State

Collect from all available sources:

1. **Task state**: Read `.claude/memory/state.md` — active task, subtasks, status
2. **Budget state**: Read `.claude/memory/budget.md` — tier, counters, how much budget remains
3. **Recent decisions**: Read `.claude/memory/decisions.md` — last 3 entries
4. **Git state**: Run these commands:
   ```bash
   git branch --show-current
   git status --short
   git log --oneline -5
   git diff --stat
   ```
5. **Learnings this session**: Read `.claude/memory/learnings.md` — check for entries from today
6. **Implementation plan**: Read `.claude/memory/implementation-plan.md` if it exists

### Step 2: Determine What's Done and What Remains

From the task state:
- List completed subtasks (with one-line summaries)
- List remaining subtasks (with dependencies and method)
- Identify the **immediate next action** — the very first thing the next session should do

### Step 3: Write Checkpoint

Write to `.claude/memory/checkpoint.md`:

```markdown
# Session Checkpoint

**Saved**: <date> <time (approximate)>
**Task**: <goal from state.md>
**Branch**: <current git branch>
**Progress**: <N/M subtasks complete>

## What Was Done This Session

<Bulleted list of completed work, with file paths where relevant>

## What Remains

| # | Subtask | Status | Depends on | Method |
|---|---------|--------|-----------|--------|
<Remaining subtasks from state.md>

## Immediate Next Action

<The single most important thing to do first. Be specific:
 file path, function name, what change to make.>

## Key Context

<Essential information the next session needs to understand WHY
 decisions were made. Keep to 5-10 bullet points max.
 Reference decisions.md entries if detailed rationale exists.>

## Git State

- Branch: <branch>
- Uncommitted changes: <yes/no — if yes, list files>
- Last commit: <hash + message>

## Budget State

- Tier: <tier>
- Agents: <used>/<limit>
- Critics: <used>/<limit>

## Resume Prompt

> <A complete, self-contained prompt that can be given to a fresh
>  Claude session. It should include:
>  1. The overall goal
>  2. Current state (what's done, what's not)
>  3. The immediate next action
>  4. Any critical constraints or decisions
>  5. Reference to files: CLAUDE.md, .claude/memory/state.md,
>     .claude/memory/checkpoint.md
>  Write in English (for Claude). Keep under 300 words.>
```

### Step 4: Notify User

After saving, output:
```
Checkpoint saved. To resume in a new session, paste this:

<the resume prompt from above>
```

## Resume From Checkpoint

When invoked with "resume" (or auto-detected at session start):

1. Read `.claude/memory/checkpoint.md`
2. If empty or missing → report "No checkpoint found"
3. If exists:
   - Display summary: task, progress, immediate next action
   - Ask user: "Resume from checkpoint, or start fresh?"
   - If resume: read all referenced memory files to rebuild context
   - If fresh: run `clear` (archive and delete)

## Status Check

When invoked with "status":

1. Read `.claude/memory/checkpoint.md`
2. If missing → "No checkpoint exists"
3. If exists → show: task name, save date, progress fraction, immediate next action

## Clear Checkpoint

When invoked with "clear":

1. Read `.claude/memory/checkpoint.md`
2. Append summary to `.claude/memory/state.md` under completed tasks history
3. Delete content of checkpoint.md (write empty template)

## Context Health Heuristic

This skill can be called by `/orchestrate` when it suspects context is getting large.
The heuristic signals are:

1. **Subtask progress >70%** — most of the work is behind us, context is heavy
2. **Agent spawns ≥3** — each agent result added significant context
3. **Session has been running for many exchanges** — user and assistant have gone back and forth extensively
4. **Recall degradation** — orchestrator notices it can't remember early details accurately

When auto-triggered by orchestrate, save checkpoint silently and return a one-line status
to the orchestrator (don't interrupt the user's flow).

## Rules

1. **Resume prompt is king** — it must be self-contained. A fresh session with only that prompt and access to the files should be able to continue.
2. **Be specific** — "continue implementing feature" is useless. "Edit `.claude/skills/orchestrate/SKILL.md` line 107, add context health check after subtask completion" is useful.
3. **Don't over-save** — one checkpoint file, always overwritten. Only the latest matters.
4. **Keep checkpoint under 100 lines** — it's a summary, not a full transcript.
5. **Git state matters** — always include branch and uncommitted changes. A session that starts on the wrong branch wastes time.
