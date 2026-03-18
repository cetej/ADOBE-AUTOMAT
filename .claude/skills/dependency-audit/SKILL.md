---
name: dependency-audit
description: Audit project dependencies for outdated versions, breaking changes, and security issues. Use when checking if dependencies need updating, after /watch reports version gaps, or before planning upgrades.
argument-hint: [full / quick / package-name]
user-invocable: true
allowed-tools: Read, Glob, Grep, WebSearch, WebFetch
---

# Dependency Audit — Version & Compatibility Checker

You analyze project dependencies, check for updates, identify breaking changes, and produce a prioritized upgrade plan.

## Input

Parse `$ARGUMENTS`:
- **"full"** (default) → Audit all dependencies in requirements.txt and CLAUDE.md
- **"quick"** → Check only critical dependencies (Python, PyTorch, diffusers, transformers)
- **"<package-name>"** → Deep audit of a single package (e.g., "timm", "torch")

## Process

### Step 1: Read Current State

1. Read `requirements.txt` — extract all pinned versions
2. Read `CLAUDE.md` — extract dependency versions from Dependencies section
3. Read `.claude/memory/news.md` — check if /watch already found version issues

### Step 2: Check Latest Versions

For each dependency (or subset based on input):

Use `WebSearch` to find: `<package> latest version pypi 2026`

Focus on these critical packages:
| Package | Current | Priority |
|---------|---------|----------|
| Python | 3.8.10 | CRITICAL — EOL, blocks everything |
| torch | 2.1.2 | HIGH — 8 major versions behind |
| diffusers | >=0.30.1 | HIGH — 0.37 requires Python 3.10 |
| transformers | 4.39.3 | MEDIUM |
| timm | 0.6.12 | MEDIUM — 1.0.x is current |
| accelerate | 0.30.0 | MEDIUM |
| einops | (unpinned) | LOW |
| gradio | (unpinned) | LOW |

### Step 3: Identify Breaking Changes

For each package with a significant version gap:
1. Search for migration guides and changelogs
2. Identify Python version requirements
3. Check for API changes that affect our code
4. Note if peer dependencies conflict

### Step 4: Build Dependency Graph

Map which upgrades block others:
```
Python 3.8 → 3.10+  (MUST do first)
  ├── unlocks diffusers 0.37+
  ├── unlocks torch 2.x latest
  └── unlocks transformers latest
       └── may require diffusers version bump
```

### Step 5: Produce Upgrade Plan

## Output Format

```markdown
## Dependency Audit Report — <date>

**Mode**: full / quick / <package>
**Packages audited**: N
**Issues found**: N critical, N high, N medium, N low

### Critical Issues

| Package | Current | Latest | Gap | Blocker |
|---------|---------|--------|-----|---------|
| Python | 3.8.10 | 3.12.x | 4 major | EOL, blocks all upgrades |

### Upgrade Plan (ordered)

| Phase | Package | From → To | Breaking Changes | Effort |
|-------|---------|-----------|-----------------|--------|
| 1 | Python | 3.8.10 → 3.10.x | f-strings OK, some stdlib changes | HIGH |
| 2 | torch | 2.1.2 → 2.x.x | <specific changes> | MEDIUM |
| 3 | ... | ... | ... | ... |

### Compatibility Matrix

| Package A | Package B | Compatible Range |
|-----------|-----------|-----------------|
| torch 2.10 | transformers 4.x | 4.40+ |

### Risk Assessment

- **High risk**: <packages with known breaking API changes>
- **Medium risk**: <packages with minor API changes>
- **Low risk**: <packages with only bugfixes>

### Recommendations

1. <Prioritized, actionable steps>
2. <Include "test X after upgrading Y" notes>
```

## Rules

1. **Don't guess versions** — always verify via WebSearch
2. **Dependency order matters** — Python version gates everything else
3. **Note what we actually use** — only flag breaking changes in APIs we import
4. **Be conservative** — recommend minimum viable upgrade, not always latest
5. **Cross-reference with /watch** — avoid duplicating findings from news.md
