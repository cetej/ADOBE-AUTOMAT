# LEARNINGS — ADOBE-AUTOMAT

Poučení z vývoje. Nejnovější záznamy nahoře.

---

## 2026-04-30 — Cross-batch konzistence v překladu: pre-deduplikace v `translate_batch`

**Kontext:** Pravidlo č. 6 v `SYSTEM_PROMPT` říká „stejný EN → stejný CZ napříč dokumentem", ale Claude ho **nedrží napříč batchy**. Migration mapa (131 elementů, 6 batchů) měla 3 elementy se stejným EN `COMMON WET SEASON RANGE`, ale 2 různé CZ překlady — protože každý batch je samostatné API volání bez paměti.

**Pravidlo v promptu nestačí, když architektura porušuje invariant.** Claude může číst pravidlo a chtít ho dodržovat, ale nemá data — předchozí batche nevidí.

**Řešení:** pre-deduplikace v `translate_batch()` — místo posílat všech N elementů, skupinujeme podle `el.contents` a posíláme jen unikátní reprezentanty. Po API volání rozšíříme výsledek na všechny duplicates ve skupině.

**Architektura:**
```python
en_groups = OrderedDict()
for el in to_translate:
    en_groups.setdefault(el.contents, []).append(el)

unique_to_translate = [grp[0] for grp in en_groups.values()]
# ... API call jen na unique ...
for grp in en_groups.values():
    cz = rep_id_to_cz.get(grp[0].id)
    for el in grp:
        all_results.append({"id": el.id, "czech": cz})
```

**Empirický výsledek (Migration retranslate):**
- Před: `total_batches=6`, 3 elementy se 2 různými CZ
- Po: `total_batches=4` (33 % úspora API volání), 0 mismatched EN→CZ párů

**Generální princip:** invariant „konzistence napříč více volání" musí být zaručen **strukturou kódu**, ne instrukcí v promptu. Pokud LLM nemá kontext, nemůže rozhodnout konzistentně.

**Lekce pro budoucí pipeline:** pokaždé, když máš v promptu pravidlo typu „buď konzistentní s/zachovej napříč X", zeptej se: má model k tomu data? Pokud ne, oprav strukturu, ne prompt.

**Soubory:**
- `backend/services/translation_service.py:translate_batch` — pre-deduplikace + expanze výsledku
- `backend/scripts/audit_maps.py` — heuristický audit pro detekci inkonzistencí
- `backend/scripts/retranslate_batch.py` — paralelní retranslate více map

**Empirické výsledky napříč 8 mapami (2 retranslate iterace + manuální cleanup):**
- INCONSISTENT: 25 → **0** (-100 %)
- CAPS: 63 → **22** (-65 %, zbytek vše FP — vlastní jména / ALL CAPS / věty)
- 35 manuálních fixů (předložky, kapitalizace popisků, halucinace `Aralqum`, kanonizace terminologie)

---

## 2026-04-29 — Geografické názvy: prompt-level pravidla pro konzistenci

