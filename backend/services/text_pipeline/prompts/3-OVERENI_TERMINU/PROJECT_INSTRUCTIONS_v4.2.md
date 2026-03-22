# PROJECT INSTRUCTIONS v4.2: VERIFIED OUTPUT

## CORE CHANGES v4.2
- **DB-FIRST PŘÍSTUP** — nejdřív kontroluj lokální databáze (SpeciesDB, TermDB, Global Ledger), teprve pak web search
- **POVINNÁ CITACE** z WebSearch výsledku — žádné ověření bez důkazu
- **ANTI-HALUCINACE** pravidla
- Max 20 web searches na článek (většina termínů se řeší lokálně)

---

## KROK 0: KONTROLA LOKÁLNÍCH DATABÁZÍ (PŘED web search!)

### Dostupné zdroje (injektovány v kontextu)

| Priorita | Zdroj | Velikost | Jak je poznáš v kontextu |
|----------|-------|----------|--------------------------|
| **1** | SpeciesDB (BioLib/Wikidata/iNat) | 218K+ taxonů | Tabulka "PŘEDBĚŽNĚ OVĚŘENÉ DRUHY" |
| **2** | TermDB (terminology.db) | 1600+ termínů | Blok "TermDB" |
| **3** | Global Ledger | 1200+ termínů | Blok "DŘÍVE OVĚŘENÉ TERMÍNY" |

### Pravidlo DB-FIRST

1. **NEJDŘÍV** projdi dodané tabulky — hledej každý termín z článku v pre-resolved datech
2. Pokud termín JE v tabulce a český název sedí do kontextu → **PŘIJMI BEZ WEB SEARCH**
3. Pokud termín JE v tabulce ale český název nesedí → ověř web searchem (počítej jako HIGH RISK)
4. Pokud termín NENÍ v žádné tabulce → standardní web search postup (HIGH/LOW RISK triage)

⚠️ Pre-resolved druhy z SpeciesDB jsou SPOLEHLIVÉ (218K+ záznamy z BioLib scrape + Wikidata).
Nemusíš je ověřovat znovu — POUZE zkontroluj, zda CZ název sedí v kontextu věty.

---

## KRITICKÉ: ANTI-HALUCINACE PROTOKOL

### ZAKÁZÁNO
- Psát `✓` bez předchozího WebSearch volání (výjimka: pre-resolved z DB)
- Uvádět "zdroj: biolib.cz" bez citace snippetu z výsledku
- Přiřazovat český název bez důkazu z externího zdroje nebo lokální DB
- **VYMÝŠLET ALTERNATIVNÍ ČESKÉ NÁZVY** — pokud snippet/DB obsahuje „juka krátkolistá", NESMÍŠ přidat vlastní variantu jako „jošuovník"
- Kombinovat snippet-ověřený název s vlastním výmyslem
- Tvořit pseudo-české názvy odvozené z angličtiny (např. Joshua → jošuovník)

### POVINNÉ
Každý ověřený termín MUSÍ obsahovat:
1. **Zdroj** — buď "pre-resolved (SpeciesDB/TermDB/ledger)" NEBO snippet z WebSearch
2. **URL** — odkaz z DB/vyhledávání
3. **Extrahovaný název** — český název ZE ZDROJE (a ŽÁDNÝ jiný)

### FORMÁT VÝSTUPU (povinný)
```
pronghorn:
  Zdroj: pre-resolved (SpeciesDB)
  CZ: vidloroh americký
  LAT: Antilocapra americana
  → vidloroh americký ✓ (DB match, kontext OK)

javelina:
  WebSearch: "Pecari tajacu site:biolib.cz"
  Snippet: "Pakůň límcový (Pecari tajacu) | BioLib.cz"
  URL: https://www.biolib.cz/cz/taxon/id1234/
  → pakůň límcový ✓
```

### ČERVENÉ VLAJKY — OKAMŽITĚ ZASTAVIT
- Dva různé anglické termíny → stejný český název = CHYBA
- WebSearch nevrátil snippet s českým názvem = NEOVĚŘENO (ne ✓)
- Latinský název v překladu neodpovídá latinskému názvu ve snippetu = CHYBA
- **Český název, který jsi použil, se NEVYSKYTUJE v žádném snippetu ani DB** = VYMYŠLENÝ TERMÍN → smaž ho

---

## WORKFLOW SUMMARY

```
Lokální DB check → Triage (RESOLVED/HIGH/LOW) → WebSearch pro HIGH RISK → Citace → Výstup
```

**Finální výstupy:** Tabulka TERMINOLOGICKÉ OPRAVY + NEOVĚŘENÉ TERMÍNY + TRIAGE REPORT + STATISTIKY

---

## TIER SYSTÉM (pro web search — jen termíny co NEJSOU v DB)

### BIOLOGICKÉ TERMÍNY
| Tier | Zdroj | Query formát |
|------|-------|--------------|
| **1** | biolib.cz | `{LAT} site:biolib.cz` |
| **2** | cs.wikipedia.org | `{LAT} site:cs.wikipedia.org` |
| **3** | obecné | `"{LAT}" český název` |

### OSTATNÍ DOMÉNY
| Doména | Tier 1 | Query formát |
|--------|--------|--------------|
| Geografie | cs.wikipedia.org | `{termín} site:cs.wikipedia.org` |
| Medicína | wikiskripta.eu | `{termín} site:wikiskripta.eu` |
| Filmy | csfd.cz | `{termín} site:csfd.cz` |

---

## BIOLOGICKÝ PROTOKOL (jen pro druhy co NEJSOU v pre-resolved tabulce)

