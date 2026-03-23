# Layout Generator — Plán implementace

## Vize

Nový modul NGM Localizeru: **Layout Generator** — vytváří unikátní IDML layouty
pro reportáže na základě analýzy existujících NG šablon, nahraných fotek a textu.

## Dataset — květnové číslo NG 05/2026

| Soubor | Typ | Stran | Kategorie |
|--------|-----|-------|-----------|
| CV 0526 | Cover | 12 | Cover |
| TC 0526 | Table of Contents | 18 | Frontmatter |
| PG 0526 | Page Guide | 24 | Frontmatter |
| EP 0526 | Editor's Page | 14 | Frontmatter |
| BP 0526 | Big Picture | 32 | Frontmatter |
| Our World 0526 | Our World rubriky | 58 | Frontmatter |
| Secrets of the Bees | Velká reportáž | 76 | Feature |
| Aral Sea | Velká reportáž | 59 | Feature |
| S Sudan Animal Migration | Velká reportáž | 49 | Feature |
| Fecal Archive | Střední reportáž | 40 | Feature |
| MF The Grid-Humanoids | Medium Feature | 20 | MF |
| MF Portfolio-Bike Life | Medium Feature | 19 | MF |
| MF Explorer Spotlight | Medium Feature | 27 | MF |

**Poznámka:** Memory_044-077 je ze speciálu (jiný rozměr), Mohenjo Daro starší — oba jako bonus reference.

## Architektura

```
┌─────────────────────────────────────────────────────┐
│  Frontend — nový Dashboard + Layout Wizard          │
│  (upload fotek, textu, volba stylu, preview)        │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────┐
│  Backend — Layout Engine                            │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Template    │  │  Layout      │  │  IDML      │ │
│  │  Analyzer    │  │  Planner     │  │  Builder   │ │
│  │  (parse NG   │→ │  (AI/rules   │→ │  (generuje │ │
│  │   vzory)     │  │   kompozice) │  │   .idml)   │ │
│  └─────────────┘  └──────────────┘  └────────────┘ │
│         ↑                                     ↓     │
│  data/templates/    Claude API         data/exports/ │
└─────────────────────────────────────────────────────┘
```

---

## Session 1: Template Analyzer — Reverse-engineering IDML layoutů
**Cíl:** Parsovat existující NG IDML a extrahovat layout pravidla do JSON.
**Vstup:** 13 IDML souborů z květnového čísla.

### Úkoly

1. **Analyzovat strukturu IDML spreadu** (30 min)
   - Rozbalit 2-3 IDML (Cover, jednu reportáž, jeden MF)
   - Prostudovat `Spreads/Spread_*.xml` — definice rámců
   - Identifikovat: `TextFrame` vs `Rectangle` (image frame) vs `Group`
   - Mapovat atributy: `ItemTransform`, `PathPointArray`, `ParentStory`
   - Zjistit: rozměry stránky, marginy, sloupce, bleed

2. **Vytvořit `backend/services/layout/template_analyzer.py`** (90 min)
   - `analyze_idml(idml_path) → TemplateAnalysis`
   - Extrahovat pro každý spread:
     - Rozměry stránky (trim box)
     - Pozice a velikosti všech rámců (text/image)
     - Paragraph styles použité v text frames
     - Character styles (fonty, velikosti)
     - Vazby rámec → story (pro identifikaci typu obsahu)
   - Klasifikovat rámce: `HERO_IMAGE`, `BODY_TEXT`, `HEADLINE`, `CAPTION`,
     `PULL_QUOTE`, `FOLIO`, `SIDEBAR`, `BLEED_IMAGE`
   - Výstup: JSON s layout patterny

3. **Vytvořit `backend/models_layout.py`** (30 min)
   - Pydantic modely: `SpreadLayout`, `FrameSpec`, `TemplateAnalysis`,
     `LayoutStyle`, `PageGrid`

4. **Testovat na 3 typech** (30 min)
   - Cover (CV 0526) — specifický 1-stránkový layout
   - Velká reportáž (Secrets of the Bees) — opening + body variety
   - Medium Feature (Grid-Humanoids) — kompaktní layout
   - Identifikovat edge cases (grouped frames, anchored objects, master pages)

