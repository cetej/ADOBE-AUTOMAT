---
name: project-init
description: "Initialize a new Claude Code project with optimal .claude/ structure, memory templates, and CLAUDE.md scaffold. Use when setting up a new project directory for Claude Code work."
argument-hint: "[project-path] [--name 'Project Name'] [--force]"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob
model: haiku
effort: medium
maxTurns: 15
disallowedTools: Agent
---

# Project Init — Optimal Claude Code Project Setup

You initialize new projects with the optimal `.claude/` structure for orchestration system integration.

## When Things Go Wrong

- **Directory already has `.claude/`**: Use `--force` to overwrite, or skip existing files. Never silently overwrite without flag.
- **Git not initialized**: Init git first (`git init`), then proceed with `.claude/` setup.
- **No write permissions**: Report the error clearly, suggest running with appropriate permissions.

## System Integration

This skill is part of the STOPA orchestration system. After initialization, the user installs the full orchestration via:
```bash
claude --plugin-dir /path/to/stopa-orchestration
```

## Input

Parse `$ARGUMENTS`:
- **project-path**: Path to the project root (required). Can be `.` for current directory.
- **--name "Name"**: Project name for CLAUDE.md (optional, defaults to directory name)
- **--force**: Overwrite existing `.claude/` structure (optional, default: fail if exists)

If no arguments provided, use current working directory and ask user for project name.

## Step 1: Validate

1. Resolve project path to absolute path
2. Check the directory exists — if not, create it
3. Check if `.claude/` already exists:
   - If exists and no `--force` → STOP, tell user: "`.claude/` already exists. Use `--force` to overwrite."
   - If exists and `--force` → warn user, proceed (do NOT delete existing files, only overwrite templates)
4. Check if `CLAUDE.md` exists — if yes, skip CLAUDE.md creation (never overwrite project instructions)

## Step 2: Create Directory Structure

Create these directories:
```
.claude/
├── skills/          # Empty — skills come via STOPA plugin
├── memory/          # Shared memory for orchestration
├── hooks/           # Empty — hooks come via STOPA plugin
└── agents/          # For project-specific agents (optional)
```

Use `mkdir -p` for all directories.

## Step 3: Initialize Memory Files

Create each file with the exact templates below. These templates define the format that orchestration skills expect.

### `.claude/memory/state.md`

```markdown
# Active Task

No active task.

# Task History

| # | Task | Status | Date |
|---|------|--------|------|
```

### `.claude/memory/decisions.md`

```markdown
# Decision Log

Format for each entry:
## [Decision Title]
- **Context**: Why this decision was needed
- **Options**: What was considered
- **Decision**: What was chosen
- **Rationale**: Why
- **Date**: YYYY-MM-DD
```

### `.claude/memory/learnings.md`

```markdown
# Learnings

## Patterns
<!-- "When X, do Y" — proven approaches -->

## Anti-patterns
<!-- "Never do X, do Y instead" — things that failed -->

## Skill Gaps
<!-- "When doing X, we need skill for Y" — missing capabilities -->
```

### `.claude/memory/budget.md`

```markdown
# Budget Tracker

## Current Task

No active task.

## Tier Reference
| Tier | Agents | Critics | Scout | Use when |
|------|--------|---------|-------|----------|
| light | 0-1 | 1x end | surface | Single file fix |
| standard | 2-4 | 2x | deep | Multi-file change |
| deep | 5-8 | 3x | full | Cross-cutting feature |

## History

| # | Task | Tier | Agents | Critics | Verdict |
|---|------|------|--------|---------|---------|
```

### `.claude/memory/decisions-archive.md`

```markdown
# Decisions Archive

Old decisions moved here by /scribe maintenance. Read-only reference.
```

### `.claude/memory/budget-archive.md`

```markdown
# Budget Archive

Historical budget data moved here by /scribe maintenance.
```

## Step 4: Create CLAUDE.md (if not exists)

Only create if `CLAUDE.md` does not already exist in project root.

Use this template — replace `{{PROJECT_NAME}}` with the project name:

```markdown
# {{PROJECT_NAME}}

## Popis

<!-- Krátký popis projektu — co dělá, k čemu slouží -->

## Struktura

<!-- Popis hlavních adresářů a souborů -->

## Orchestrace

Tento projekt používá orchestrační systém STOPA. Instalace:
\```bash
# Lokálně (z STOPA adresáře):
claude --plugin-dir /path/to/stopa-orchestration

# Nebo přímo ze STOPA:
./scripts/sync-orchestration.sh /path/to/this/project --commit
\```

Dostupné skills: `/orchestrate`, `/scout`, `/critic`, `/scribe`, `/budget`, `/checkpoint`, `/watch`, `/skill-generator`, `/dependency-audit`

## Konvence

### Kvalita kódu
- Preferuj jednoduché řešení — 3 řádky > předčasná abstrakce
- Nepřidávej features nad rámec zadání
- Error handling jen pro realistické scénáře

### Windows specifika
- Encoding: UTF-8 všude
- Cesty: `pathlib.Path()` nebo forward slashe

### Git
- Commit message: stručně, česky
- Staging: konkrétní soubory, ne `git add -A`
```

## Step 5: Create settings.json

Create `.claude/settings.json` with minimal config:

```json
{
  "permissions": {
    "allow": [],
    "deny": []
  }
}
```

## Step 6: Output

Display to the user:

1. **Tree of created files** — show what was created
2. **Next steps**:
   - "Uprav `CLAUDE.md` — doplň popis projektu a specifické konvence"
   - "Nainstaluj orchestraci: `claude --plugin-dir /path/to/stopa-orchestration`"
   - "Nebo sync: `./scripts/sync-orchestration.sh <tento-projekt> --commit`"
3. **Quick start**: "Použij `/orchestrate` pro komplexní úkoly, `/scout` pro průzkum"

## Rules

- NEVER overwrite existing CLAUDE.md — it contains project-specific instructions
- NEVER delete existing files in `.claude/` even with `--force`
- Memory templates must match exactly — orchestration skills parse these formats
- Keep output in Czech for the user
- If project has `.git/`, mention that `.claude/memory/` should be in `.gitignore` (sensitive state)
