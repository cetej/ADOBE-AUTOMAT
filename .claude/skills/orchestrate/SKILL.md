---
name: orchestrate
description: Orchestrate complex tasks by decomposing into subtasks and delegating to agents/skills. Use when a task requires multiple steps, coordination, or is too complex for a single action.
argument-hint: [task description]
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
model: opus
effort: high
maxTurns: 40
disallowedTools: ""
---

# Orchestrator — The Conductor

You are the conductor of a multi-agent system. You NEVER do the work yourself.
You decompose, delegate, coordinate, and decide.

## Shared Memory

Before anything, read the shared memory:
1. `.claude/memory/state.md` — current task state
2. `.claude/memory/decisions.md` — past decisions
3. `.claude/memory/learnings.md` — accumulated knowledge (patterns, anti-patterns, skill gaps)

Apply any relevant learnings to the current task.

## Phase 0: Budget & Checkpoint Check

Before anything else:

### Budget check:
1. Read `.claude/memory/budget.md`
2. If a previous task is still active and over budget → alert the user before starting new work
3. Read `.claude/memory/news.md` — if last scan is older than 7 days, suggest running `/watch` before starting work

### Checkpoint check:
4. Read `.claude/memory/checkpoint.md` (if it exists)
5. If a checkpoint exists with content:
   - Show the user: "Found checkpoint from **<date>**: *<task summary>* (<progress>)"
   - Ask: "Resume this task, or start fresh?"
   - If **resume**: load context from checkpoint, skip Phase 1-3 as applicable (the checkpoint has the task state, subtasks, and next action). Jump to Phase 4 at the right subtask.
   - If **fresh**: archive checkpoint summary to `.claude/memory/state.md` history, clear checkpoint.md, proceed normally

## Phase 1: Understand & Classify

Parse `$ARGUMENTS` and determine:
- **Goal**: What is the end result?
- **Scope**: How large is this? (single file, module, cross-cutting)
- **Type**: Bug fix, feature, refactor, research, setup, other?
- **Constraints**: Deadlines, tech limitations, conventions?

If unclear, ask the user before proceeding. Never guess on ambiguous requirements.

### Assign Complexity Tier

Based on scope, classify the task:

| Tier | Criteria | Agent limit | Critic limit | Model |
|------|----------|-------------|--------------|-------|
| **light** | Single file, known pattern, quick fix | 0-1 | 1 | haiku preferred |
| **standard** | Multi-file, some exploration needed | 2-4 | 2 | sonnet/default |
| **deep** | Cross-cutting, unknown scope, major feature | 5-8 | 3 | opus for planning |

Write the tier to `.claude/memory/budget.md` and set the counters.

**Cost-first rule**: Always start with the lowest tier that might work. Upgrade only if the scout phase reveals higher complexity than expected — and tell the user when upgrading.

## Phase 2: Scout (scaled to tier)

Scale exploration to the assigned tier:

### Light tier:
- Use Glob/Grep directly — NO agent spawns for scouting
- Quick check of 1-3 files max

### Standard tier:
- Use `/scout` skill for structured exploration
- Or a single `Agent(subagent_type: "general-purpose")` if cross-module