### Výstup session
- Funkční analyzer: IDML → JSON popis layoutu
- Uložené analýzy v `data/templates/` jako reference pro planner

---

## Session 2: Layout Pattern Library — Katalog spread typů
**Cíl:** Z analyzovaných IDML vytvořit knihovnu spread patterns + style profiles.

### Úkoly

1. **Batch analýza všech 13 IDML** (60 min)
   - Spustit template_analyzer na celý dataset
   - Identifikovat opakující se spread patterny napříč číslem
   - Katalogizovat typické kompozice:
     - **Opening spread** — full-bleed foto + overlay titulek (reportáže)
     - **Body 2-col** — 2 sloupce textu + 1 fotka (nejčastější)
     - **Body 3-col** — 3 sloupce textu + menší fotky
     - **Photo dominant** — velká fotka přes 60%+ spreadu + caption
     - **Photo grid** — 3-6 fotek v mřížce + krátké texty
     - **Closing** — závěrečný text, menší fotky, byline
     - **Frontmatter item** — 1-2 stránky, headline + lead + fotka
     - **Cover** — full-bleed foto, logo pozice, titulky
     - **TOC spread** — obsah čísla
     - **Big Picture** — full-bleed fotka + minimální text

2. **Vytvořit `backend/services/layout/spread_patterns.py`** (90 min)
   - `SpreadPattern` — abstraktní popis kompozice
   - Každý pattern: seznam `SlotSpec` (typ=text/image, relativní pozice a velikost)
   - Patterns parametrizované — proporce, ne fixní pixely
   - `pattern.instantiate(page_width, page_height, margins) → SpreadLayout`

3. **Vytvořit `data/templates/patterns.json`** (30 min)
   - Serializovaná knihovna patterns s metadata

4. **Vytvořit `backend/services/layout/style_profiles.py`** (60 min)
   - `StyleProfile` — typografický profil extrahovaný z NG šablon
   - Fonty, velikosti, řádkování, barvy pro: headline, subhead, body,
     caption, pull quote, folio, byline
   - Paragraph + Character style definice (IDML XML fragmenty)
   - Profily: **NG Feature** (reportáž), **NG Short** (frontmatter/MF)

### Výstup session
- Knihovna 8-12 spread patterns
- 2 style profiles (NG Feature, NG Short)
- Patterns kombinovatelné do sekvence spreadů

---

## Session 3: IDML Builder — Programatická tvorba IDML
**Cíl:** Engine pro generování validních IDML souborů z layout specifikace.
**Nejtěžší session** — IDML builder musí produkovat soubory, které InDesign otevře.

### Úkoly

1. **Deep-dive do IDML struktury pro tvorbu** (60 min)
   - Rozbalit reálný NG IDML, zmapovat povinné soubory:
     - `mimetype`, `designmap.xml`, `META-INF/container.xml`
     - `Resources/Fonts.xml`, `Resources/Styles.xml`, `Resources/Graphic.xml`
     - `Spreads/Spread_*.xml`, `Stories/Story_*.xml`
     - `MasterSpreads/`, `XML/`, `Preferences/`
   - Jak InDesign odkazuje: Story → TextFrame → Spread
   - Jak se definují linked images (Links, MediaMetadata)
   - **Strategie: "skeleton IDML"** — vzít reálný NG IDML, vyprázdnit obsah,
     použít jako základ (obsahuje správné Preferences, Fonts, Graphic nastavení)

2. **Vytvořit `backend/services/layout/idml_builder.py`** (120 min)
   - `IDMLBuilder` třída:
     - `__init__(skeleton_idml, style_profile)`
     - `add_spread(spread_layout)` — přidá spread se specifikovanými rámci
     - `add_text_frame(spread_id, bounds, story_content, paragraph_style)`
     - `add_image_frame(spread_id, bounds, image_path)`
     - `set_styles(style_profile)` — nastaví typografii
     - `build(output_path) → idml_path` — zabalí do IDML
   - **KRITICKÉ:** String replace přístup (stejně jako idml_writeback),
     NE ElementTree.write() — zachovat IDML kompatibilitu
   - UID generátor pro unikátní Self atributy

3. **XML šablony** v `backend/services/layout/templates/` (60 min)
   - `spread.xml.j2` — parametrický spread s rámci
   - `story.xml.j2` — text story s paragraph/character styles
   - Ostatní soubory ze skeleton IDML (kopie s úpravami)

