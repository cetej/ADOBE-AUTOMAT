# Research Prompt — TermVerifier Call 1

TVÝM ÚKOLEM JE IDENTIFIKOVAT A OVĚŘIT ODBORNÉ TERMÍNY V ČLÁNKU.

{ledger_block}ČLÁNEK K ANALÝZE:
{translated_content}

---

## POVINNÝ PROTOKOL OVĚŘOVÁNÍ (máš k dispozici web_search a web_fetch!)

Máš nástroje web_search a web_fetch. NIKDY nepoužívej znalosti z paměti pro odborné termíny.

### KROK 0: TRIAGE — roztřiď termíny PŘED hledáním

Projdi článek a sesbírej VŠECHNY odborné termíny. Roztřiď na:

**ALREADY RESOLVED (žádný web search!):**
- Druhy v tabulce "PŘEDBĚŽNĚ OVĚŘENÉ DRUHY" — SpeciesDB (218K+ druhů z BioLib/Wikidata)
- Termíny v tabulce "TermDB" nebo "global ledger" kde kontext sedí
→ Pouze zkontroluj, zda CZ název sedí v kontextu věty. Pokud sedí, PŘESKOČ.

**HIGH RISK (ověř web searchem):**
- Biologické druhy které NEJSOU v pre-resolved tabulce
- Méně známé geografické lokality (ne hlavní města, ne státy)
- Odborné termíny z medicíny, geologie, fyziky kde překlad nemusí být zřejmý
- Termíny kde existují podobné české alternativy (false friends)

**LOW RISK (PŘESKOČ — neověřuj web searchem):**
- Obecně známá zvířata (lev, orel, slon, delfín...) — pokud nejde o specifický druh
- Hlavní města, státy, kontinenty, oceány
- Běžné geografické pojmy (pohoří, řeka, ostrov)
- Obecné pojmy které čtenář NG zná (fotosyntéza, evoluce, klimatická změna)

⚠️ PRAVIDLO: ALREADY RESOLVED = 0 searches. HIGH RISK = max 2 searches/termín. LOW RISK = 0 searches.
Cíl: max {TERM_SEARCH_MAX_USES} searches celkem. Většina druhů by měla být v pre-resolved tabulce!

### Postup pro HIGH RISK biologické druhy (POUZE ty co NEJSOU v pre-resolved tabulce):
1. web_search("{anglický název} český název site:cs.wikipedia.org OR site:biolib.cz") — jeden search, oba zdroje
2. Pokud Wikipedia a BioLib se liší → preferuj Wikipedia/NG.cz (žurnalistický standard)
3. Jen při úplné nejasnosti: web_fetch na biolib.cz stránku (spotřebuje web_fetch limit!)

### TAXONOMIE vs. ŽURNALISTIKA
BioLib.cz = systematické názvy. Wikipedia/NG.cz = žurnalistické názvy. Při rozporu PREFERUJ Wikipedia/NG.cz. Detaily a příklady viz PROJECT_INSTRUCTIONS.

### Postup pro ostatní HIGH RISK termíny:
1. web_search("{termín} site:cs.wikipedia.org") — zkopíruj přesnou formulaci ze snippetu
(LOW RISK termíny NEZAPISUJ do tabulky oprav)

### KONTROLNÍ BODY (před každým ✓):
- Dva různé EN termíny → stejný CZ název = CHYBA, ověř znovu
- Žádný snippet = NEOVĚŘENO (NEVYMÝŠLEJ vlastní název!)
- Snippet říká jiný název → OPRAV na snippet
- Kontroluj: CZ název pochází ze snippetu/DB, ne z paměti?
- Kontroluj: LAT ve snippetu = LAT v článku?
- STOP TRIGGER: 2 neúspěšné hledání pro 1 termín → NEOVĚŘENO

---

⚠️ VÝSTUP: POUZE TABULKA OPRAV — NE CELÝ ČLÁNEK!

Vrať POUZE sekci "## TERMINOLOGICKÉ OPRAVY" v tomto formátu:

## TERMINOLOGICKÉ OPRAVY

| # | EN původní | LAT | CZ v článku | CZ správně | Snippet (důkaz) | URL | Poznámka |
|---|---|---|---|---|---|---|---|
| 1 | spotted salamander | Ambystoma maculatum | mlok skvrnitý | mlok skvrnitý | "mlok skvrnitý (Ambystoma maculatum)" | cs.wikipedia.org/... | biolib říká "axolotl skvrnitý" — systematický název rodu, v žurnalistice nepoužívaný |
| 2 | pronghorn | Antilocapra americana | vidlorožec | vidloroh americký | "Vidloroh americký (Antilocapra americana)" | biolib.cz/... | |

## NEOVĚŘENÉ TERMÍNY

| # | EN | Důvod |
|---|---|---|
| 1 | Sierran treefrog | Žádný český název v biolib/wiki — deskriptivní překlad "stromová žába sierranská" ponechán |

## TRIAGE REPORT
- HIGH RISK termínů (ověřováno): X
- LOW RISK termínů (přeskočeno): Y
- Důvody přeskočení: obecně známý/v global ledger/běžná geografie

## STATISTIKY
- Celkem termínů: X
- Ověřeno (HIGH RISK): Y
- Opraveno: Z
- Neověřeno: W
- Web searches použito: N/{TERM_SEARCH_MAX_USES}

DŮLEŽITÉ: NEREPRODUKUJ celý článek. Vrať JEN tabulky výše.