**Kontext:** Po fix cyrilice se v Alaska mapě objevila další třída chyb — nekonzistentní překlad geografických názvů. Stejný term `Barry Arm` byl ve dvou vrstvách jednou `záliv Barry`, podruhé `Barry Arm`. `Glenn Highway`, `Seward Highway` zůstávaly v angličtině. „To Prince William Sound" → „Ke Prince William Sound" (předložka „ke" + 1. pád = nesmysl).

**Příčina:** Původní `SYSTEM_PROMPT` měl jen vágní `## ZEMĚPISNÉ NÁZVY` s 3 příklady (Vienna→Vídeň, Reykjavík). Claude se rozhodoval **statisticky** — kde viděl v tréninku víc překlady, tam přeložil; kde viděl víc originál, ponechal. Bez tvrdých pravidel = inkonzistence.

**Řešení — 6 explicitních pravidel** v sekci „ZEMĚPISNÉ NÁZVY — TVRDÁ PRAVIDLA":
1. Generikum se VŽDY překládá (tabulka 25+ generik: Lake→jezero, Arm/Sound/Bay→záliv, Highway→dálnice, Mountains→pohoří, Passage→průliv, Canal→průplav, atd.)
2. Vlastní jméno se NEPŘEKLÁDÁ
3. Pořadí: česky `[generikum] [Vlastní]` — opačně než EN
4. Skloňování: skloňuje se POUZE generikum (nejvyšší impact: „k zálivu Prince William", ne „Ke Prince William Sound")
5. Sídla — výjimka, NEPŘEKLÁDAJÍ se (Glacier View, Victory Bible Camp)
6. Konzistence napříč dokumentem — stejný term vždy stejný překlad

**Empirický výsledek (retranslate Alaska, overwrite=True):**

| | Před | Po |
|---|---|---|
| `Barry Arm` (Landslides) | `Barry Arm` ❌ | `záliv Barry` ✅ |
| `Barry Arm` (Hydro) | `záliv Barry` ✅ | `záliv Barry` ✅ |
| `Glenn Highway` | `Glenn Highway` ❌ | `dálnice Glenn` ✅ |
| `Seward Highway` | `Seward Highway` ❌ | `dálnice Seward` ✅ |
| `To Prince William Sound` | `Ke Prince William Sound` ❌ | `K zálivu Prince William` ✅ |
| `Barry Arm tsunami arrival time` | `Čas příchodu tsunami z Barry Arm` ⚠️ | `Čas příchodu tsunami ze zálivu Barry` ✅ |
| `Glacier View` (sídlo) | `Glacier View` ✅ | `Glacier View` ✅ |
| `Alaska Marine Highway` | `Alaska Marine Highway` ⚠️ | `Alaska Marine Highway` ⚠️ (sporné — proper název ferry systému) |

**10 z 23 klíčových termínů** opraveno, **konzistence napříč vrstvami** (rule 6) drží. Cena ~$0.085 za retranslate, ~50 sekund.

**Lekce:** vágní prompt = statistický výstup. Pro doménu, kde existuje **deterministická editorská konvence** (NG kartografie), prompt MUSÍ obsahovat tvrdá pravidla a vyčerpávající tabulku známých případů. „Příklady" v promptu nestačí — model je interpretuje jako sugesci, ne pravidlo.

**Princip:** invariant je tvrdé tehdy, když ho lze unit-testnout. „Lake → jezero" je tvrdé. „Zachovej diakritiku" je měkké.

**Soubory:**
- `backend/services/translation_service.py:170-220` — sekce „ZEMĚPISNÉ NÁZVY — TVRDÁ PRAVIDLA"
- `backend/services/translation_service.py:_CYRILLIC_TO_LATIN` — rozšířen o н/т/к/м (Claude haluje) a ь/ъ (vyhodit)

---

## 2026-04-29 — Cyrilice v českém překladu (halucinace homoglyphů)

**Kontext:** V mapě Alaska_v16 se ve 2 elementech ze 120 objevil text `'Aktivní\nsesuvы'` — poslední znak je cyrilské `ы` (U+044B), ne latinské `y`. Vizuálně k nerozeznání, ale funkčně chyba (search/grep/export to nepozná, write-back zpátky do AI by to mohl pokazit).

**Příčina:** Halucinace Claude. U slov s blízkou ruskou variantou model tu a tam zaplete cyrilský homoglyph. System prompt to předtím nezakazoval (prompt obsahoval „diakritika vždy správně" — ale to o cyrilici nic neříká).

**Architektonický princip — defense in depth pro LLM výstup:**

LLM nikdy nemá deterministickou záruku na žádný invariant. Ke každému invariantu, který je pro doménu kritický, je potřeba:
1. **Prompt-level** — explicit zákaz/požadavek (snižuje frekvenci, ne k 0)
2. **Post-processing detektor** — deterministické pravidlo, které invariant zkontroluje
3. **Auto-fix nebo eskalace** — pokud se dá deterministicky opravit (homoglyph mapping), opravit; jinak označit a hodit na uživatele

V překladu už máme tuhle vrstvu pro:
- Em-dash → en-dash (`routers/translate.py:162`)
- Kanonická terminologie (Glossary Enforcer)
- Typografie + anglicismy (CzechCorrector)

Cyrilice byla blind spot. Přidán `_strip_cyrillic_homoglyphs` v `translation_service.py` se stejnou strukturou jako ostatní (mapping + log + apply).

**Mapping je konzervativní:** jen vizuálně identické nebo skoro identické (`а→a`, `е→e`, `о→o`, `р→p`, `с→c`, `у→y`, `х→x`, `і→i`, `ј→j`, `ы→y`, `и→i`, `й→j` + uppercase). Cyrilice mimo mapping (např. `б`, `ж`, `ш`) se nemění a logujeme warning — uživatel uvidí v editoru a rozhodne.

**Lekce:** vždycky se zeptej _„který invariant z této domény LLM porušuje statisticky? a mám pro něj deterministický check?"_. Pokud check chybí, blind spot. Sebenáročnější prompt to nezachrání.

**Soubory:**
- `backend/services/translation_service.py:345-400` — `_CYRILLIC_TO_LATIN` mapping + `_strip_cyrillic_homoglyphs` helper
- `backend/services/translation_service.py:300-318` — volání v `translate_batch` před glossary enforcerem
- `backend/services/translation_service.py:213-216` — prompt sekce „ABECEDA — KRITICKÉ"
- `backend/tests/test_translation_parsing.py` — 6 regression testů

---

## 2026-04-29 — LLM JSON odpovědi: dva nezávislé failure modes při překladu mapy

**Kontext:** AI překlad u mapy `NGM_2605_Alaska_v16_FINAL2_FP_METRIC` (120 elementů, 27 % s `\n` v contents typu „Direction\nof View") tiše kolaboval. Symptom: `ValueError: Claude API vratil neplatny JSON`. Předchozí mapy fungovaly — nepoznaný regression.

**Dva nezávislé bugy se aktivovaly současně:**

### Bug 1 — raw control chars uvnitř JSON stringu

Claude při překladu víceřádkového vstupu (`"Direction" + LF + "of View"`) vrací překlad **se stejným raw LF uvnitř JSON stringu**:
```
[{"id": "x", "czech": "Smer
pohledu"}]
```
RFC 8259 to zakazuje (control chars uvnitř stringu MUSÍ být escapované jako `\n` nebo `
`). `json.loads()` padne s `Invalid control character at: line N column M`.

Sourozenecký modul `text_extractor.py` to už řeší ve směru Illustrator→backend (Illustrator používá `\r`), ale ve směru Claude→backend chyběla symetrická obrana.

### Bug 2 — můj první fix byl tupý

První pokus: `re.sub(r'[\x00-\x1f]', escape, text)` na celém JSON. **To rozbije strukturu** — JSON spec povoluje `LF`, `CR`, `TAB` jako legitimní whitespace **mezi tokens**. Můj cleanup je escapnul taky → `[
 {
 "id"...` — `\u` mimo string není JSON, parser padá s `Expecting value: line 1 column 2`.

**Lekce:** sanitize JSON musí být **parser-aware** — odlišit „uvnitř stringu" vs „mezi tokens". Helper `_escape_control_chars_in_strings()` v `translation_service.py` drží jednoduchý state (in_string, escape_next).

### Bug 3 — Claude halucinuje vstupní klíč ve výstupu

Po fix 1+2 přijela další chyba: `KeyError: 'czech'`. Claude vracel `[{"id": "...", "text": "<překlad>"}]` místo `"czech"`. Když má vstup i výstup stejné schéma s klíčem `text`, model **kopíruje klíč ze vstupu** — což zní jako pravděpodobné chování i při velmi explicitním promptu.

**Řešení (víc vrstev defense-in-depth):**
1. **Vstupní klíč jiný než výstupní** — vstup `"en"`, výstup `"czech"`. Claude pak nemá důvod kopírovat.
2. **Explicitní instrukce v user promptu** (ne jen system): „VSTUP klíč `en`, VÝSTUP klíč `czech`, nikdy `text`/`en`/`translation`". User prompt má v praxi vyšší adherenci než system prompt.
3. **Tolerant mapping** v `routers/translate.py:_run_translation` — `r.get("czech") or r.get("text") or r.get("translation") or r.get("cs")` + warning logging kolik výsledků mělo nestandardní klíč. Defenzivně zachytí, kdyby zpřísnění promptu selhalo.

**Verifikace fix v3:** 120 elementů přeloženo, 5 batchů, žádný recovery branch nepoužit, žádná halucinace klíče.

**Generální princip — sanitize symetrie:** Všude, kde JSON přechází mezi systémy (Illustrator↔Python, Claude↔Python, frontend↔backend), je třeba mít stejnou kvalitu sanitize na **obou stranách**. Cleanup v `text_extractor.py` byl implementovaný proaktivně, v `translation_service.py` chyběl — protože dlouho neselhal. Mapa s vysokým podílem víceřádkového vstupu byla první trigger.

**Soubory:**
- `backend/services/translation_service.py:345-380` — `_escape_control_chars_in_strings` helper
- `backend/services/translation_service.py:520-540` — strategie parsování (try → escape → fix quotes → raise)
- `backend/services/translation_service.py:463,478` — vstupní klíč `en` + explicitní prompt
- `backend/routers/translate.py:155-180` — tolerantní mapping s warning logging

---

## 2026-04-18 — Glossary Enforcer: post-LLM DB substituce (P0 z audit TASK)

**Kontext:** Audit `docs/TASK_term_verification_audit.md` odhalil, že `termdb.db` (246K+) byla v překladu jen **soft hint** v systém promptu. LLM mohl přepsat kanonické názvy vlastními (pattern co selhal v NG-ROBOT: "lesňáček cerulea" místo "lesňáček modropláštíkový").

**Implementace:**
- Nový modul `backend/services/glossary_enforcer.py` — post-LLM deterministický override
- Napojeno do `translation_service.translate_batch()` za `_translate_api_call()`
- Zpřísnění direktivy v `SYSTEM_PROMPT` a `_build_term_hints()`: "ZAKÁZÁNO překládat tyto termíny vlastními slovy"
- Write-protection v `write_back_to_termdb()`: pokud DB už kanonický překlad má a liší se, nezapisovat (ochrana proti kontaminaci 246K DB)

**Kritický nález: `NormalizedTermDB.batch_translate()` a `.lookup()` dělají LIKE '%x%' fuzzy search**
- `'London'` → vrátí `'pamlok omejský'` (salamandr *Batrachuperus londongensis* obsahuje substring "London")
- Pro enforcer **NEPOUŽITELNÉ** — enforcer musí dělat exact SQL match na `canonical_name` + fallback přes EN alias kde `canonical_name == EN translation`
- Lekce: fuzzy search API je OK pro hints/suggestions, ale pro deterministický override je potřeba EXACT match

**Ochrana proti false positives (zjištěné při testu na 7 reálných projektech):**
1. **Krátké tokeny (len<4)**: `'of'→'OF'`, `'by'→'By'`, `'is'→'IS'` — DB obsahuje zrcadlové (identita) záznamy pro stopwords
2. **Zrcadlové záznamy obecně**: pokud `cs == en` case-insensitive, ignorovat
3. **Meta-anotované varianty**: `'Brattahlíð (ponechat, historický název)'`, `'Středověké klimatické optimum / středověká teplá perioda'` — DB obsahuje editorské poznámky v závorkách a lomítkové alternativy, enforcer je nesmí přebírat jako kanonikum
4. **Synonymy ochrana**: pokud LLM výstup je v množině CS variant pro daný canonical, neměnit (např. "London"→"Londýn" i "London" jsou DB variants)

**Výsledky na 7 reálných projektech (819 přeložených elementů):**
- 15 fixes (1.8%) — geografická transliterace (Amu Darya→Amudarja, Syr Darya→Syrdarja), oprava kanonického názvu (Aral Sea→Aralské jezero), biologické druhy
- Známý limit: enforcer přepíše skloněný tvar na nominativ (`'mědi' → 'měď'`, `'pracovní paměti' → 'pracovní paměť'`). V krátkých IDML popiscích typicky správné, v delším textu může narušit gramatiku. Editor umožňuje manual revert.

**Klíčové reference:**
- NG-ROBOT Phase 1.5: `C:\Users\stock\Documents\000_NGM\NG-ROBOT\claude_processor\glossary_enforcer.py` (biology-specific, italic Latin pattern matching)
- ADOBE-AUTOMAT varianta: per-element exact match (elementy jsou KRÁTKÉ 1-15 slov, ne dlouhé články)

---

## 2026-03-23 — Kritický bugfix: Layout Generator text mapping

**Problém:** Text se do generovaného IDML nedostával. Headline a deck fungovaly, ale body text, captions, pull quotes, bio, credits — vše bylo prázdné.

**Příčina:** Systémový nesoulad klíčů mezi 3 vrstvami:
- **Router** ukládal `pullquote_0` (bez podtržítka), planner přiřazoval `pull_quote_0` (s podtržítkem)
- **Planner** přiřazoval body text jako `body_0`, `body_1`, ale pattern sloty se jmenují `body_text`
- **Closing spread**: planner přiřazoval `closing_text`, `bio`, `credits` — pattern má `body_text`, `sidebar`, `credit`
- **Captions**: planner `caption_0` vs. pattern `caption_1`, `caption_row1` — indexy nesedí

**Řešení (3 soubory):**
1. `routers/layout.py` — router nyní spojuje body odstavce per spread (ne individuálně), pullquotes s `pull_quote_` (podtržítko), přidává closing_text/bio/credits
2. `idml_builder.py` (`build_from_plan` + multi-article verze) — nová mapping vrstva: section_id → slot_id s fallbacky (body→body_text|sidebar, caption sekvenčně do caption slotů, bio→sidebar, credits→credit)
3. `layout_planner.py` — `_select_body_pattern` — photo_grid jen pro ≤300 znaků textu (grid nemá body_text slot)

**Poučení:**
- Při designu pipeline s named slots: **definovat ID konvenci jednou** a sdílet mezi vrstvami
- Caption/body/pullquote indexy z planneru se NESMÍ matchovat přes přímý slot lookup (caption_1 z planneru ≠ caption_1 slot v patternu)
- Vždy E2E testovat s reálným textem a ověřovat obsah ZIP výstupu

---

## 2026-03-23 — Session 11: Illustrator Integration (Mapy v layoutu)

**Vytvořeno:**
- `backend/services/layout/map_detector.py` — heuristická detekce map/infografik (filename keywords, aspect ratio, caption keywords, content_hint)
- `backend/services/layout/illustrator_exporter.py` — export AI šablony + import editovaných map + resolve helper
- `backend/extendscripts/create_map_template.jsx` — ExtendScript pro vytvoření nového AI dokumentu s crop marks a label vrstvou
- `models_layout.py` → přidán `MapInfo` Pydantic model
- 4 nové API endpointy v `routers/layout.py`: detect-maps, export-map-template, import-edited-map, maps list

**Integrace:**
- `idml_builder.build_from_plan()` — nový parametr `maps_dir`, při generování IDML se kontroluje, zda pro slot existuje editovaná mapa
- `resolve_image_with_maps()` — helper pro rozhodnutí mapa vs. originální obrázek
- Frontend: state variables pro mapy + `detectMaps()`, `exportMapTemplate()`, `importEditedMap()` funkce
- Step 5 toolbar: tlačítko "Detekovat mapy" + MapPanel s per-map akcemi

**Klíčová rozhodnutí:**
- MapCandidate je Python class (ne Pydantic) — confidence se počítá v paměti, serializuje se přes `to_dict()`
- ExtendScript cesta: `parent.parent.parent / "extendscripts"` (3 úrovně: layout/ → services/ → backend/)
- Graceful degradation: pokud Illustrator nepřipojený, API vrátí HTTP 503, frontend zobrazí chybu — mapy se použijí jako běžné obrázky
- Editované mapy se ukládají do `data/layout_projects/{id}/maps/{slot_id}.{ext}` — slot_id je klíč pro resolve

---

## 2026-03-23 — OpenJarvis Adopce: Engine + Registry + Traces

**Inspirace:** Stanford OpenJarvis (open-jarvis/OpenJarvis) — local-first AI framework.
Cherry-picked 3 patterns, zbytek (channels, security, learning/LoRA, DAG workflow) je pro náš use case overkill.

**Vytvořeno (`backend/core/`):**
- `registry.py` — Generic `RegistryBase[T]` s dekorátorovým `@register("key")`. Izolované _registry per subclass.
- `engine.py` — `InferenceEngine` ABC + `AnthropicEngine` implementace. `EngineResult` s cost estimation. Singleton `get_engine()`.
- `traces.py` — `TraceStore` (SQLite), `TraceCollector` (wrapper), `Trace` dataclass. Per-call záznam tokenů, latence, nákladů.

**Refactored:**
- `layout_planner._plan_ai()` — přímé `anthropic.Anthropic()` → `get_engine()` + `TraceCollector`
- `translation_service._translate_api_call()` — `client.messages.create()` → `collector.generate()`
- `ClaudeProcessor.__init__()` — přidán engine + collector, `is_available()` deleguje na `engine.health()`
- `ClaudeProcessor.process()` — trace záznam po každém streaming volání

**API endpointy:**
- `GET /api/traces/summary?since=&until=&module=` — agregované statistiky
- `GET /api/traces/recent?limit=20` — posledních N volání

**Klíčová rozhodnutí:**
- ClaudeProcessor zachovává přímý streaming přes `client.messages.stream()` — Engine abstrakce je pro non-streaming a trace tracking. Streaming vyžaduje granulární kontrolu nad events (thinking blocks, tool_use, cache stats).
- `TraceStore` používá persistent SQLite connection pro `:memory:` mode (každý `sqlite3.connect(':memory:')` vytváří novou prázdnou DB).
- Cost estimation je hardcoded tabulka (Anthropic pricing 2026-03) — stačí pro interní monitoring, přesné billing info je v API dashboard.
- `get_engine()` je singleton — jeden engine per process. Pro multi-model routing stačí volat `engine.generate(model="haiku")`.

**Architektonické poučení:**
- OpenJarvis Registry pattern je elegantní ale pro náš scope (3 moduly, 1 engine) je registrace dekorátorem spíš pro budoucí rozšiřitelnost. Dnes stačí `get_engine()`.
- TraceCollector jako wrapper je čistší než inline tracking — přidá se jednou a pak se nemusí řešit v každém modulu.

---

## 2026-03-22 — Frontend Dashboard + Layout Wizard (Session 6)

**Vytvořeno:**
- `Dashboard.svelte` redesign: dva sloupce (Lokalizace | Layout Generator) + záložky Lokalizace/Layouty
- `LayoutWizard.svelte` — 6-step wizard (Styl → Fotky → Text → Nastavení → Plán → Generování)
- `api.js` — 12 nových layout API metod (CRUD, upload, plan, generate, download)
- `router.js` — podpora query params (`?style=xxx`) pro hash router

**Klíčové rozhodnutí:**
- Layout wizard je samostatná stránka (`#layout-wizard` / `#layout-wizard/{projectId}`) — ne pod lokalizačním projektem
- `pendingProjectId` subscriber v App.svelte musel být podmíněn `currentPage !== 'layout-wizard'` — jinak se snažil načíst layout project ID jako lokalizační projekt (404 → redirect na dashboard)
- Props z `$props()` inicializované do `$state()` zachytí jen initial value (Svelte 5 warning `state_referenced_locally`) — v tomto případě OK, protože se mění jen jednou při mount

**Architektura wizardu:**
- Step detection z `projectMeta.phase`: created→1, images_uploaded→3, text_uploaded→4, planned→5, generated→6
- Polling pattern pro plan/generate (stejný jako translate/pipeline) — `setInterval` s 1s, čeká na `status: done|error`
- Image preview: `URL.createObjectURL()` pro lokální náhledy před uploadem, hero designation click-to-set
- Spread miniatura: pozice slotů relativně z layout plánu (`slot.x/990*100%`), barvy podle typu (zelená=image, modrá=text)

---

## 2026-03-22 — Backend API + Integration Pipeline (Session 5)

**Vytvořeno:**
- `backend/routers/layout.py` — 14 REST API endpointů pro celý layout workflow
- Layout projekt storage: `data/layout_projects/{id}/` (meta.json, images/, plan, idml)

**Architektura:**
- Async generování s polling (stejný pattern jako pipeline.py) — threading.Thread + in-memory progress dict
- Oddělený storage od lokalizačních projektů (layout_projects/ vs projects/)
- Skeleton IDML: auto-detection z `input/samples/`, preferuje menší MF/EP soubory

**Klíčové rozhodnutí:**
- Import fix: layout moduly měly `from backend.models_layout import ...` — opraveno na `from models_layout import ...` (CWD je backend/, konzistentní s routery)
- Layout projekty mají vlastní storage (ne project_store.py) — jiná struktura dat (images, plan, idml vs elements)

**E2E pipeline ověřen:** create → upload images (4) → upload text → plan (rule-based, 3 spreads) → generate IDML (68 KB) → download

---

## 2026-03-22 — Layout Planner: AI kompozice (Session 4)

**Moduly:**
- `image_analyzer.py` — Pillow pro rozměry/EXIF, klasifikace hero/supporting/detail
- `text_parser.py` — strukturovaný (`# HEADLINE:`) i nestrukturovaný text, auto-detekce pull quotes
- `layout_planner.py` — rule-based jádro + volitelný AI-assisted mód (Claude API)

**Klíčové metriky pro odhad prostoru NG textu:**
- ~40 znaků/řádek, ~55 řádků/sloupec → ~2200 znaků/sloupec
- 2 sloupce/stránka = ~4400 znaků/stránka
- Formula: `ceil(body_chars / 4400 / 2) + 2` = počet spreadů (opening + body + closing)

**Pattern selection logika:**
- 3+ fotek → `photo_grid_3x2`
- 1 velká landscape + málo textu → `photo_dominant`
- landscape fotka + text → `body_mixed_top_photo`
- text + fotka → `body_mixed_2col`
- hodně textu, málo fotek → `body_text_3col`

**Pull quote auto-detekce:** Krátké věty (30-150 znaků) s uvozovkami nebo emotivními slovy. Score-based, top 3.

**Nové modely v `models_layout.py`:** `ImageInfo`, `ImagePriority`, `ImageOrientation`, `ArticleText`, `TextEstimate`

---

## 2026-03-22 — IDML Builder: Programatická tvorba IDML

**Klíčové poznatky z implementace IDML Builder (Session 3):**

- **Skeleton IDML přístup**: Vzít reálný NG IDML, kopírovat Resources/Preferences/Fonts/MasterSpreads/XML beze změn, generovat jen nové Spready a Stories. Eliminuje nutnost reverse-engineerovat 100+ KB Styles.xml a Preferences.xml.
- **Spread souřadnicový systém**: Spread origin je v centru spreadu. Levá stránka `ItemTransform="1 0 0 1 -495 -360"`, pravá `"1 0 0 1 0 -360"`. Pro konverzi z absolutních souřadnic: `spread_x = abs_x - 495`, `spread_y = abs_y - 360`.
- **Frame positioning**: "Top-left at origin" pattern — `PathPointArray` definuje obdélník od (0,0) do (w,h), `ItemTransform` translate posune na místo ve spread coords.
- **Frames jsou children of `<Spread>`, NE `<Page>`**. Page element je jen metadata (marginy, guides).
- **Threaded text frames**: Sdílejí `ParentStory` UID, propojeny přes `PreviousTextFrame`/`NextTextFrame` atributy. Jedna Story → mnoho TextFrame.
- **UID generátor**: Formát `u{hex}`, začínat od vysokého čísla (0xA0000+) aby se vyhnul kolizím se skeleton UID.
- **Single page vs double page**: Cover je single-page spread (`PageCount="1"`), reportáže jsou double-page (`PageCount="2"`). Single page má page origin `ItemTransform="1 0 0 1 -{w/2} -{h/2}"`.
- **designmap.xml**: Musí mít `<?aid?>` processing instruction, `StoryList` se všemi story UIDs, a `<idPkg:*>` reference na všechny soubory v ZIPu.

---

## 2026-03-22 — Layout Generator: IDML struktura a NG typografie

**Poznatky z reverse-engineeringu 15 NG IDML souborů (květen 2026):**

- **Stránka NG**: 495×720 pt (6.875"×10"), 12 sloupců, 24pt gutter
- **Marginy**: asymetrické — Top=75, Bottom=84, Left=57, Right=48 pt
- **Fonty**: Marden (headlines), Grosvenor Book (body), Geograph Edit (captions/bylines), Earle (alt headlines), Turnpike (drop caps)
- **IDML atributy**: `Tracking` a `ColumnCount` mohou být float stringy (`"240.00000000000003"`) → vždy `int(float(x))`
- **Frame identifikace**: `TextFrame.ParentStory` → Story XML → `ParagraphStyleRange.AppliedParagraphStyle` → klasifikace (headline/body/caption...)
- **Image frames**: `Rectangle ContentType="GraphicType"`, link v `Link.LinkResourceURI`
- **Spread patterny**: body_mixed (31%), map_infographic (17%), big_picture (16%), photo_grid (16%), opening (6%), closing (5%)
- **Opening spread**: typicky full-bleed fotka přes oba stránky (1008×738pt nebo větší) + overlay titulky
- **Body text**: threaded přes více TextFrames se stejným `ParentStory` ID

---

## 2026-03-22 — PDF matcher NIKDY nepřepisuje contents

**Problém:** PDF source matcher přímo přepisoval `contents` u single-element stories. Nízký práh similarity (0.3) způsobil chybné párování — titulek mapy dostal obsah z jiné story. 5 elementů přepsáno špatným textem.

**Řešení:**
- PDF matcher NIKDY nepíše do `contents` — vše do `notes` jako `[PDF UPDATE]` pro manuální review
- Práh similarity zvýšen z 0.3 na 0.5
- **Pravidlo:** Automatický import z externího zdroje nesmí destruktivně přepisovat primární data.

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
