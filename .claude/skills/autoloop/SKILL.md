---
name: autoloop
description: Run autonomous optimization loop on a file (Karpathy Loop pattern). Use when asked to iteratively improve a skill, prompt, or config with a measurable metric.
argument-hint: <target file path> [goal description]
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
effort: high
maxTurns: 30
disallowedTools: Agent
---

# AutoLoop — Autonomous Optimization Loop

You run the Karpathy Loop pattern: read target → propose change → measure → keep/revert → repeat.

## Core Principle

**One file, one metric, autonomous iteration, git rollback.**

You are both the proposer AND the executor. Each iteration:
1. Read the target file + goal
2. Think about what would improve the score
3. Make ONE focused edit
4. Measure the new score
5. If score improved → git commit. If not → git revert.
6. Repeat until budget exhausted or score plateaus.

## Phase 0: Setup

### Parse input

From `$ARGUMENTS`, extract:
- **target**: file path to optimize (required)
- **goal**: what to optimize for (optional — inferred from file type if missing)

If target is not provided, ask the user.

### Detect target type

| Pattern | Type | Default goal |
|---------|------|-------------|
| `*/SKILL.md` | skill | Improve structure, description quality, and integration |
| `*.md` (other) | prompt/doc | Improve clarity, specificity, and completeness |
| `*.py` | script | Improve readability and efficiency |
| `*.json` | config | Improve structure and completeness |
| Other | generic | Ask user for goal |

### Set budget

Default: **10 iterations** (override with `budget:N` in arguments).

### Create feature branch

```bash
git checkout -b autoloop/$(basename <target> .md)-$(date +%s)
```

If git is not initialized or branch creation fails, warn user and continue without git (no rollback safety — reduce budget to 5).

### Calculate baseline score

Run the scoring function (see Scoring section below) on the unmodified target. Record as `baseline_score`.

## Phase 1: Iteration Loop

For each iteration (1 to budget):

### Step 1: Analyze

Read the target file. Identify the **lowest-scoring dimension** from the last score breakdown. Focus your edit there — don't scatter changes.

### Step 2: Propose & Apply

Make ONE focused edit using the Edit tool. Rules:
- **One change per iteration** — don't rewrite the whole file
- **Small, targeted edits** — like Karpathy: "a hypothesis, not a rewrite"
- **Never delete content that scores points** — only add, improve, or restructure
- **Preserve frontmatter** — never break YAML frontmatter structure

### Step 3: Measure

Run the scoring function on the modified file. Record as `new_score`.

### Step 4: Decide

```
If new_score > current_score:
  → KEEP: git add <target> && git commit -m "autoloop: +<delta> (<what changed>)"
  → Update current_score = new_score
  → Log: "✓ Iteration N: score X → Y (+delta) — <what changed>"

If new_score <= current_score:
  → REVERT: git checkout -- <target>
  → Log: "✗ Iteration N: score stayed at X — <what was tried> (reverted)"
```

If git is not available, use a backup copy for revert:
```bash
cp <target> <target>.backup  # before edit
cp <target>.backup <target>  # to revert
```

### Step 5: Check exit conditions

Stop early if:
- **Plateau**: 3 consecutive reverts (no improvement found)
- **Max score**: All scoring dimensions are maxed out
- **Budget**: Iteration count hit the limit

## Phase 2: Final Validation (LLM-as-judge)

After the loop ends, do ONE semantic validation. Read the optimized file and evaluate:

For **skill** targets:
> "Read this SKILL.md. Evaluate on 3 dimensions (1-10 each):
> 1. **Trigger clarity**: Would Claude reliably know WHEN to invoke this skill based on the description?
> 2. **Instruction completeness**: Are the instructions clear enough that Claude can execute without guessing?
> 3. **Integration quality**: Does the skill properly use shared memory and follow orchestration patterns?
> Overall score (average of 3)."

For **other** targets:
> "Read this file. Does it achieve its stated purpose clearly and completely? Score 1-10."

Record the validation score. If it dropped below 5 on any dimension, warn — the structural improvements may have hurt semantic quality.

## Phase 3: Report

Output the experiment log:

```markdown
## AutoLoop Report: <target>

**Goal**: <goal>
**Iterations**: <used> / <budget>
**Branch**: autoloop/<name>

### Score Progression

| Iter | Score | Delta | Change | Status |
|------|-------|-------|--------|--------|
| 0 | <baseline> | — | baseline | — |
| 1 | ... | +N | <what> | ✓ kept |
| 2 | ... | 0 | <what> | ✗ reverted |
| ... | | | | |

### Summary
- **Baseline**: <score> → **Final**: <score> (+<total delta>)
- **Kept changes**: N / M iterations
- **Validation score**: X/10
- **Exit reason**: budget | plateau | max score

### Accepted Changes (cumulative diff)
<show git diff from baseline to final>
```

Ask the user: "Merge branch `autoloop/<name>` into current branch, or discard?"

## Scoring: SKILL.md (built-in)

For `*/SKILL.md` files, use this structural heuristic. Run each check and sum points:

### Positive signals (max 15 points)