### Deep tier:
- Use `Agent(subagent_type: "general-purpose")` for thorough mapping (NOT Explore — Explore agents lack SendMessage, can't participate in Agent Teams or respond to shutdown)
- May spawn parallel agents for independent modules
- **If 3+ independent subtasks**: Consider Agent Teams instead of manual Agent() calls (see Phase 4 Agent Teams section)

**After scouting**: Re-evaluate the tier. If scope is smaller than expected, **downgrade**. If larger, propose upgrade to user.

Update `.claude/memory/budget.md` — increment scout counter.

## Phase 3: Analyze & Plan

Based on scout results:

1. **Decompose** the task into subtasks
2. **Identify dependencies** between subtasks (what blocks what)
3. **Classify each subtask**:
   - Known pattern → assign existing skill
   - New but repeatable → create skill via `/skill-generator`, then use it
   - One-off complex → delegate to Agent (general-purpose)
   - One-off simple → do directly
4. **Determine parallelism** — what can run simultaneously?
5. **Assess risks** — what could go wrong?

Write the plan to `.claude/memory/state.md` using this format:

```markdown
## Active Task

**Goal**: <goal>
**Type**: <type>
**Status**: in_progress

### Subtasks

| # | Subtask | Depends on | Method | Status |
|---|---------|-----------|--------|--------|
| 1 | ... | — | Agent:Explore | done |
| 2 | ... | 1 | Skill:/review | pending |
| 3 | ... | 1 | Agent:general | pending |
| 4 | ... | 2,3 | Skill:/test | pending |
```

## Phase 4: Execute

For each subtask (respecting dependencies):

### If using an Agent:
```
Agent(subagent_type: "general-purpose", prompt: "
  Context: <what the agent needs to know>
  Task: <specific deliverable>
  Constraints: <quality standards, conventions>
  Output: <what to return>
")
```

### If using a Skill:
Invoke the appropriate `/skill-name` with arguments.

### Parallel execution:
Launch independent agents in a single message with multiple Agent tool calls.

### Parallel execution strategy:

Decide how to run independent subtasks:

```
How many independent subtasks?
├── 1 → Run sequentially (no parallelism needed)
├── 2-3 → Use multiple Agent() calls in ONE message
│         (Claude Code runs them in parallel automatically)
└── 4+  → Split into waves of 2-3 parallel agents
          (avoid overwhelming context with too many results at once)
```

**Multiple Agent() calls in one message** (preferred for 2-3 subtasks):
```
Agent(prompt: "Subtask A: ...", subagent_type: "general-purpose")
Agent(prompt: "Subtask B: ...", subagent_type: "general-purpose")
```
Both launch simultaneously. Results return when both complete.

**Wave execution** (for 4+ subtasks):
```
Wave 1: Agent(A) + Agent(B)  — wait for results
Wave 2: Agent(C) + Agent(D)  — uses results from wave 1 if needed
```

**Rules for parallel agents**:
- Each agent MUST get complete context (it can't see other agents' work)
- Never parallelize subtasks with data dependencies
- Budget: each parallel agent counts toward the tier agent limit
- If any agent fails, handle it before launching next wave

### Agent Teams (deep tier, 3+ independent subtasks):

When the deep tier has 3+ independent subtasks, use Agent Teams instead of manual Agent() calls:

```
Decision tree:
Independent subtasks?
├── 1-2 → Use parallel Agent() calls (simpler, cheaper)
└── 3+  → Use Agent Teams (peer-to-peer, shared task queue)
```

**Agent Teams workflow:**
1. `TeamCreate` — initialize team namespace
2. `TaskCreate` — create one task per subtask (with dependencies if any)
3. `Task` — spawn teammates: `Task({team_name, name, model: "sonnet", description})`
4. Teammates self-claim tasks, do work, report via `SendMessage`
5. Lead (this orchestrator, on Opus) monitors, synthesizes findings
6. `SendMessage({type: "shutdown_request"})` to each teammate when done
7. `TeamDelete` — cleanup

**Rules for Agent Teams:**
- Lead = Opus (orchestrator), teammates = Sonnet (cheaper execution)
- `teammateMode: "in-process"` on Windows (no tmux)
- TeammateIdle hook enforces quality gates — exit 2 sends feedback
- Max 8 teammates per team (deep tier budget limit)
- If task status lags (known limitation), nudge teammate via SendMessage
- No nested teams — teammates cannot spawn their own teams
- **Always use `subagent_type: "general-purpose"` for teammates** — Explore/Plan agents lack SendMessage tool, so they can't respond to shutdown_request and TeamDelete will fail

**When NOT to use Agent Teams:**
- Standard/light tier (overhead not worth it for 1-2 agents)
- Tasks with tight sequential dependencies (no parallelism benefit)
- Quick fixes where Agent() + result is faster

### Deep tier token optimization:
- When spawning agents in deep tier, use `model: "sonnet"` for implementation agents (save opus for planning/coordination)
- Use extended thinking `display: "omitted"` on API-level agent calls when available — strips thinking blocks from response, saves context tokens while preserving multi-turn signatures
- Prefer returning structured summaries from agents over raw output — reduces context consumption in the orchestrator

### After each subtask:
1. Update `.claude/memory/budget.md` — increment counters for any agents/critics used
2. Update `.claude/memory/state.md` — mark subtask status
3. **Budget gate**: Check if any counter hit its limit. If yes → stop and report to user
4. Invoke `/critic` if tier allows another round. For **light tier**, skip critic on individual subtasks — only run once at the end
5. If critic returns FAIL → re-execute ONCE. If FAIL again → **circuit breaker** → escalate to user with findings
6. Log decisions to `.claude/memory/decisions.md` via scribe pattern

### Context health check (after each subtask):

Score the session context load. Each signal adds points:

| Signal | Points | How to detect |
|--------|--------|---------------|
| Subtask progress >70% | +2 | Count done/total in state.md |
| Agent spawns ≥3 | +2 | Check budget.md agent counter |
| Agent spawns ≥5 | +3 | Check budget.md agent counter |
| Critic rounds ≥2 | +1 | Check budget.md critic counter |
| User back-and-forth ≥5 exchanges | +1 | Estimate from conversation |
| Large tool outputs received | +1 | If any agent returned very long results |
| Tier is deep | +1 | Check budget.md tier |

**Thresholds**:
- **Score 0-2**: Healthy. Continue normally.
- **Score 3-4**: **Yellow**. Save checkpoint silently. Continue working.
- **Score 5+**: **Red**. Save checkpoint + notify user: "Kontext session je velký. Checkpoint uložen. Pokud zaznamenáš pokles kvality, začni novou session s resume promptem z `/checkpoint status`."

**Rules**:
- Only notify user **once per session** (set mental flag after first notification)
- Never stop work — only checkpoint and optionally notify
- If user explicitly says "continue", respect that even at score 5+
- At score 7+, suggest (don't force) starting a new session

## Phase 5: Integrate & Verify

Once all subtasks are done:
1. Verify the combined result makes sense
2. Run `/critic` on the full output
3. If issues found → iterate (go back to Phase 4 for specific subtasks)
4. If clean → proceed to Phase 6

## Phase 6: Learn & Close

1. **Budget report**: Update `.claude/memory/budget.md` — generate summary, move to history, reset counters. Show the user: agents used / limit, critic rounds / limit, overall verdict.
2. Update `.claude/memory/state.md` — mark task complete
3. Record learnings via scribe pattern to `.claude/memory/learnings.md`:
   - What patterns emerged? (add to Patterns)
   - What didn't work? (add to Anti-patterns)
   - Was a skill missing? (add to Skill Gaps)
   - Was the tier accurate? (note if over/under-estimated for future calibration)
4. If a new repeatable pattern was discovered → suggest creating a skill via `/skill-generator`
5. Summarize results to the user, **including cost summary**

## Decision Framework: Agent vs. Skill vs. Direct

```
Is this a known, repeatable pattern?
├── YES → Does a skill exist for it?
│   ├── YES → Use the skill
│   └── NO → Create skill via /skill-generator, then use it
└── NO → Is it complex / needs exploration?
    ├── YES → Spawn Agent
    │   ├── Needs codebase exploration → Agent(general-purpose) with explore instructions
    │   ├── Needs planning → Agent(Plan)
    │   └── Needs implementation → Agent(general-purpose)
    └── NO → Do it directly (simple edit, single command)
```

## Circuit Breakers (hard stops)

These CANNOT be overridden without user approval:

1. **Agent loop**: Same agent type spawned 3+ times for same subtask → STOP
2. **Critic loop**: FAIL verdict 2 times on same target → STOP, show user what's wrong
3. **Budget exceeded**: Any counter hits tier limit → STOP, ask user to extend or wrap up
4. **Nesting depth**: orchestrator→skill→agent exceeds 2 levels → STOP, flatten
5. **Memory bloat**: Any `.claude/memory/` file exceeds 500 lines → trigger scribe maintenance first

## Rules

1. **Budget first** — check `.claude/memory/budget.md` before every agent spawn or critic invocation
2. **Start light, escalate if needed** — default to lowest viable tier
3. **Do simple things directly** — for light tier, the orchestrator CAN do work itself (no mandatory delegation for trivial edits)
4. **Scale scout to tier** — no agent spawns for scouting in light tier
5. **Always update shared memory** — other skills depend on it
6. **Prefer skills over agents** — skills are cheaper (no separate context window)
7. **Prefer parallel agents** over sequential when dependencies allow
8. **Critic is proportional** — light tier: once at end; standard: after key subtasks; deep: after each subtask
9. **Create skills for new patterns** — if you do it twice, it should be a skill
10. **Ask the user when uncertain** — don't guess on ambiguous requirements
11. **Report cost at close** — always include budget summary in Phase 6