4. **Validace v InDesignu** (30 min)
   - Vygenerovat minimální IDML (1 spread, 1 text frame, 1 image frame)
   - Otevřít v InDesignu přes MCP → ověřit
   - Iterativně fixovat edge cases

### Výstup session
- Funkční IDML builder — z JSON specifikace vytvoří validní IDML
- Ověřeno otevřením v InDesignu

---

## Session 4: Layout Planner — AI kompozice
**Cíl:** Modul pro návrh sekvence spreadů na základě vstupů.

### Úkoly

1. **Vytvořit `backend/services/layout/layout_planner.py`** (90 min)
   - `plan_layout(images, text, style, num_pages) → LayoutPlan`
   - Vstup:
     - `images[]` — cesty + metadata (rozměry, orientace, priorita)
     - `text` — strukturovaný (titulek, lead, body, captions, pull quotes)
     - `style` — odkaz na StyleProfile
     - `num_pages` — požadovaný počet stran (nebo "auto")
   - Logika:
     - Spočítá potřebný prostor pro text (znaky → sloupce → stránky)
     - Vybere opening spread pattern (dle hero fotky)
     - Distribuuje fotky a text do body spreadů
     - Optimalizuje: velké fotky dostanou víc prostoru, malé se seskupí

2. **AI-assisted planning** (60 min)
   - Claude API: "Navrhni kompozici pro reportáž s N fotkami a M znaky textu"
   - Vstup: seznam fotek s rozměry + délka textu + zvolený styl
   - Výstup: JSON s doporučenou sekvencí spread patterns
   - Fallback: rule-based planning pokud AI nedostupné

3. **Image analysis** (60 min)
   - Detekce rozměrů a orientace fotek (Pillow)
   - Claude Vision pro analýzu obsahu fotky (volitelně):
     - Krajina → full-bleed kandidát
     - Portrét → vertikální rámec
     - Detail/makro → menší rámec
   - Přiřazení priority: hero shot, supporting, detail

4. **Text parser** (30 min)
   - Rozdělit vstupní text na sekce: headline, lead, body paragraphs, captions
   - Odhad počtu znaků → potřebný počet text frames
   - Identifikace pull quote kandidátů (krátké, výrazné věty)

### Výstup session
- Layout planner generuje `LayoutPlan` — sekvenci spreadů s přiřazenými fotkami a textem
- Testováno na reálném článku s fotkami

---

## Session 5: Backend API + Integration Pipeline
**Cíl:** REST API endpointy a propojení všech modulů do pipeline.

### Úkoly

1. **Vytvořit `backend/routers/layout.py`** (60 min)
   - `POST /api/layout/analyze-template` — upload IDML vzoru → analýza
   - `POST /api/layout/create-project` — nový layout projekt
   - `POST /api/layout/upload-images` — upload fotek (multipart)
   - `POST /api/layout/upload-text` — upload textu (paste nebo soubor)
   - `POST /api/layout/plan` — spustí layout planner → vrátí LayoutPlan
   - `POST /api/layout/generate` — z LayoutPlan vygeneruje IDML
   - `GET /api/layout/download/{project_id}` — stáhne hotový IDML
   - `GET /api/layout/templates` — seznam dostupných style profiles
   - `GET /api/layout/patterns` — seznam spread patterns

2. **Async generování s progress** (30 min)
   - Polling pattern (jako stávající translate/pipeline)
   - Progress: "Analyzuji fotky..." → "Plánuji layout..." → "Generuji IDML..."

3. **Rozšířit project model** (30 min)
   - `ProjectType.LAYOUT` — nový typ projektu
   - `LayoutProject` model s vazbami na images, text, plan, generated IDML

4. **Registrovat router v `main.py`** (10 min)

5. **End-to-end test** (60 min)
   - Upload fotek + textu → plan → generate → download IDML
   - Ověřit IDML v InDesignu

### Výstup session
- Kompletní backend API
- E2E test projde

---

## Session 6: Frontend — Nový Dashboard + Layout Wizard
**Cíl:** Předělat Dashboard na hub se dvěma směry + vytvořit Layout Wizard UI.

### Úkoly