### ⚠️ TAXONOMIE vs. ŽURNALISTIKA — KRITICKÉ ROZLIŠENÍ

BioLib.cz používá **SYSTEMATICKÉ** názvy — jeden český ekvivalent pro celý rod.
Česká Wikipedia a NG.cz používají **ŽURNALISTICKÉ** názvy — zavedené, srozumitelné čtenáři.

**Tyto dvě konvence se mohou lišit!** Příklady:

| BioLib (systematicky) | Wikipedia/NG.cz (žurnalisticky) | Proč je biolib nevhodný |
|---|---|---|
| axolotl skvrnitý (*Ambystoma maculatum*) | **mlok skvrnitý** | "axolotl" v CZ = jen *A. mexicanum* (neotenie); *A. maculatum* je suchozemský mlok |
| ropucha obrovská (*Rhinella marina*) | **ropucha třtinová** | zavedený žurnalistický název |

**ROZHODOVACÍ PRAVIDLO:**
- Pokud cs.wikipedia.org NEBO nationalgeographic.cz používá jiný zavedený název než biolib.cz → PREFERUJ Wikipedia/NG.cz (žurnalistický standard)
- Pokud žádný žurnalistický alternativní název neexistuje → ponech biolib.cz
- Vždy zapiš do poznámky, pokud se zdroje liší

### Postup (MAX 2 searches per biologický termín)
```
S1: "{EN name} český název site:cs.wikipedia.org OR site:biolib.cz" → merged query, oba zdroje
S2: (jen při rozporu/nejasnosti) web_fetch na biolib/wiki stránku pro kontext
    POKUD stále nenalezeno → označ jako NEOVĚŘENO
```

### Příklad: druh JE v pre-resolved tabulce
```
Termín: "pronghorn"
→ Pre-resolved tabulka: pronghorn | Antilocapra americana | vidloroh americký | SpeciesDB
→ Kontext v článku: "vidloroh americký..." — sedí ✓
→ PŘIJATO BEZ WEB SEARCH

VÝSTUP:
pronghorn → Antilocapra americana → vidloroh americký
  Zdroj: pre-resolved (SpeciesDB), kontext OK [0s]
```

### Příklad: druh NENÍ v tabulce (web search)
```
Termín: "spotted salamander"
→ Není v pre-resolved tabulce → HIGH RISK

S1: WebSearch("spotted salamander český název site:cs.wikipedia.org OR site:biolib.cz")
    Snippet wiki: "Mlok skvrnitý (Ambystoma maculatum) je..."
    Snippet biolib: "axolotl skvrnitý (Ambystoma maculatum) | BioLib.cz"
    → KOLIZE: wiki=mlok, biolib=axolotl

ROZHODNUTÍ: Wikipedia říká "mlok skvrnitý" → PREFERUJI (žurnalistický standard)

VÝSTUP:
spotted salamander → Ambystoma maculatum → mlok skvrnitý
  Důkaz: "Mlok skvrnitý (Ambystoma maculatum)" cs.wikipedia.org
  Poznámka: biolib uvádí "axolotl skvrnitý" (systematický rod)
  [1s, T2 preferováno]
```

### Příklad CHYBNÉHO postupu (ZAKÁZÁNO)
```
CHYBA 1: Ignorovat pre-resolved tabulku a hledat znovu
pronghorn → Antilocapra americana → vidloroh americký [2 zbytečné searches]
  ^^^ CHYBA: Byl v pre-resolved tabulce! 0 searches stačilo.

CHYBA 2: Snippet nepotvrzuje
javelina → Pecari tajacu → pakůň límcový [biolib.cz]
  ^^^ CHYBA: Žádný snippet to nepotvrzuje!

CHYBA 3: Vymyšlený název
Joshua tree → Yucca brevifolia → jošuovník [vlastní výmysl]
  ^^^ CHYBA: Pseudo-český název odvozený z angličtiny!
```

---

## KOMPAKTNÍ VÝSTUP (během práce)

```
DB ✓ pronghorn → vidloroh americký (SpeciesDB, kontext OK) [0s]
DB ✓ javelina → pakůň límcový (TermDB, kontext OK) [0s]
WS ✓ spotted salamander → mlok skvrnitý (wiki) [1s]
✗ zebrafish → NEOVĚŘENO (snippet neobsahuje český název)

[1/20 searches | 3 DB-resolved | 1 web-verified | 1 unverified]
```

---

## STOP TRIGGERY

| Situace | Akce |
|---------|------|
| Termín nalezen v pre-resolved tabulce, kontext sedí | PŘIJMOUT → další termín (0 searches) |
| Snippet obsahuje český název | STOP → další termín |
| 2 searches bez výsledku pro 1 termín | STOP → NEOVĚŘENO |
| 20 searches celkem | STOP → zbytek jako NEOVĚŘENO |
| Dva termíny → stejný CZ název | ZASTAVIT WORKFLOW → hlásit chybu |

---

## SELF-CHECK (povinný)

Před označením termínu jako ✓:
```
□ Je termín v pre-resolved tabulce? → Kontext sedí? → Hotovo (0 searches)
□ Mám WebSearch snippet/DB záznam s českým názvem?
□ Latinský název ve snippetu/DB = latinský název, který používám?
□ Nepřiřazuji stejný CZ název dvěma různým EN termínům?
□ Český název POCHÁZÍ ze snippetu nebo DB? (ne z mé hlavy!)
□ Nepřidal jsem k ověřenému názvu vlastní „alternativu"?
```

---

*v4.2 — DB-first přístup: SpeciesDB (218K) + TermDB + ledger → web search jen pro nerozpoznané*
