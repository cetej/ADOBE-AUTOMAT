# LEARNINGS — ADOBE-AUTOMAT

Poučení z vývoje. Nejnovější záznamy nahoře.

---

## 2026-03-07 — ExtendScript: Deep textFrames collection

### layer.textFrames je HLUBOKÁ kolekce
- **Problém**: `layer.textFrames` v Illustratoru vrací textové rámce ze VŠECH podvrstev, ne jen přímé potomky
- **Důsledek**: Extrakce indexovala i texty z podvrstev → writeback nemohl najít indexy (7 chyb na Vikings mapě)
- **Řešení**: `isDirectChild(tf, layer)` — walker parent chainu, vrací true jen pro přímé potomky
- **Pravidlo**: V extract_texts.jsx i write_texts.jsx VŽDY filtrovat přes `isDirectChild()`, sublayery zpracovat rekurzivně

---

## 2026-03-07 — MAP Writeback: Adaptivní dávkování

### Fixní BATCH_SIZE nestačí pro různé typy map
- **Problém**: Mapy s dlouhými texty (legendy, články) mohou překročit ExtendScript string limit
- **Řešení**: `_make_batches()` v `map_writeback.py` — akumuluje položky do dávky podle:
  - MAX_BATCH_BYTES = 50 KB (velikost JSON payloadu)
  - MAX_BATCH_ITEMS = 30 (horní limit počtu)
  - Co přijde dřív → nová dávka
- **Výhoda**: Krátké popisky map = velké dávky (30), dlouhé texty = automaticky menší dávky

---

## 2026-03-07 — Dashboard: Drag-and-drop UX

### Jeden krok místo průvodce
- **Problém**: Vícekrokový dialog (typ → jméno → soubor → extrakce) byl nepraktický
- **Řešení**: Drop .idml → auto-create projekt + upload + extrakce + navigace do editoru
- Drop .ai → create MAP projekt + navigace do extractoru
- Illustrator status bar s tlačítkem "Extrahovat mapu"
- **Pravidlo**: Minimalizovat kroky pro uživatele, automatizovat co jde

---

## 2026-03-06 — IDML Writeback: Whitespace + Apostrophe Bug

### Extrakce `.strip()` vs XML whitespace
- **Problém**: Extrakce volá `.strip()` na text z `<Content>`, ale XML má whitespace okolo (`<Content>text </Content>`). Writeback hledal exact match → 163/386 selhalo (42%).
- **Root cause 1 (160x)**: Leading/trailing mezery, taby, U+2028 v XML stripnuté při extrakci
- **Root cause 2 (3x)**: `xml_escape()` neescapovala `'` na `&apos;` — XML má `wouldn&apos;t`, hledali jsme `wouldn't`
- **Řešení**: Whitespace-tolerantní regex v `safe_batch_replace()` + `&apos;` v `xml_escape()`
- **Výsledek**: 223/387 → 386/387 nahrazeno (99.7%)
- **Pravidlo**: Při writebacku VŽDY počítat s tím, že extrakce normalizuje text jinak než je v XML

---

## 2026-03-06 — IDML Processing

### NIKDY ElementTree.write() na IDML XML
- **Problém**: `ET.write()` ničí XML declaration + Processing Instructions
- **Řešení**: String replace na raw XML, pak `ET.fromstring()` pro validaci
- **Pravidlo**: Regex jen uvnitř `<Content>` elementů, nikdy na celém XML

### ZIP repack pravidla
- `mimetype` MUSÍ být první soubor v ZIP, ZIP_STORED (ne DEFLATED)
- Validace po každé změně: `ET.fromstring(xml_str.encode('utf-8'))`

### IDML kategorizace
- PointSize>20 = heading, AllCaps = lead, BaselineShift>0+color = bullet, <8pt = caption
- 387 elementů z Memory_044-077 sample (225 body, 44 lead, 27 heading, 27 separator...)

---

## 2026-03-06 — Illustrator ExtendScript

### JSON serialization povinná
- `return results` vrací `[object Object]` — VŽDY `return JSON.stringify(results)`

### Kritický bug: \r v textech
- Illustrator používá `\r` pro zalomení řádku, matchování MUSÍ mít `\r`

### Velké výstupy
- ExtendScript výsledky > 25000 tokenů → delegovat na sub-agenta

### Cesty a export
- Forward slashe `C:/Users/...` pro `new File()` v ExtendScript
- MCP `export_png` komolí Windows cesty → přímo `doc.exportFile()` přes ExtendScript

---

## 2026-03-06 — Svelte 5 konvence

### Runes syntax
- `$props()`, `$state()`, `$derived()`, `$bindable()`
- `onclick` ne `on:click` (Svelte 5 breaking change)

### Model konzistence
- Pole `TextElement.contents` (ne `original`!) — frontend i backend musí být konzistentní

### Upload response
- Oba upload endpointy vracejí celý `project` objekt (ne dict s metadata)

---

## 2026-03-06 — Infra / Windows

### Port konflikty
- Při testu zabít starý uvicorn process: `netstat -ano | grep PORT`

### CEP Plugin Setup (Illustrator 2026, v30.2.1)
- PlayerDebugMode: HKLM (admin), CSXS.12
- Registry: `HKLM\Software\Adobe\CSXS.12\PlayerDebugMode = "1"` (REG_SZ)
- CEP plugin: `C:\Users\stock\Tools\adb-mcp\cep\com.mikechambers.ai\`

---

## 2026-03-06 — Claude Desktop stabilita

### Příliš mnoho MCP serverů = crash
- 9 serverů (~160+ nástrojů) + velké MEMORY.md = přetečení kontextu při startu
- Odstraněno: `claude-code` MCP (duplikát), `photoshop-mcp` (duplikát), `playwright` (Desktop má Chrome)
- Pravidlo: Max 6 MCP serverů v Desktop, detaily do docs/ ne do MEMORY.md
