# Shared Memory — News & Updates

Tracked findings from `/watch` scans. Only ACTION and WATCH items are recorded here.

## Last Scan

**2026-03-18** — full (STOPA-focused)

## Active Items

### Action Items

1. **Plugin System GA** — zabalit orchestraci jako plugin (`.claude-plugin/plugin.json`)
   - Impact: high — nahradí sync skript, snadnější distribuce
   - Status: open, high priority
   - Ref: https://code.claude.com/docs/en/plugins

2. **Agent Teams GA** — native parallel agent coordination přes SendMessage + shared task list
   - Impact: high for /orchestrate deep tier
   - Status: open, guidance v orchestrate skill existuje, potřeba native API
   - Ref: https://code.claude.com/docs/en/agent-teams

3. **`/loop` command** — opakované spouštění skills na intervalu
   - Impact: medium — automatizace `/watch` bez ručního spouštění
   - Status: open

4. **HTTP hooks** — POST JSON místo shell commands
   - Impact: medium — čistší hook implementace, cross-platform
   - Status: open

5. **Token limit increase** — Opus 64k default, 128k max output
   - Impact: low — aktualizovat budget estimation formule
   - Status: open

### Watch List

1. **Hook-enforced orchestration** — `barkain/claude-code-workflow-orchestration` — PreToolUse hooks vynucují delegaci
   - Relevance: konkurenční pattern, silnější enforcement než naše convention-based pravidla
2. **Ruflo/Claude Flow** — multi-agent swarm s 60+ agenty, self-learning
   - Relevance: over-engineered pro nás, ale zajímavý self-improvement pattern
3. **Agent Skills Standard** — Anthropic's open standard, cross-tool kompatibilita
   - Relevance: ověřit shodu našich skills se standardem
4. **MCP Memory Servers** — persistent memory přes MCP místo file-based
   - Relevance: alternativa k naší .claude/memory/ architektuře

## Scan History

### 2026-03-18 — full — STOPA-focused scan
- Plugin System GA — highest priority finding
- Agent Teams GA, /loop command, HTTP hooks
- Competing orchestration patterns (hook-enforced vs convention-based)
- 14k+ MCP servers in ecosystem

### 2026-03-18 — full — initial scan (in test1 context)
- First scan focused on Pyramid Flow dependencies
- Orchestration-relevant items extracted to STOPA

## Skipped Sources

<!-- Sources that consistently return nothing useful -->
