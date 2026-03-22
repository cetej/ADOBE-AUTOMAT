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

## Session 8: Pokročilé funkce (volitelná)
**Cíl:** Rozšíření pro power users.

### Možné úkoly
1. **Style transfer** — upload libovolného IDML → extrakce stylu → nový profil
2. **Batch generování** — více variant layoutu z jednoho vstupu (A/B testování kompozice)
3. **Template editor** — uživatel může vytvořit vlastní spread pattern
4. **PDF preview** — vygenerovat PDF náhled přímo v browseru (bez InDesignu)
5. **Caption matching** — AI přiřadí popisky k fotkám na základě obsahu
6. **Multi-article** — layout pro celé číslo (více reportáží + frontmatter)
7. **Illustrator integration** — export map/infografik do layoutu

---

## Technické závislosti

| Závislost | Účel | Stav |
|-----------|------|------|
| `Pillow` | Image processing, thumbnaily | Pravděpodobně už v projektu |
| `Jinja2` | XML šablony pro IDML builder | Nutno přidat |
| Claude API | Layout planning, image analysis | Již v projektu |
| `python-docx` | Parsing text z DOCX uploadu | Již v projektu |

## Rizika

| Riziko | Mitigace |
|--------|----------|
| IDML builder — soubor se neotevře v InDesignu | Skeleton IDML přístup (vycházet z reálného souboru), iterativní testování |
| Layout planner — AI navrhne nerealizovatelnou kompozici | Validace plánu proti constraints (min velikost rámce, overlap detection) |
| Příliš mnoho spread patterns → nepřehledné | Začít s 5-6 ověřenými, rozšiřovat postupně |
| Performance — velké fotky → pomalý upload | Resize na serveru, progress indikátor |
| Fonty — NG používá licencované fonty | Skeleton IDML je obsahuje, builder je referencuje |

## Odhad rozsahu

| Session | Hlavní téma | Klíčový výstup | Náročnost |
|---------|------------|----------------|-----------|
| 1 | Template Analyzer | JSON analýza existujících IDML | ⭐⭐ |
| 2 | Pattern Library | Katalog spread typů + style profiles | ⭐⭐ |
| 3 | IDML Builder | Programatická tvorba IDML | ⭐⭐⭐⭐ |
| 4 | Layout Planner | AI/rule-based kompozice | ⭐⭐⭐ |
| 5 | Backend API | REST endpointy, pipeline | ⭐⭐ |
| 6 | Frontend UI | Dashboard redesign + Layout Wizard | ⭐⭐⭐ |
| 7 | Preview & Polish | Vizuální preview, drag-and-drop, UX | ⭐⭐⭐ |
| 8 | Pokročilé (opt.) | Style transfer, batch, editor | ⭐⭐ |

**Celkem:** 7 povinných sessions + 1 volitelná
**Kritická cesta:** Session 1 → 2 → 3 → 4 → 5 → 6 → 7 (sekvenční závislost)
