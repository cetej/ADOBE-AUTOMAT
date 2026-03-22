# EXAMPLES - Příklady nálezů a oprav

**Verze:** 1.0  
**Účel:** Konkrétní příklady kontextuálních chyb a jejich oprav z reálné praxe

---

## 📚 PŘÍKLAD 1: TEMPORÁLNÍ KONTEXT (KRITICKÁ CHYBA)

### Kontext
Článek o paleoantropologickém nálezu z Maroka, fosilie datované na 773 000 let.

### Originál (EN)
> "This ancient human may be at the root of the Homo sapiens family tree"

### Překlad (chybný)
> "Tento **starověký** člověk může být kořenem rodokmenu Homo sapiens"

### Problém
- „Starověk" v češtině označuje období cca 3500 př.n.l. – 476 n.l.
- Fosilie staré 773 000 let patří do **pravěku/prehistorie**
- Chyba činí titulek fakticky nesmyslným pro znalého čtenáře

### Oprava
> "Tento **pravěký** člověk může být kořenem rodokmenu Homo sapiens"

### Kategorie
🔴 KRITICKÁ – mění faktický význam

### Kontrola, která to měla zachytit
- Temporální kontext (TEMPORAL_TERMINOLOGY.md)
- Translation trap: ancient ≠ automaticky „starověký"

---

## 📚 PŘÍKLAD 2: FALSE FRIEND (DŮLEŽITÁ CHYBA)

### Originál (EN)
> "The results were actually quite surprising."

### Překlad (chybný)
> "Výsledky byly **aktuálně** docela překvapivé."

### Problém
- „Actually" ≠ „aktuálně"
- „Actually" = „vlastně, ve skutečnosti"
- „Aktuálně" = „v současnosti, nyní"

### Oprava
> "Výsledky byly **vlastně** docela překvapivé."

### Kategorie
🟡 DŮLEŽITÁ – mění význam věty

### Kontrola
- Translation trap: actually ≠ aktuálně (TRANSLATION_TRAPS.md)

---

## 📚 PŘÍKLAD 3: IDIOM (DŮLEŽITÁ CHYBA)

### Originál (EN)
> "The discovery was just the tip of the iceberg."

### Překlad (chybný)
> "Objev byl jen **špičkou ledové hory**."

### Problém
- Doslovný překlad idiomu
- Čeština používá „špička ledovce", ne „ledové hory"

### Oprava
> "Objev byl jen **špičkou ledovce**."

### Kategorie
🟢 DROBNÁ – zní nepřirozeně, ale význam zachován

### Kontrola
- Idiomy (IDIOMS_DATABASE.md)

---

## 📚 PŘÍKLAD 4: KOLOKACE (DŮLEŽITÁ CHYBA)

### Originál (EN)
> "Scientists conducted extensive research and made several important discoveries."

### Překlad (chybný)
> "Vědci **vedli** rozsáhlý výzkum a **udělali** několik důležitých objevů."

### Problém
- „conduct research" → „provádět výzkum", ne „vést výzkum"
- „make a discovery" → „učinit objev", ne „udělat objev"

### Oprava
> "Vědci **prováděli** rozsáhlý výzkum a **učinili** několik důležitých objevů."

### Kategorie
🟡 DŮLEŽITÁ – zní nepřirozeně, narušuje plynulost

### Kontrola
- Kolokace (COLLOCATIONS_GUIDE.md)

---

## 📚 PŘÍKLAD 5: MĚRNÉ JEDNOTKY (KRITICKÁ CHYBA)

### Originál (EN)
> "The temperature reached 104°F, making it the hottest day on record."

### Překlad (chybný)
> "Teplota dosáhla **104 °F**, což z něj dělá nejteplejší den v historii měření."

### Problém
- Český čtenář nerozumí Fahrenheitům
- Chybí přepočet na Celsia

### Oprava
> "Teplota dosáhla **40 °C** (104 °F), což z něj dělá nejteplejší den v historii měření."

### Kategorie
🔴 KRITICKÁ – čtenář nerozumí informaci

### Kontrola
- Měrné jednotky (TRANSLATION_TRAPS.md, sekce D)

---

## 📚 PŘÍKLAD 6: KULTURNÍ REFERENCE (DŮLEŽITÁ CHYBA)

### Originál (EN)
> "It's like comparing apples and oranges."

### Překlad (chybný)
> "Je to jako **srovnávat jablka a pomeranče**."

### Problém
- Anglický idiom, v češtině neexistuje
- Čeština má jiné ekvivalenty

### Oprava
> "Je to jako **srovnávat hrušky s jablky**." / "To se nedá srovnávat."

### Kategorie
🟡 DŮLEŽITÁ – zní cize

### Kontrola
- Idiomy (IDIOMS_DATABASE.md)
- Kulturní reference

---

## 📚 PŘÍKLAD 7: VĚDECKÁ TERMINOLOGIE V KONTEXTU

### Originál (EN)
> "The control group showed no significant changes."

### Překlad (chybný)
> "**Kontrolní** skupina nevykazovala žádné významné změny."

### Problém
- „Control group" v experimentu = srovnávací skupina
- „Kontrolní skupina" evokuje spíše „skupina provádějící kontrolu"

### Oprava
> "**Srovnávací** skupina nevykazovala žádné významné změny."

### Kategorie
🟡 DŮLEŽITÁ – odborná terminologie