| # | Check | Points | How to verify |
|---|-------|--------|---------------|
| S1 | Description has trigger conditions | +2 | Grep description line for: `when`, `use when`, `use this`, `after`, `before`, `trigger` (case-insensitive) |
| S2 | Description is 50-200 chars | +1 | Measure description field length |
| S3 | argument-hint is present and non-empty | +1 | Check frontmatter |
| S4 | effort field is present | +1 | Check frontmatter |
| S5 | Has process/steps section | +1 | Grep for `^##.*[Pp]rocess\|^##.*[Ss]tep\|^## Phase` |
| S6 | Has error/failure handling section | +1 | Grep for `^##.*[Ee]rror\|^##.*[Ff]ail\|^##.*wrong\|circuit.breaker` |
| S7 | References `.claude/memory/` | +2 | Grep for `.claude/memory/` or `memory/state\|memory/learnings\|memory/decisions` |
| S8 | Logs to decisions or learnings | +1 | Grep for `decisions.md\|learnings.md` and context suggests writing |
| S9 | Under 500 lines | +1 | `wc -l` |
| S10 | Has output format section | +1 | Grep for `^##.*[Oo]utput\|^##.*[Ff]ormat\|^##.*[Tt]emplate\|```markdown` |
| S11 | Has rules/guidelines section | +1 | Grep for `^##.*[Rr]ule\|^##.*[Gg]uideline\|^## Rules` |
| S12 | Has shared memory read instruction | +2 | Grep for `Read first\|read.*memory\|Before anything.*read\|Shared Memory` |

### Negative signals (penalties)

| # | Check | Points | How to verify |
|---|-------|--------|---------------|
| N1 | Description is vague | -2 | Grep description for: `useful`, `helpful`, `general.purpose`, `various`, `miscellaneous` |
| N2 | Missing name in frontmatter | -1 | Check frontmatter |
| N3 | Missing description in frontmatter | -2 | Check frontmatter |
| N4 | Over 500 lines | -1 | `wc -l` |

### Scoring implementation

Run these bash commands and sum the results. Use this exact pattern:

```bash
# Extract description from frontmatter
DESC=$(sed -n '/^---$/,/^---$/p' <target> | grep '^description:' | sed 's/^description: *//')

# S1: trigger words in description (+2)
echo "$DESC" | grep -iE 'when|use (this|when)|after|before|trigger' > /dev/null && echo "S1:+2" || echo "S1:0"

# S2: description length 50-200 (+1)
LEN=$(echo -n "$DESC" | wc -c)
[ "$LEN" -ge 50 ] && [ "$LEN" -le 200 ] && echo "S2:+1" || echo "S2:0"

# S3: argument-hint present (+1)
sed -n '/^---$/,/^---$/p' <target> | grep -q '^argument-hint:.\+.' && echo "S3:+1" || echo "S3:0"

# S4: effort field (+1)
sed -n '/^---$/,/^---$/p' <target> | grep -q '^effort:' && echo "S4:+1" || echo "S4:0"

# S5: process/steps section (+1)
grep -qiE '^##.*(process|step|phase)' <target> && echo "S5:+1" || echo "S5:0"

# S6: error handling section (+1)
grep -qiE '^##.*(error|fail|wrong)|circuit.breaker' <target> && echo "S6:+1" || echo "S6:0"

# S7: references .claude/memory/ (+2)
grep -q '.claude/memory/' <target> && echo "S7:+2" || echo "S7:0"

# S8: logs to decisions/learnings (+1)
grep -qE 'decisions\.md|learnings\.md' <target> && echo "S8:+1" || echo "S8:0"

# S9: under 500 lines (+1)
[ "$(wc -l < <target>)" -lt 500 ] && echo "S9:+1" || echo "S9:0"

# S10: output format section (+1)
grep -qiE '^##.*(output|format|template)|```markdown' <target> && echo "S10:+1" || echo "S10:0"

# S11: rules section (+1)
grep -qiE '^##.*(rule|guideline)' <target> && echo "S11:+1" || echo "S11:0"

# S12: shared memory read instruction (+2)
grep -qiE 'read first|read.*memory|before anything.*read|shared memory' <target> && echo "S12:+2" || echo "S12:0"

# N1: vague description (-2)
echo "$DESC" | grep -iE 'useful|helpful|general.purpose|various|miscellaneous' > /dev/null && echo "N1:-2" || echo "N1:0"

# N2: missing name (-1)
sed -n '/^---$/,/^---$/p' <target> | grep -q '^name:' && echo "N2:0" || echo "N2:-1"

# N3: missing description (-2)
sed -n '/^---$/,/^---$/p' <target> | grep -q '^description:' && echo "N3:0" || echo "N3:-2"

# N4: over 500 lines (-1)
[ "$(wc -l < <target>)" -ge 500 ] && echo "N4:-1" || echo "N4:0"
```

Parse all S/N outputs and sum. This is the structural score.

## Scoring: Generic files

For non-SKILL.md files, create a custom scoring function based on the goal. Ask yourself:
- What structural properties indicate quality for this file type?
- What can be checked with grep/wc/regex?
- Design 8-12 checks worth ~15 points total.

If you can't design automated checks for the target type, fall back to **LLM-as-judge for every iteration** (warn user about higher cost).

## Budget Awareness

Before starting:
1. Read `.claude/memory/budget.md`
2. This skill does NOT count as an agent spawn (it runs in the main context)
3. Log the autoloop run to budget event log when done
4. Estimated cost: ~2-5k tokens per iteration (edit + grep scoring) + ~5k for final validation

## Rules

1. **One change per iteration** — isolation of effects, like Karpathy's single-variable experiments
2. **Never break the file** — if an edit makes the file unparseable (broken YAML, broken markdown), revert immediately
3. **Diminishing returns** — if 3 consecutive iterations are reverted, STOP (plateau detected)
4. **Preserve semantics** — structural score is a proxy; never sacrifice meaning for points
5. **Git safety** — always work on a feature branch, never on main/master
6. **Report everything** — log kept AND reverted experiments (the failures are informative)
7. **Ask before merge** — never auto-merge the branch; let the user decide
8. **Respect budget** — default 10 iterations, user can override
