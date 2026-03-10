# TROUBLESHOOTING — ADOBE-AUTOMAT

Řešení známých problémů. Nejnovější nahoře.

---

## Claude Desktop padá při startu konverzace

**Příznaky**: Konverzace se ukončí hned po otevření, žádná chybová hláška.

**Příčina**: Příliš mnoho MCP serverů → přetečení kontextu (~160+ tool definic).

**Řešení**:
1. Otevři `%APPDATA%\Claude\claude_desktop_config.json`
2. Odstraň duplicitní servery (`photoshop-mcp`, `claude-code`, `playwright`)
3. Nech max 6 serverů
4. Restartuj Claude Desktop

**Prevence**:
- MEMORY.md max 40 řádků, detaily do `docs/LEARNINGS.md`
- Default config: 0 MCP serverů, zapínat jen přes switcher
- Switcher: `python C:\Users\stock\Tools\claude-mcp-switch.py [profil]`

**Profily switcheru**:
```
off     — vypne vše (default)
ps      — jen Photoshop
ai      — jen Illustrator
pr      — jen Premiere
id      — jen InDesign
adobe   — všechny 4 Adobe servery
web     — Brave Search + Context7
ps ai   — kombinace (více argumentů)
```

---

## Backend se nespustí (port obsazený)

**Příznaky**: `Address already in use` při startu uvicorn.

**Řešení**:
```bash
netstat -ano | grep 8100
taskkill /PID <číslo> /F
```

---

## IDML export — poškozený XML

**Příznaky**: InDesign hlásí corrupted file po write-back.

**Příčina**: `ElementTree.write()` ničí XML declaration + Processing Instructions.

**Řešení**: Použít string replace na raw XML, validovat `ET.fromstring()`. Viz `idml_writer.py`.

---

## Illustrator ExtendScript — [object Object]

**Příznaky**: MCP vrací `[object Object]` místo dat.

**Řešení**: `return JSON.stringify(results)` — NIKDY holé `return results`.

---

## Illustrator writeback — Text index out of range

**Příznaky**: Chyby typu `Text index out of range (9 direct frames)` při zápisu.

**Příčina**: `layer.textFrames` je hluboká kolekce — zahrnuje i texty z podvrstev. Extrakce indexovala sublayer texty pod parent vrstvou, writeback je pak nemohl najít.

**Řešení**: `isDirectChild(tf, layer)` v extract_texts.jsx i write_texts.jsx — filtruje jen přímé potomky, sublayery se zpracují rekurzivně.

**Prevence**: Vždy kontrolovat konzistenci indexování mezi extrakcí a zápisem.

---

## Illustrator texty — nefunguje matchování

**Příznaky**: `tf.contents === original` nefinduje shodu.

**Příčina**: Illustrator používá `\r` (ne `\n`) pro zalomení řádku.

**Řešení**: V matchovacím stringu nahradit `\n` za `\r`.