1. **Redesign Dashboard.svelte** (90 min)
   ```
   ┌──────────────────────────────────────────────────┐
   │              NGM LOCALIZER                       │
   ├───────────────────────┬──────────────────────────┤
   │                       │                          │
   │   📥 LOKALIZACE       │   📐 LAYOUT GENERATOR    │
   │                       │                          │
   │   Drop IDML/AI        │   Vytvoř nový layout     │
   │   pro překlad         │   z fotek a textu        │
   │   a lokalizaci        │                          │
   │                       │   Zvol styl:             │
   │   [Existující         │   • NG Reportáž          │
   │    projekty ↓]        │   • NG Krátká zpráva     │
   │                       │   • Vlastní IDML vzor    │
   │                       │                          │
   │                       │   [Existující layouty ↓] │
   └───────────────────────┴──────────────────────────┘
   ```
   - Stávající drop-zone zůstane (levá část)
   - Nová pravá část: vstup do Layout Wizard
   - Seznam projektů: záložky Lokalizace | Layouty

2. **Vytvořit `frontend/src/pages/LayoutWizard.svelte`** (120 min)
   - **Step 1: Volba stylu** — karty s vizuálním náhledem
   - **Step 2: Upload fotek** — drag-and-drop, grid náhledů, označení hero fotky,
     drag-and-drop řazení priority
   - **Step 3: Vložení textu** — textarea / upload .txt/.docx,
     auto-detekce struktury (headline, lead, body, captions)
   - **Step 4: Nastavení** — počet stran (auto/manual), volba patterns
   - **Step 5: Preview plánu** — miniatury spreadů, přetažení fotek mezi spready
   - **Step 6: Generování** — progress bar, download IDML

3. **Route + navigace** (20 min)
   - `#layout-wizard` a `#layout-wizard/{project_id}` v `stores/router.js`
   - Tab "Layout" v header navigaci `App.svelte`

### Výstup session
- Nový Dashboard se dvěma směry
- Funkční Layout Wizard (6-step flow)
- Propojeno s backend API

---

## Session 7: Preview & Polish
**Cíl:** Vizuální preview spreadů, UX vylepšení, edge cases.

### Úkoly

1. **SpreadPreview.svelte** (90 min)
   - SVG miniatura spreadu — obdélníky rámců (modrá=text, zelená=image)
   - Kliknutí na rámec → detail (jaká fotka, jaký text)
   - Thumbnail fotky v image rámcích

2. **Drag-and-drop editace** (60 min)
   - Přetažení fotky mezi rámci v preview
   - Přetažení celých spreadů pro změnu pořadí
   - Po změně: přepočítání layout plánu

3. **Image processing** (60 min)
   - Thumbnaily pro preview (Pillow)
   - EXIF orientace
   - Crop hints pro různé poměry stran rámců

4. **Edge cases a validace** (30 min)
   - Příliš málo/moc fotek pro zvolený počet stran
   - Příliš dlouhý text → auto přidání stran
   - Chybějící headline → upozornění
   - Neplatné formáty obrázků

5. **UX polish** (30 min)
   - Konzistentní Tailwind styling
   - Loading states, error handling, toast notifikace
   - Keyboard shortcuts

### Výstup session
- Vizuální preview layoutu před generováním
- Drag-and-drop editace plánu
- Ošetřené edge cases

---

## Session 8: Pokročilé funkce ✅ DONE
**Cíl:** Rozšíření pro power users.

### Implementováno
1. ✅ **Style transfer** — upload IDML → extrakce stylu → nový custom profil
2. ✅ **Batch generování** — 3 varianty layoutu (shuffled/inverzní fotky)
3. ✅ **PDF preview** — ReportLab renderování spreadů s reálnými fotkami
4. ✅ **Caption matching** — Claude Vision AI přiřazení popisků k fotkám

### Nové moduly
- `backend/services/layout/pdf_preview.py`
- `backend/services/layout/caption_matcher.py`

---

## Session 9: Template Editor — Vizuální editor spread patterns
**Cíl:** Uživatel může vytvářet a editovat vlastní spread patterns přes drag-and-drop UI.

