# ADOBE-AUTOMAT

Automatizace workflow v Adobe Creative Suite + NGM Localizer web app.

## Dostupné MCP servery

| Server | Aplikace | Poznámka |
|--------|----------|----------|
| `Adobe_Photoshop_MCP_Server` | Photoshop | UXP plugin, plná podpora vrstev, generative AI |
| `Adobe_Premiere_MCP_Server` | Premiere Pro | Sekvence, efekty, exporty |
| `Adobe_Illustrator_MCP_Server` | Illustrator | ExtendScript, export PNG |
| `Adobe_InDesign_MCP_Server` | InDesign | UXP plugin, tvorba dokumentů |

## Konvence

- **Jazyk**: Komentáře a dokumentace česky
- **Skripty**: Python 3, UTF-8
- **Cesty**: Absolutní Windows cesty pro Adobe API (`C:\Users\stock\...`)
- **Svelte 5**: `$props()`, `$state()`, `$derived()`, `onclick` (ne `on:click`)

## Dokumentace

- `docs/LEARNINGS.md` — poučení z vývoje, konvence, architektonická rozhodnutí
- `docs/TROUBLESHOOTING.md` — řešení známých problémů
- `memory/illustrator_extendscript.md` — ExtendScript vzory a reference

## Kritická pravidla

- **IDML**: NIKDY `ElementTree.write()` — string replace + `ET.fromstring()` validace
- **ExtendScript**: VŽDY `return JSON.stringify()`, cesty s forward slashy
- **Illustrator texty**: `\r` pro zalomení (ne `\n`)

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

This project uses **code-review-graph** for structural code analysis via MCP.

### Available Tools

| Tool | Description |
|------|-------------|
| `build_or_update_graph` | Build or incrementally update the knowledge graph |
| `detect_changes` | Risk-scored change impact analysis for code review |
| `get_impact_radius` | Blast radius from changed files |
| `get_review_context` | Focused review context with source snippets |
| `get_affected_flows` | Find execution flows affected by changes |
| `query_graph` | Predefined graph queries (callers, callees, imports, tests) |
| `semantic_search_nodes` | Search by name or semantic similarity |
| `list_flows` / `get_flow` | Explore execution flows |
| `list_communities` / `get_community` | Explore code communities |
| `get_architecture_overview` | High-level architecture from communities |
| `find_large_functions` | Find oversized functions/classes |
| `refactor_tool` / `apply_refactor_tool` | Graph-powered refactoring |
| `list_graph_stats` | Codebase metrics |
| `embed_graph` | Compute vector embeddings for semantic search |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
