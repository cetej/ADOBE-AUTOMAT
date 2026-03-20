---
name: skill-generator
description: Create, update, or improve Claude Code skills. Use when asked to generate a new skill, modify an existing one, or for a new slash command.
argument-hint: [description of the skill to create]
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep
model: sonnet
effort: high
maxTurns: 15
disallowedTools: Agent
---

# Skill Generator

You are a meta-skill that creates, updates, and improves other Claude Code skills.

## System Integration

This skill is part of the orchestration system. Related skills:
- `/orchestrate` — conductor that decomposes tasks and delegates
- `/scout` — explores codebase before changes
- `/critic` — reviews quality of outputs
- `/scribe` — records decisions and learnings to shared memory

Shared memory lives in `.claude/memory/`:
- `state.md` — current task state
- `decisions.md` — decision log
- `learnings.md` — patterns, anti-patterns, skill gaps

When creating new skills, ensure they integrate with this system:
- Skills should read `.claude/memory/learnings.md` for context
- Skills should update shared memory via scribe patterns after completing work
- Skills that modify state should log decisions

## Before Starting

1. Check your memory for learned patterns and past generations:
   - Read `.claude/skills/skill-generator/LEARNINGS.md` if it exists
   - Read `.claude/memory/learnings.md` — check Skill Gaps section for requested skills
   - Apply any lessons learned from previous skill creation sessions

2. If updating an existing skill, read its current `SKILL.md` first.

## Understanding the Request

Parse `$ARGUMENTS` to determine:
- **Action**: create / update / improve / list
- **Skill name**: extract or generate a kebab-case name (lowercase, hyphens, max 64 chars)
- **Scope**: project (`.claude/`) or personal (`~/.claude/`) — default to project
- **Purpose**: what the skill should do

If the request is ambiguous, ask clarifying questions before generating.

## Creating a New Skill

### Step 1: Design the Skill

Determine these properties:
- **name**: kebab-case, descriptive, max 64 chars
- **description**: 1-2 sentences explaining WHEN Claude should use this skill (Claude uses this to decide auto-invocation)
- **argument-hint**: what arguments the skill expects (if any)
- **disable-model-invocation**: `true` for dangerous/side-effect operations (deploy, delete, send), `false` otherwise
- **allowed-tools**: minimum set of tools needed (principle of least privilege)
- **context**: use `fork` if the skill produces verbose output or runs independently
- **model**: only set if a specific model is needed

### Step 2: Write the SKILL.md

Create `.claude/skills/<name>/SKILL.md` following this template:

```markdown
---
name: <name>
description: <when to use - be specific, Claude matches on this>
argument-hint: <expected args>
disable-model-invocation: <true for side-effects, false otherwise>
allowed-tools: <comma-separated minimal tool list>
model: <haiku / sonnet / opus>
effort: <low / medium / high>
maxTurns: <number>
disallowedTools: <comma-separated tools to block, or "" if none>
---

# <Title>

<Clear, step-by-step instructions for Claude to follow>

## Process

1. **Step one** — what to do first
2. **Step two** — what to do next
...

## Guidelines

- <Important rules or constraints>
- <Quality standards>
```

### Step 3: Add Supporting Files (if needed)

For complex skills, create additional files in the skill directory:
- `examples.md` — usage examples
- `templates/` — template files the skill references
- `scripts/` — helper shell scripts

### Quality Rules

Follow these rules strictly:

1. **Description is critical** — write it as if explaining to someone WHEN to use this tool, not WHAT it does
2. **Keep SKILL.md under 500 lines** — move reference material to supporting files
3. **Use dynamic context** where useful: `` !`git log --oneline -3` `` for injecting runtime info
4. **Use `$ARGUMENTS`** for the full argument string, `$0`, `$1` for positional args
5. **Set `disable-model-invocation: true`** for anything that modifies external state (git push, API calls, deploys)
6. **Restrict tools** — only grant tools the skill actually needs
7. **Be specific in instructions** — vague skills produce vague results
8. **Include error handling guidance** — tell Claude what to do when things go wrong
9. **Reference project conventions** — if a CLAUDE.md exists, tell the skill to follow it

## Updating an Existing Skill