### Kontext
Aktuálně existuje 9 hardcoded patterns v `spread_patterns.py`. Každý pattern definuje
sloty (SlotSpec) s relativními koordináty 0–1 v rámci spreadu (990×720pt).
Template Editor umožní vizuálně kreslit nové patterns a ukládat je jako custom.

### Úkoly

1. **Backend: Custom pattern persistence** (30 min)
   - `spread_patterns.py`: přidat `register_custom_pattern()`, `delete_custom_pattern()`, `load_custom_patterns()`
   - Ukládání do `data/templates/custom_patterns/` jako JSON (stejný formát jako `patterns.json`)
   - Upravit `get_all_patterns()` — vrátí hardcoded + custom
   - Validace: overlap detection, min velikost slotu (5% × 5%), margin check

2. **Backend: CRUD endpointy pro patterns** (30 min)
   - `POST /api/layout/patterns` — vytvoří nový custom pattern (JSON body)
   - `PUT /api/layout/patterns/{pattern_id}` — update existujícího custom patternu
   - `DELETE /api/layout/patterns/{pattern_id}` — smaže custom pattern
   - `POST /api/layout/patterns/validate` — validace patternu (overlap, min size, required slots)

3. **Frontend: PatternEditor.svelte** (120 min) — hlavní komponenta
   - SVG canvas s přesností na spread (990×720pt mapped do px)
   - **Grid & guides**: marginy (šedě čárkovaně), stránkový střed (svislá čára), volitelný 12-column grid
   - **Kreslení slotů**: kliknutí + tah → nový obdélník → modal s nastavením (slot_type, required, allow_bleed)
   - **Drag-and-drop editace**: přetáhnutí slotu, resize za rohy/hrany, snap to grid/margins
   - **Slot list sidebar**: seznam slotů s typem, pozicí, delete button
   - **Barvy podle typu**: hero_image=zelená, body_text=modrá, headline=fialová (viz SLOT_COLORS z SpreadPreview)
   - **Real-time validace**: červeně zvýraznit překrývající se sloty

4. **Frontend: Integrace do wizardu** (30 min)
   - Nový sub-step v Step 1: vedle výběru stylu → "Vlastní pattern" tlačítko
   - Nebo samostatná stránka `#pattern-editor` s routingem
   - Po uložení: pattern se objeví v pattern selection pro planner

5. **Frontend: Pattern preset templates** (30 min)
   - Tlačítka pro rychlé vytvoření z presetů: "2-sloupcový", "Full-bleed + caption", "Grid 3×2"
   - Preset vyplní sloty do editoru, uživatel je pak doladí

### Koordinátní systém
- Spread: 990×720pt (rel 0–1)
- Levá stránka: x ∈ [0.0, 0.5], Pravá: x ∈ [0.5, 1.0]
- Marginy: LEFT=57pt (0.058), RIGHT=48pt (0.049), TOP=75pt (0.104), BOTTOM=84pt (0.117)
- Snap threshold: 5pt (0.005 rel)

### SlotSpec pole (pro formulář editoru)
```
slot_id: string       — unikátní ID ("headline", "body_text", "image_1"...)
slot_type: FrameType  — dropdown (18 typů: hero_image, body_text, headline...)
rel_x, rel_y: float   — pozice 0–1
rel_width, rel_height: float — rozměr 0–1
required: bool        — povinný slot
allow_bleed: bool     — povolení přesahu přes marginy
default_style: string — název InDesign stylu (volitelné)
```

### Validační pravidla
- Žádné dva sloty se nesmí překrývat (IoU > 0.05 → error)
- Min rozměr slotu: 5% × 5% spreadu (≈50×36pt)
- Pattern musí mít alespoň 1 slot
- Doporučení: alespoň 1 text slot + 1 image slot (warning, ne error)
- `pattern_id` unikátní a safe (kebab-case)

### Klíčové soubory
- Edit: `spread_patterns.py`, `routers/layout.py`, `api.js`
- New: `frontend/src/components/PatternEditor.svelte`, `data/templates/custom_patterns/`

### Výstup session
- Vizuální drag-and-drop editor pro spread patterns
- Custom patterns persistované na disku, použitelné v planneru
- Preset šablony pro rychlé vytvoření

---

## Session 10: Multi-Article — Layout pro celé číslo
**Cíl:** Sestavit layout z více reportáží/rubrik v jednom IDML souboru.

