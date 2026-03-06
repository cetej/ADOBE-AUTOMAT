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
