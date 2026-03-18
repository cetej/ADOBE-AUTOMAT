# Implementation Plan — Orchestration System v2

**Created**: 2026-03-18
**Source**: /watch full scan + user requirements
**Status**: DRAFT — awaiting approval

---

## Overview

Two tracks of work:
- **Track A**: Improvements driven by /watch findings (6 action items)
- **Track B**: Session Continuity System (new capability — user priority)

Estimated total: 5 implementation tasks, complexity tier **standard**.

---

## Track B: Session Continuity System (PRIORITY)

### Problem

Claude Code sessions have finite context windows. When a complex task spans multiple sessions:
- Progress is lost unless manually documented
- No automatic warning when context is running low
- No structured handoff between sessions
- User must manually re-explain context to the next session

### Solution: `/checkpoint` skill + session awareness in `/orchestrate`

#### B1. New Skill: `/checkpoint`

**Purpose**: Save session state so next session can continue seamlessly.

**File**: `.claude/skills/checkpoint/SKILL.md`

**Triggers**:
- User runs `/checkpoint` manually
- Orchestrator detects high context usage (via heuristic — see B2)
- User says "save progress", "I'm ending session", "continue later"

**What it saves** (to `.claude/memory/checkpoint.md`):
```markdown
## Session Checkpoint — <date> <time>

### Task In Progress
<goal, current status, what's done, what remains>

### Active Context
- Branch: <git branch>
- Files modified: <list>
- Uncommitted changes: <yes/no, summary>
- Todo list state: <current todos>

### Next Steps (ordered)
1. <specific next action with file paths>
2. <next action>
3. ...

### Key Decisions Made This Session
<link to decisions.md entries or inline summary>

### Resume Prompt
> <A ready-to-paste prompt the user can give the next session to resume work.
>  Includes goal, current state, and explicit next steps.>
```

**Design details**:
- `allowed-tools`: Read, Write, Edit, Glob, Grep, Bash (for git status/diff)
- `disable-model-invocation`: false (safe — only reads/writes memory)
- Reads: state.md, budget.md, TodoWrite state, git status, git diff --stat
- Writes: checkpoint.md (overwrite — only latest matters)
- Also appends summary to state.md under Active Task

#### B2. Context Awareness in `/orchestrate`

**Modify**: `.claude/skills/orchestrate/SKILL.md`

Add to Phase 4 (Execute), after each subtask completion:

```
### Context Health Check (after each subtask)

Heuristic for "running low on context":
1. Count completed subtasks vs total — if >70% done, context is likely large
2. If orchestrator notices degraded recall of early-session details
3. If session has spawned 4+ agents (each consumes context for results)

When detected:
- Auto-invoke /checkpoint
- Notify user: "Context is getting large. Checkpoint saved. Consider
  starting a new session with the resume prompt if quality degrades."
- Continue working (don't stop unless user says so)
```

#### B3. Session Start Hook (optional, if user wants automation)

**Option A**: Add to `.claude/settings.json` a `SessionStart` hook that prints checkpoint.md contents if it exists:
```json
{
  "hooks": {
    "SessionStart": [{
      "type": "command",
      "command": "cat .claude/memory/checkpoint.md 2>/dev/null || echo 'No checkpoint found.'"
    }]
  }
}
```

**Option B**: Add instruction to CLAUDE.md:
```markdown
## Session Start
At the beginning of each session, read `.claude/memory/checkpoint.md`.
If it exists and has content, offer to resume from the checkpoint.
```

Option B is simpler and doesn't require hooks. Recommend starting with B.

#### B4. Auto-Remind in `/orchestrate`

**Modify**: `.claude/skills/orchestrate/SKILL.md` Phase 0

Add check:
```
### Checkpoint Check (Phase 0, before anything else)

1. Read `.claude/memory/checkpoint.md`
2. If exists and has content:
   - Show user: "Found checkpoint from <date>: <task summary>"
   - Ask: "Resume this task, or start fresh?"
   - If resume: load context from checkpoint, skip to appropriate phase
   - If fresh: archive checkpoint to state.md history, clear checkpoint.md
```

### Implementation Order for Track B

| Step | What | Effort | Depends on |
|------|------|--------|-----------|
| B1 | Create `/checkpoint` skill | medium | — |
| B2 | Add context health check to `/orchestrate` | small | B1 |
| B3 | Add session start instruction to CLAUDE.md | small | B1 |
| B4 | Add checkpoint check to `/orchestrate` Phase 0 | small | B1 |

---

## Track A: Watch-Driven Improvements

### A1. Integrate Agent Teams into `/orchestrate`