### Kontext
Aktuálně planner zpracovává jeden článek → jeden LayoutPlan → jeden IDML.
Multi-article layout umožní nahrát více článků, přiřadit fotky ke každému,
naplánovat layout pro celé číslo a vygenerovat jeden IDML s article boundaries.

### Úkoly

1. **Backend: MultiArticleText model** (30 min)
   - `models_layout.py`: přidat `ArticleItem(BaseModel)` a `MultiArticleText(BaseModel)`
   ```python
   class ArticleItem(BaseModel):
       article_id: str           # "article_1", "bees"
       headline: str
       deck: Optional[str]
       byline: Optional[str]
       body_paragraphs: list[str]
       captions: list[str]
       pull_quotes: list[str]
       style_profile_id: str = "ng_feature"  # styl per-article

   class MultiArticleText(BaseModel):
       articles: list[ArticleItem]
       credits: Optional[str] = None  # sdílený závěrečný text
   ```

2. **Backend: Multi-article text parser** (30 min)
   - `text_parser.py`: přidat `parse_multi_article_text(raw_text) → MultiArticleText`
   - Delimiter mezi články: `===` nebo `# ARTICLE: Název`
   - Alternativa: upload více textových souborů (každý = jeden článek)

3. **Backend: Multi-article planner** (60 min)
   - `layout_planner.py`: přidat `plan_multi_article_layout()`
   - Pro každý článek samostatný `plan_layout()` → seznam `LayoutPlan[]`
   - `spread_offset` counter pro správné číslování spreadů
   - Přechodové spready: volitelný "section divider" pattern mezi články
   - Image allocation: uživatel přiřadí fotky článkům, zbytek auto-distribute

4. **Backend: Multi-article IDML builder** (60 min)
   - `idml_builder.py`: přidat `build_from_multi_article_plans()`
   - Každý článek = samostatný threaded story (body text nese sám)
   - Mezi články NENÍ text threading link → vizuální oddělení
   - Page numbers continuous (článek 1: strany 1-10, článek 2: 11-18...)
   - Celkový počet stran: součet všech článků

5. **Backend: API endpointy** (60 min)
   - `POST /api/layout/multi/upload-articles/{project_id}` — upload N textových souborů
   - `POST /api/layout/multi/allocate-images/{project_id}` — přiřazení fotek článkům
   - `POST /api/layout/multi/plan/{project_id}` — naplánuje layout pro celé číslo
   - `GET /api/layout/multi/plan/{project_id}/progress` — polling
   - `POST /api/layout/multi/generate/{project_id}` — generuje IDML
   - Projekt meta.json rozšířen: `articles: [{...}]`, `image_allocation: {article_id: [filenames]}`

6. **Frontend: Multi-article wizard mode** (90 min)
   - Step 1: checkbox "Multi-article layout" → aktivuje rozšířený flow
   - Step 3 (Text): místo 1 textarea → dynamický seznam článků
     - "Přidat článek" → nový blok (headline + textarea nebo file upload)
     - Drag-and-drop řazení článků
     - Zobrazení: headline, počet znaků, odhadovaný počet spreadů
   - Step 2.5 (nový): Image allocation
     - Vlevo: grid fotek (ze Step 2)
     - Vpravo: článkové "buckety" — drag fotky do článků
     - Auto-allocate tlačítko (podle pořadí nebo AI)
   - Step 5 (Náhled): článkové záložky nad spread gridem
     - Barevné odlišení spreadů podle článku
     - Vertikální separator mezi články
   - Step 6: download jednoho IDML s celým číslem

### Data flow
```
Upload N textů  →  parse_multi_article_text()  →  MultiArticleText
Upload fotek    →  analyze_batch()              →  ImageInfo[]
Allocate        →  {article_id: [filenames]}    →  image_allocation
Plan            →  plan_multi_article_layout()  →  LayoutPlan[] (jeden per článek)
Generate        →  build_from_multi_article_plans() → jeden .idml
```

### Klíčové designové rozhodnutí
- **Jeden LayoutPlan per článek** (ne jeden mega-plán) — zachovává modularitu
- **Body threading per článek** — každý článek má vlastní story chain
- **Image allocation explicitní** — uživatel řídí, které fotky patří ke kterému článku
- **Style profile per článek** — jeden článek může být "feature", jiný "short"

