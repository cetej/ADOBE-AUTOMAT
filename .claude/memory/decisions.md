# Shared Memory — Decision Log

Decisions made during task execution. Each entry captures WHAT was decided, WHY, and by WHOM.

### 2026-03-18 — Add Budget Controller to Orchestration System
- **Context**: Self-assessment revealed no cost controls. System could become a "token black hole" with unbounded agent spawns and critic loops.
- **Options considered**: (A) Simple agent counter, (B) Full budget skill with tiers + circuit breakers + history, (C) External hook-based monitoring
- **Decision**: Option B — full budget skill with 3 complexity tiers (light/standard/deep)
- **Rationale**: Most practical. Tiers give proportional control without over-engineering.
- **Decided by**: orchestrator + user

### 2026-03-18 — Soften "Never Do Work Yourself" Rule
- **Context**: Original orchestrator rule "never do the work yourself" forced delegation even for trivial edits, wasting tokens.
- **Decision**: Light tier allows direct work, standard/deep still delegate
- **Rationale**: Proportional approach. A single-line fix shouldn't spawn an agent.
- **Decided by**: orchestrator (self-assessment)

### 2026-03-18 — Remove Bash and Agent from skill-generator
- **Context**: skill-generator had Bash and Agent in allowed-tools but doesn't need them.
- **Decision**: Restricted to Read, Write, Edit, Glob, Grep
- **Rationale**: Least-privilege principle.
- **Decided by**: orchestrator (self-assessment)

### 2026-03-18 — STOPA as Source of Truth
- **Context**: Orchestrační systém se vyvíjel v test1, kopíroval do ng-robot a ADOBE-AUTOMAT. Vznikal chaos.
- **Decision**: Vytvořit STOPA jako samostatný meta-projekt — source of truth pro orchestraci
- **Rationale**: Jeden zdroj pravdy, distribuce přes sync skript
- **Decided by**: user