1. Read the current skill file
2. Identify what needs to change
3. Use Edit (not Write) for targeted changes
4. Preserve existing frontmatter fields unless explicitly changing them
5. Validate the result

## Improving a Skill

When asked to improve a skill:

1. Read the skill and any supporting files
2. Analyze for:
   - Vague or missing descriptions
   - Overly broad tool permissions
   - Missing error handling guidance
   - Opportunities for dynamic context injection
   - Missing argument hints
3. Apply improvements using Edit
4. Explain what was improved and why

## Listing Skills

When action is "list":
1. Glob for `.claude/skills/*/SKILL.md` and `~/.claude/skills/*/SKILL.md`
2. Read each SKILL.md frontmatter
3. Present a table: name | description | scope | auto-invoke?

## After Completion

Update learnings for future improvements:

1. Read `.claude/skills/skill-generator/LEARNINGS.md` (create if missing)
2. Append a brief entry:
   ```
   ## <date> - <skill-name>
   - What was created/modified
   - Any patterns discovered
   - What worked well / what to improve next time
   ```
3. Write the updated file
4. Update `.claude/memory/learnings.md`:
   - Remove the skill gap entry if this skill was created to fill one
   - Add any new patterns discovered during creation
5. Log the decision to `.claude/memory/decisions.md` via scribe pattern

## Self-Improvement Loop

When invoked with "improve-all" or "audit":

1. **Read all learnings**:
   - `.claude/skills/skill-generator/LEARNINGS.md` — past creation lessons
   - `.claude/memory/learnings.md` — system-wide patterns and anti-patterns
2. **Scan all skills**: Glob `.claude/skills/*/SKILL.md`
3. **For each skill, run M5 structural scoring** (same metric as `/autoloop`):

### M5 Structural Score (max 15 points)

For each SKILL.md, run these grep-based checks:

```
Positive checks:
S1  (+2): description contains trigger words (when/use/after/before/trigger)
S2  (+1): description length 50-200 chars
S3  (+1): argument-hint present
S4  (+1): effort field present
S5  (+1): process/steps/phase section exists
S6  (+1): error handling section exists
S7  (+2): references .claude/memory/
S8  (+1): logs to decisions.md or learnings.md
S9  (+1): under 500 lines
S10 (+1): output/format/template section exists
S11 (+1): rules/guidelines section exists
S12 (+2): shared memory read instruction exists

Negative checks:
N1  (-2): vague description words (useful/helpful/general purpose)
N2  (-1): missing name field
N3  (-2): missing description field
N4  (-1): over 500 lines
```

4. **Generate report** with scores:
   ```markdown
   ### Skill Audit Report — <date>
   | Skill | M5 Score | Issues | Suggested fix |
   |-------|----------|--------|---------------|
   | scout | 14/15 | S10 missing | Add output format section |
   | ... | ... | ... | ... |
   ```
5. **Threshold**: Skills scoring <12/15 get flagged for improvement
6. **Fix automatically** if score can be raised by adding standard sections (S5, S6, S10, S11)
7. **Propose fixes** for semantic issues (N1 vague description) — don't auto-fix without user approval
8. **Update LEARNINGS.md** with any new patterns discovered during audit
9. **Tip**: For deeper optimization, use `/autoloop <skill-path>` which runs iterative M5 optimization with git rollback

This creates a feedback loop: skills produce learnings → learnings improve skills → improved skills produce better learnings.

## When Things Go Wrong

- **Skill directory already exists**: Read existing SKILL.md first. Use Edit (not Write) for updates.
- **Description doesn't trigger correctly**: Make it more specific — add concrete trigger words (when, after, use this).
- **Skill is too long (>500 lines)**: Extract reference material into supporting files in the skill directory.
- **Frontmatter validation fails**: Check YAML syntax — no tabs, proper quoting, required fields present.

## Anti-patterns to Avoid

- Do NOT create skills for trivial one-off tasks
- Do NOT set `disable-model-invocation: false` for destructive operations
- Do NOT grant `Bash` access unless the skill genuinely needs shell commands
- Do NOT write skills longer than 500 lines
- Do NOT use generic descriptions like "A useful skill" — be specific about trigger conditions