### Klíčové soubory
- Edit: `models_layout.py`, `text_parser.py`, `layout_planner.py`, `idml_builder.py`, `routers/layout.py`, `api.js`, `LayoutWizard.svelte`
- New: žádné nové moduly (rozšíření stávajících)

### Výstup session
- Upload a parsování více článků
- Vizuální přiřazení fotek článkům
- Plánování a generování multi-article IDML
- Continuous page numbers, article boundaries

---

## Session 11: Illustrator Integration — Mapy a infografiky v layoutu
**Cíl:** Propojit Layout Generator s Illustratorem pro tvorbu a editaci map/infografik.

### Kontext
Projekt už má `illustrator_bridge.py` (Socket.IO → CEP plugin → Illustrator),
`map_writeback.py` a ExtendScript skripty v `backend/extendscripts/`.
Tato session propojí Layout Generator s Illustratorem — detekce map v layoutu,
export šablon do Illustratoru, re-import editovaných map zpět do IDML.

### Předpoklady
- Illustrator běží s připojeným CEP pluginem (port 3001)
- Session 10 (Multi-article) nemusí být hotová — funguje i se single-article

### Úkoly

1. **Backend: Map/infographic detector** (30 min)
   - Nový modul `backend/services/layout/map_detector.py`
   - `detect_maps(images: list[ImageInfo], captions: list[str]) → list[MapCandidate]`
   - Heuristiky:
     - Aspect ratio blízký 1:1 (0.7–1.3) → může být mapa
     - Filename obsahuje "map", "mapa", "infographic", "diagram"
     - Caption obsahuje klíčová slova: "mapa", "diagram", "přehled"
   - Volitelně: Claude Vision analýza (rozpoznat mapy vs fotky)
   - Output: `MapCandidate(image: ImageInfo, confidence: float, map_type: "map"|"infographic"|"diagram")`

2. **Backend: Illustrator template exporter** (60 min)
   - Nový modul `backend/services/layout/illustrator_exporter.py`
   - `export_map_template(slot_bounds: Bounds, style_profile, output_dir) → Path`
   - Vytvoří `.ai` šablonu přes ExtendScript:
     - Nový dokument s rozměry slotu (z layout plánu)
     - Crop marks, bleed guides
     - Textové rámce pro labely (font z style profile)
     - Vrátí cestu k uloženému `.ai` souboru
   - Využití `illustrator_bridge.send_command()` pro komunikaci s Illustratorem

3. **Backend: Map re-import** (30 min)
   - `import_edited_map(map_path: Path, project_id, slot_id) → Path`
   - Illustrator → export jako high-res PNG/PDF
   - Uložit do `data/layout_projects/{id}/maps/`
   - Při generování IDML: nahradit originální fotku editovanou mapou

4. **Backend: API endpointy** (30 min)
   - `POST /api/layout/detect-maps/{project_id}` — detekce map ve fotkách
   - `POST /api/layout/export-map-template/{project_id}` — export šablony do Illustratoru
   - `POST /api/layout/import-edited-map/{project_id}` — upload editované mapy
   - `GET /api/layout/maps/{project_id}` — seznam map (detekovaných + editovaných)

5. **Frontend: Map workflow v Step 5** (60 min)
   - Po plánování: automatická detekce map (async)
   - V pravém panelu detailu spreadu:
     - Pokud slot obsahuje detekovanou mapu → "Otevřít v Illustratoru" tlačítko
     - Status: "Čeká na export" → "Edituje se v Illustratoru" → "Editováno ✓"
   - Import flow: "Importovat editovanou mapu" → file upload → náhrada v plánu
   - Thumbnail aktualizace po importu

6. **Integrace s IDML builderem** (30 min)
   - `idml_builder.py`: při `build_from_plan()` — pokud pro image slot existuje
     editovaná mapa v `maps/`, použít ji místo originální fotky
   - `image_paths` mapování rozšířit: check `maps/` dir first, fallback na `images/`

### Workflow uživatele
```
1. Nahraje fotky (mix fotek + map/infografik)
2. Planner rozloží do spreadů
3. Detector identifikuje mapy (auto nebo manual)
4. Pro každou mapu:
   a. Klik "Otevřít v Illustratoru" → export šablony
   b. Uživatel edituje mapu v Illustratoru
   c. Klik "Importovat" → upload editované verze
5. Generování IDML — použije editované mapy místo originálů
```