### Kontrola
- Translation traps: control group (TRANSLATION_TRAPS.md)

---

## 📚 PŘÍKLAD 8: LOGICKÁ KONZISTENCE

### Originál (EN)
> "The 200-million-year-old dinosaur fossils predate the ancient Egyptian pyramids by millennia."

### Překlad (chybný)
> "200 milionů let staré dinosauří fosílie předcházejí starověké egyptské pyramidy o tisíciletí."

### Problém
- 200 milionů let vs. 4 500 let (pyramidy)
- „O tisíciletí" je směšně nepřesné – správně „o stovky milionů let"
- Srovnání je absurdní a v překladu mělo být opraveno/okomentováno

### Oprava
> "200 milionů let staré dinosauří fosílie jsou o **stovky milionů let starší** než egyptské pyramidy."

NEBO komentář: [Poznámka: Srovnání v originále je nepřesné]

### Kategorie
🔴 KRITICKÁ – logický nesmysl

### Kontrola
- Logická konzistence
- Temporální kontext

---

## 📚 PŘÍKLAD 9: REGISTR A STYL

### Originál (EN)
> "The CEO stated that profits were 'awesome' this quarter."

### Překlad (chybný)
> "Generální ředitel prohlásil, že zisky byly tento kvartál '**awesome**'."

### Problém
- Anglicismus ponechán v textu
- Neformální „awesome" ve formálním kontextu

### Oprava
> "Generální ředitel prohlásil, že zisky byly tento kvartál '**skvělé**'."

### Kategorie
🟡 DŮLEŽITÁ – stylistická nekonzistence

### Kontrola
- Registr a styl

---

## 📚 PŘÍKLAD 10: PARTIAL EQUIVALENT

### Originál (EN)
> "This represents a critical period in human evolution."

### Překlad (chybný)
> "Toto představuje **kritické** období lidské evoluce."

### Problém
- „Critical" zde neznamená „kritický" (nebezpečný, vážný)
- Znamená „klíčový, rozhodující, zlomový"

### Oprava
> "Toto představuje **klíčové/rozhodující** období lidské evoluce."

### Kategorie
🟡 DŮLEŽITÁ – významový posun

### Kontrola
- Partial equivalents: critical (TRANSLATION_TRAPS.md)

---

## 📊 STATISTIKA PODLE KATEGORIÍ

| Kategorie | Kritické | Důležité | Drobné |
|-----------|----------|----------|--------|
| Temporální kontext | 2 | 0 | 0 |
| False friends | 0 | 2 | 0 |
| Idiomy | 0 | 1 | 1 |
| Kolokace | 0 | 1 | 0 |
| Měrné jednotky | 1 | 0 | 0 |
| Logická konzistence | 1 | 0 | 0 |
| Registr | 0 | 1 | 0 |
| Srozumitelnost terminologie | 0 | 1 | 0 |
| Transliterace | 1 | 0 | 0 |
| **CELKEM** | **5** | **6** | **1** |

---

## 📚 PŘÍKLAD 11: SROZUMITELNOST TERMINOLOGIE

### Kontext
Článek o paleoantropologickém nálezu pro čtenáře National Geographic.

### Originál (EN)
> "What immediately struck me was the unexpected gracility of the adult mandible."

### Překlad (chybný)
> "Co mě okamžitě zaujalo, byla nečekaná **graciálnost** dospělé čelisti."

### Problém
- „Graciálnost" je odborný anatomický termín (z lat. gracilis = štíhlý)
- Běžný čtenář NG tento termín nezná
- Může ho zaměnit s „grácií" (půvab) → špatná interpretace

### Oprava
> "Co mě okamžitě zaujalo, byla nečekaná **jemnost a štíhlost** dospělé čelisti."

### Kategorie
🟡 DŮLEŽITÁ – narušuje srozumitelnost

### Kontrola
- Srozumitelnost odborné terminologie (TERMINOLOGY_ACCESSIBILITY.md)

---

## 📚 PŘÍKLAD 12: TRANSLITERACE (ě → e, NE i!)

### Kontext
Tvorba URL slug pro článek o pravěkém nálezu.

### Originál
> Titulek: „Tento pravěký člověk může být kořenem rodokmenu"

### Zpracování (chybné)
> URL slug: `prav**i**ki-clovek-koren-rodokmenu`

### Problém
- `ě` se transliteruje na `e`, NE na `i`
- Chyba vzniká záměnou grafému (písmo) a fonému (výslovnost)
- `ě` = varianta `e`, NE `i`

### Oprava
> URL slug: `prav**e**ky-clovek-koren-rodokmenu`

### Kategorie
🔴 KRITICKÁ – chybný URL slug

### Kontrola
- Transliterace (TRANSLITERATION_RULES.md)

---

## 📝 POUČENÍ Z PŘÍKLADŮ

### Nejčastější zdroje chyb:
1. **Automatický překlad** bez kontroly kontextu
2. **Neznalost českých ekvivalentů** idiomů a kolokací
3. **Ignorování odborné terminologie** v kontextu
4. **Nepřepočítávání měrných jednotek**
5. **Nedostatečná kontrola logiky** celého textu

### Co tyto chyby spojuje:
- Jsou **gramaticky správné**
- Projdou **spell-checkerem**
- Nepůsobí jako „chyby" při rychlém čtení
- Odhalí je až **kontextuální analýza**

---

**Verze:** 1.0  
**Poslední aktualizace:** 08.01.2026
