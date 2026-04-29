# TROUBLESHOOTING — ADOBE-AUTOMAT

Řešení známých problémů. Nejnovější nahoře.

---

## AI překlad — cyrilice v českém textu (`sesuvы`, `Aktivní сesuvy`)

**Příznaky**: V přeloženém textu se objeví znaky vypadající jako latinka, ale jsou ve skutečnosti cyrilské. Typický pozorovaný případ: `'sesuvы'` (s cyrilským `ы` U+044B místo `y`). Vizuálně skoro k nerozeznání.

**Příčina**: Halucinace Claude. U slov, která mají blízkou ruskou variantu, model občas zaplete cyrilský homoglyph. Není to v post-processingu — Claude to vrací rovnou v překladu. Nemá to spojitost s API klíčem ani parsováním.

**Detekce**:
```python
# Najít všechny elementy projektu s cyrilicí
import json, unicodedata
d = json.loads(open('data/projects/<id>.json', encoding='utf-8').read())
for e in d['elements']:
    cz = e.get('czech') or ''
    cyr = [(i, c, unicodedata.name(c, '?')) for i, c in enumerate(cz) if 0x0400 <= ord(c) <= 0x04FF]
    if cyr:
        print(e['id'], repr(cz), cyr)
```

**Řešení (deterministický cleanup)**:

`translation_service._strip_cyrillic_homoglyphs()` — volaný v `translate_batch()` po každém API volání. Mapuje vizuálně identické cyrilské znaky na latinské (`а→a`, `е→e`, `о→o`, `р→p`, `с→c`, `у→y`, `ы→y`, `х→x`, `и→i`, `й→j` + uppercase). Loguje:
- `WARNING: CyrillicGuard: N homoglyphu nahrazeno latinkou` — bylo nutné fixnout
- `WARNING: CyrillicGuard: M cyrilskych znaku bez mappingu` — exotický cyrilský znak (např. `ж`, `б`), nezná, ponechán → manuální revize v editoru

**Prevence (prompt)**: SYSTEM_PROMPT obsahuje sekci „ABECEDA — KRITICKÉ" s explicitním zákazem cyrilice a příkladem `sesuvy` vs `sesuvы`. Snižuje frekvenci, ale nemá 100% spolehlivost — proto je deterministický stripper potřeba.

**Manuální oprava existujících projektů**:
```python
# Hromadný fix v JSON projektu
for e in d['elements']:
    if e.get('czech') and 'ы' in e['czech']:
        e['czech'] = e['czech'].replace('ы', 'y')
```

**Test fixture**: `backend/tests/test_translation_parsing.py` — test_cyrillic_yeru_replaced (regression z Alaska mapy).

---

## AI překlad mapy — `Claude API vratil neplatny JSON`

**Příznaky**: V backend logu `ERROR: Neplatny JSON (len=N): Invalid control character at: line X column Y` nebo `Expecting value: line 1 column 2`. UI ukazuje chybu překladu (někdy se může jevit jako problém s API klíčem — není).

**Diagnostika**:
1. V logu hledej řádek nad chybou: `INFO: Claude API: preklady N textu`. Pokud tam je → API klíč funguje, problém je v parsování.
2. Zkontroluj JSON v error message — pokud obsahuje raw newlines uvnitř stringu (`"czech": "Smer<LF>pohledu"`) → control chars uvnitř stringu.
3. Pokud obsahuje `
` mimo string (`[
 {`) → někdo v kódu udělal blanket `re.sub(r'[\x00-\x1f]', ...)` — rozbil tím whitespace mezi JSON tokens.

**Řešení**: Parsování v `translation_service.py:_translate_api_call` musí jít cestou:
1. `json.loads(text)` — primary
2. `_escape_control_chars_in_strings(text)` — escapuje raw LF/CR/TAB JEN uvnitř stringů (drží state in_string)
3. `_fix_unescaped_quotes(text)` — escapuje rogue `"` uvnitř stringů
4. raise

**Prevence**: Nikdy nepoužívej blanket regex `[\x00-\x1f]` na celý JSON dokument — JSON spec povoluje raw LF/CR/TAB jako whitespace mezi tokens. Sanitize musí být parser-aware.

**Související**: `text_extractor.py:55-58` má symetrický cleanup ve směru Illustrator→backend (Illustrator používá `\r` pro newlines v textu). Pokud přidáváš novou cestu LLM/external→Python, zkontroluj, že obě strany mají stejně robustní sanitize.

---

## AI překlad — `KeyError: 'czech'` po úspěšném API volání

**Příznaky**: V logu `Claude API: prelozeno N textu` (úspěch), ale hned poté `[routers.translate] ERROR: Chyba prekladu: 'czech'` + `KeyError: 'czech'`. Žádné elementy se nenaaplikují.

**Příčina**: Claude vrací JSON s klíčem `"text"` (nebo `"translation"`/`"cs"`) místo `"czech"`. Stává se, když vstupní items používají stejný klíč jako očekávaný výstup — model **kopíruje klíč ze vstupu** ve výstupu, i když system prompt explicitně říká jinak.

**Řešení**:
1. **Defense 1 — odlišit vstupní a výstupní klíč**: vstup `"en"`, výstup `"czech"` (`translation_service.py:463`).
2. **Defense 2 — explicitní instrukce v user promptu**: `Vrať: [{"id": "...", "czech": "..."}]` — nikdy `text`. User prompt má vyšší adherenci než system.
3. **Defense 3 — tolerantní mapping** (`routers/translate.py:155-180`): `r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")` + warning logging. Pojistka pro případ, že 1+2 selžou.

**Diagnostický signál**: Po retestu sleduj `Preklad: N vysledku melo nestandardni klic` warning v logu — pokud se objeví, defense 1+2 nestačí a model i přes prompt halucinuje. Pokud warning není, prompt drží.

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