**What**: Claude Code now supports Agent Teams (Feb 2026) — multiple independent Claude sessions working in parallel with coordination.

**Change**: Modify `/orchestrate` Phase 4 to detect parallelizable subtasks and use Agent Teams instead of sequential Agent() calls.

**Where**: `.claude/skills/orchestrate/SKILL.md` — Phase 4 (Execute)

**Details**:
- Add decision point: "Are there 2+ independent subtasks with no data dependencies?"
- If yes AND tier is standard/deep: use Agent Teams for parallel execution
- If no: continue with sequential execution
- Update budget tracking to account for parallel agents

**Effort**: medium (requires testing Agent Teams API behavior)
**Priority**: medium — current system works, this is an optimization

### A2. Claude Code Analytics API → `/budget`

**What**: Anthropic released Analytics API for real cost/usage metrics.

**Change**: Add `budget actual` command that fetches real token usage from Analytics API.

**Where**: `.claude/skills/budget/SKILL.md`

**Details**:
- New command: `actual` — fetch real usage data via API
- Compare estimated vs actual costs
- Store in budget.md alongside estimates
- Requires API key configuration (add to CLAUDE.md setup section)

**Effort**: medium
**Priority**: medium — nice for calibrating estimates, not blocking

### A3. TaskCompleted Hook → Auto-Scribe

**What**: New `TaskCompleted` hook event available in Claude Code.

**Change**: Configure hook to auto-run `/scribe complete` when a task finishes.

**Where**: `.claude/settings.json` (or `.claude/settings.local.json`)

**Details**:
```json
{
  "hooks": {
    "TaskCompleted": [{
      "type": "command",
      "command": "echo 'REMINDER: Run /scribe complete to record learnings'"
    }]
  }
}
```

Note: Can't auto-invoke skills from hooks directly. Hook serves as reminder.

**Effort**: small
**Priority**: low — nice automation but scribe is already called by orchestrator

### A4. Plugin System Exploration

**What**: Claude Code Plugin System allows packaging and distributing extensions.

**Change**: Research feasibility of packaging our orchestration system as a plugin.

**Where**: New doc: `.claude/memory/plugin-research.md`

**Details**:
- This is research, not implementation
- Investigate plugin packaging format
- Check if skills + memory can be bundled
- Assess whether marketplace distribution makes sense

**Effort**: small (research only)
**Priority**: low — exploratory

### A5. Project Dependency Audit (from Skill Gap)

**What**: Python 3.8.10, timm 0.6.12, PyTorch 2.1.2 are critically outdated.

**Change**: Create `/dependency-audit` skill (via /skill-generator) that checks versions and produces upgrade plan.

**Where**: New skill: `.claude/skills/dependency-audit/SKILL.md`

**Details**:
- Reads requirements.txt and CLAUDE.md
- Checks PyPI for latest versions
- Identifies breaking changes (Python version requirements, API changes)
- Produces prioritized upgrade plan
- This is a new skill creation, not a direct code change

**Effort**: medium
**Priority**: medium — addresses critical skill gap from learnings.md

---

## Proposed Execution Order

```
Phase 1: Session Continuity (Track B) — PRIORITY
  B1 → B2 → B3 → B4  (sequential, each builds on previous)

Phase 2: Quick Wins (Track A, small effort)
  A3 (TaskCompleted hook)
  A4 (Plugin research)

Phase 3: Medium Improvements (Track A)
  A1 (Agent Teams)  ← can parallel with A2
  A2 (Analytics API)
  A5 (Dependency audit skill)
```

**Estimated complexity**: standard tier (3-4 agents, 2 critic rounds)

---

## Success Criteria

- [ ] `/checkpoint` skill exists and correctly saves/restores session state
- [ ] `/orchestrate` auto-checkpoints when context is large
- [ ] New sessions detect and offer to resume from checkpoints
- [ ] CLAUDE.md updated with session continuity instructions
- [ ] At least A1 or A2 implemented from Track A
- [ ] All changes committed and pushed

---

## Open Questions

1. **Checkpoint format**: Should resume prompt be in English (for Claude) or Czech (for user readability)? → Recommend: English for the prompt, Czech for human-readable summaries
2. **Context heuristic**: Without direct API access to token count, how to detect "running low"? → Subtask count + agent count as proxy; or rely on user/manual trigger
3. **Agent Teams**: Need to verify exact API/syntax — search docs before implementing A1
4. **Hook vs CLAUDE.md**: For session start, hooks are more reliable but less portable. CLAUDE.md works everywhere but depends on Claude reading it. → Start with CLAUDE.md, add hook later if needed
