# Skill Generator — Examples

## Create a new skill

```
/skill-generator create a skill that reviews Python code for security vulnerabilities
```

This will create `.claude/skills/security-review/SKILL.md` with:
- Appropriate tool restrictions (Read, Grep, Glob only — no Write needed for review)
- `disable-model-invocation: false` (safe, read-only operation)
- Instructions to check OWASP top 10, injection patterns, etc.

## Update an existing skill

```
/skill-generator update security-review to also check for hardcoded secrets
```

## Improve a skill

```
/skill-generator improve security-review
```

Analyzes the skill and suggests/applies improvements like tighter tool restrictions,
better descriptions, dynamic context injection, etc.

## List all skills

```
/skill-generator list
```

Shows a table of all project and personal skills with their descriptions.

## Create a skill with specific scope

```
/skill-generator create a personal skill for managing git worktrees (scope: personal)
```

Creates in `~/.claude/skills/` instead of `.claude/skills/`.