### Komunikace s Illustratorem
```
Python → Socket.IO (localhost:3001) → Node.js CEP proxy → Illustrator
         ↕                                    ↕
  illustrator_bridge.py                ExtendScript (.jsx)
```

### Klíčové soubory
- New: `backend/services/layout/map_detector.py`, `backend/services/layout/illustrator_exporter.py`
- Edit: `routers/layout.py`, `idml_builder.py`, `api.js`, `LayoutWizard.svelte`
- Existing: `illustrator_bridge.py`, `extendscripts/`

### Rizika
| Riziko | Mitigace |
|--------|----------|
| Illustrator nepřipojený | Graceful degradation — mapy se použijí jako obrázky |
| ExtendScript selhání | Fallback: manuální export/import (file upload) |
| Rozměry šablony nesedí s IDML slotem | Validace: porovnat rozměry před importem |

### Výstup session
- Automatická detekce map ve fotkách
- Export šablon do Illustratoru
- Re-import editovaných map
- IDML generování s editovanými mapami

---

## Technické závislosti

| Závislost | Účel | Stav |
|-----------|------|------|
| `Pillow` | Image processing, thumbnaily | ✅ V projektu |
| `reportlab` | PDF preview | ✅ Přidáno (Session 8) |
| Claude API | Layout planning, image analysis, caption matching | ✅ V projektu |
| `python-docx` | Parsing text z DOCX uploadu | ✅ V projektu |
| Illustrator CEP plugin | Komunikace s Illustratorem | ✅ V projektu (bridge + extendscripts) |

## Rizika

| Riziko | Mitigace |
|--------|----------|
| IDML builder — soubor se neotevře v InDesignu | Skeleton IDML přístup (vycházet z reálného souboru), iterativní testování |
| Layout planner — AI navrhne nerealizovatelnou kompozici | Validace plánu proti constraints (min velikost rámce, overlap detection) |
| Příliš mnoho spread patterns → nepřehledné | Začít s 5-6 ověřenými, rozšiřovat postupně |
| Performance — velké fotky → pomalý upload | Resize na serveru, progress indikátor |
| Fonty — NG používá licencované fonty | Skeleton IDML je obsahuje, builder je referencuje |
| Multi-article threading — story chains across articles | Každý článek = samostatný story chain, bez cross-article threading |
| Template Editor — overlap detection performance | O(n²) pro N slotů — max ~30 slotů per pattern, performance OK |

## Odhad rozsahu

| Session | Hlavní téma | Klíčový výstup | Náročnost | Stav |
|---------|------------|----------------|-----------|------|
| 1 | Template Analyzer | JSON analýza existujících IDML | ⭐⭐ | ✅ |
| 2 | Pattern Library | Katalog spread typů + style profiles | ⭐⭐ | ✅ |
| 3 | IDML Builder | Programatická tvorba IDML | ⭐⭐⭐⭐ | ✅ |
| 4 | Layout Planner | AI/rule-based kompozice | ⭐⭐⭐ | ✅ |
| 5 | Backend API | REST endpointy, pipeline | ⭐⭐ | ✅ |
| 6 | Frontend UI | Dashboard redesign + Layout Wizard | ⭐⭐⭐ | ✅ |
| 7 | Preview & Polish | Vizuální preview, drag-and-drop, UX | ⭐⭐⭐ | ✅ |
| 8 | Pokročilé funkce | Style transfer, batch, PDF, captions | ⭐⭐ | ✅ |
| 9 | Template Editor | Vizuální editor spread patterns | ⭐⭐⭐ | TODO |
| 10 | Multi-Article | Layout pro celé číslo | ⭐⭐⭐⭐ | TODO |
| 11 | Illustrator | Mapy a infografiky v layoutu | ⭐⭐⭐ | TODO |

**Sessions 1–8:** ✅ Hotovo
**Sessions 9–11:** Připravené plány, nezávislé (lze dělat v libovolném pořadí)
**Doporučené pořadí:** 9 → 10 → 11 (Template Editor je nejjednodušší, Multi-article nejkomplexnější)
