# Shared Memory — Learnings

Accumulated knowledge from all tasks. Used by all skills/agents to improve over time.

## Patterns

### Budget-First Orchestration
- **Context**: When orchestrating any multi-step task
- **Pattern**: Assign complexity tier BEFORE scouting. Start with lowest viable tier. Upgrade only if scout reveals higher complexity.
- **Source**: Self-assessment, 2026-03-18

### Proportional Critic Usage
- **Context**: When deciding how many review rounds to run
- **Pattern**: Light tier = once at end. Standard = after key subtasks. Deep = after each subtask.
- **Source**: Self-assessment, 2026-03-18

### Tool Least Privilege
- **Context**: When creating or reviewing skills
- **Pattern**: Only grant tools the skill actually needs. Bash and Agent are expensive — remove if not essential.
- **Source**: Self-assessment, 2026-03-18

### Cost Estimation for User Decisions
- **Context**: When proposing options with different cost profiles
- **Pattern**: Always estimate cost in tokens AND real currency (USD + CZK). Users can't judge "50k tokens" but understand "$0.15/week".
- **Source**: /watch creation, 2026-03-18

## Anti-patterns

### Mandatory Full Orchestration
- **Problem**: Over-orchestration wastes tokens. A trivial edit doesn't need scout→plan→execute→critic→scribe.
- **Instead**: Assign light tier and do simple things directly.

### Infinite Critic Loop
- **Problem**: Without a limit, critic→fix→critic→fix can loop indefinitely.
- **Instead**: Max 2 FAIL verdicts on same target, then circuit breaker → escalate to user.

### Unbounded Agent Spawning
- **Problem**: Each agent has its own context window = significant token cost. Without limits, costs explode.
- **Instead**: Tier-based limits. Light=0-1, Standard=2-4, Deep=5-8.

## Cross-Repo Setup

### User's Environment
- **Projekty**: NG-ROBOT (desktop, hlavní), test1 (web, Pyramid Flow), ADOBE-AUTOMAT (desktop, Adobe automatizace), STOPA (meta-projekt, source of truth pro orchestraci)
- **Sync**: Z STOPA do cílových projektů přes `scripts/sync-orchestration.sh`
- **CLAUDE.md**: Každý projekt má vlastní, nesyncuje se
- **Častá záměna**: User říká "udělal jsem pull a nic se nestalo" — pravděpodobně pulloval v jiném repozitáři
- **Source**: Sessions 2026-03-18

## Skill Gaps

### Plugin Distribution
- **Situation**: Plugin system je GA (v1.0.33+). Naše orchestrace se distribuuje přes sync skript, ale plugin by to nahradil elegantněji.
- **Potřeba**: Zabalit STOPA orchestraci jako Claude Code plugin (`.claude-plugin/plugin.json` + skills/ + hooks/)
- **Priority**: high
- **Source**: /watch scan, 2026-03-18

### Agent Teams Native API
- **Situation**: Agent Teams jsou GA — native coordination přes SendMessage, shared task list
- **Potřeba**: /orchestrate deep tier by měl použít native Agent Teams místo manuálních Agent() volání
- **Priority**: medium
- **Source**: /watch scan, 2026-03-18
