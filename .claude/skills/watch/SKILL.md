---
name: watch
description: Scan news and updates from AI/ML ecosystem, Claude Code, and community sources. Use weekly to stay current on tools, libraries, and techniques relevant to this project and orchestration system. Also use when the user asks "what's new" or "check for updates".
argument-hint: [full / quick / topic:specific-topic]
user-invocable: true
allowed-tools: Read, Write, Edit, WebSearch, WebFetch, Agent
---

# Watch — News & Updates Scanner

You scan external sources for news, updates, and changes relevant to this project and its orchestration system. You report findings and suggest actionable improvements.

## Shared Memory

1. Read `.claude/memory/news.md` — previous findings and last scan date
2. Read `.claude/memory/learnings.md` — current patterns (to spot relevant updates)
3. Read `CLAUDE.md` — project dependencies and tech stack (to know what to watch)

## Input

Parse `$ARGUMENTS`:
- **"full"** (default) → Scan all source tiers (1-3)
- **"quick"** → Tier 1 only (Claude Code + API). Cheapest option.
- **"topic:X"** → Focus scan on specific topic (e.g., "topic:pytorch", "topic:flow-matching")

## Source Tiers

### Tier 1: Claude Code & Anthropic (always scan)

Use `WebSearch` for each:
1. **Claude Code releases** — search: `"claude code" changelog OR release notes site:docs.anthropic.com OR site:github.com/anthropics {current_year}`
2. **Claude API updates** — search: `anthropic claude API new features OR models {current_year}`
3. **Claude skills/hooks** — search: `"claude code" skills OR hooks OR MCP new {current_year}`

For each result, `WebFetch` the most relevant 1-2 pages.

### Tier 2: AI/ML Ecosystem (scan on "full")

Use `WebSearch` for each:
4. **PyTorch** — search: `pytorch release OR blog {current_year} {current_month}`
5. **HuggingFace + diffusers** — search: `huggingface diffusers release OR update {current_year}`
6. **Flow matching / video generation** — search: `"flow matching" OR "video generation" model paper {current_year}`
7. **timm / einops** — search: `timm OR einops release {current_year}` (skip if no results)

### Tier 3: Community (scan on "full")

Use `WebSearch` for each:
8. **GitHub trending** — search: `github trending python machine learning video generation {current_month} {current_year}`
9. **Reddit** — search: `site:reddit.com (r/LocalLLaMA OR r/StableDiffusion) "flow matching" OR "video generation" OR "pyramid" {current_year}`
10. **General AI news** — search: `AI tools developer productivity {current_month} {current_year}`

## Processing

For each source that returns results:

1. **Filter**: Is this relevant to our project or orchestration system?
2. **Classify**:
   - `[ACTION]` — Directly useful, should act on it (new version of dependency, breaking change, new Claude feature)
   - `[WATCH]` — Interesting, monitor further (emerging technique, upcoming release)
   - `[INFO]` — Good to know, no action needed (industry trend, tangential news)
3. **Summarize**: 1-2 sentences per item
4. **Suggest**: For `[ACTION]` items, propose a concrete next step

## Parallel Execution

To minimize cost, use parallel WebSearch calls:
- Launch Tier 1 searches (items 1-3) in parallel
- If "full" mode, launch Tier 2 (items 4-7) in parallel
- If "full" mode, launch Tier 3 (items 8-10) in parallel
- Fetch detailed pages only for promising results

## Output Format

```markdown
## Watch Report — <date>

**Mode**: full / quick / topic:X
**Sources scanned**: N
**Items found**: N (X action, Y watch, Z info)

### Action Items

| # | Source | Finding | Suggested Action |
|---|--------|---------|-----------------|
| 1 | Claude Code v1.X | New skill hooks API | Update orchestration to use new hooks |
| 2 | diffusers 0.32 | Breaking change in scheduler API | Check compatibility with our schedulers |

### Watch List

| # | Source | Finding | Why It Matters |
|---|--------|---------|---------------|
| 1 | arxiv | New flow matching technique | Could improve generation quality |

### Info

- <brief bullet points for [INFO] items>

### Recommendations for Orchestration System

<If any findings suggest improvements to the skill system, list them here>

### Recommendations for Active Projects

<If any findings affect project dependencies or techniques, list them here>
```

## After Scanning

1. **Update `.claude/memory/news.md`**:
   - Record scan date and mode
   - Append ACTION and WATCH items (not INFO — too noisy)
   - If an ACTION item from a previous scan is now resolved, mark it done

2. **If ACTION items found for orchestration system**:
   - Add to `.claude/memory/learnings.md` under appropriate section
   - If a new skill is suggested, add to Skill Gaps

3. **If ACTION items found for project dependencies**:
   - Note in `.claude/memory/state.md` as a potential future task

## Cost Control

- **Quick mode**: ~5-8k tokens (3 searches, 1-2 fetches)
- **Full mode**: ~50-75k tokens (10 searches, 5-10 fetches)
- Use `haiku` model for agent spawns if deeper analysis needed
- Never spawn more than 1 agent — do the search/fetch work directly
- If a source consistently returns nothing useful, skip it in future scans (note in news.md)

## Scheduling Guidance

Recommended cadence: **weekly** (every Monday or at first session of the week).

How to trigger:
- User runs `/watch` or `/watch full` manually
- Orchestrator checks `.claude/memory/news.md` last scan date — if >7 days, suggest running `/watch`
- User can set up a hook or reminder externally

## Rules

1. **Signal over noise** — skip irrelevant results ruthlessly. Better to report 3 useful items than 20 tangential ones.
2. **Actionable over informational** — prioritize things the user can act on
3. **Cost-aware** — use parallel searches, minimal fetches, haiku for analysis
4. **No false urgency** — don't mark things [ACTION] unless they genuinely need attention
5. **Cumulative knowledge** — always check previous news.md to avoid reporting the same thing twice
6. **Respect project context** — filter through the lens of CLAUDE.md dependencies and tech stack
