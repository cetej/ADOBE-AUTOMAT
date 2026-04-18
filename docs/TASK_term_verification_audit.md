# TASK — Audit terminologické kontroly

**Kontext:** V projektu NG-ROBOT (2026-04-17) selhala kontrola biologických druhů — Phase 1 (Sonnet) halucinoval české názvy (např. "lesňáček cerulea" místo "lesňáček modropláštíkový") a Phase 3 tyto halucinace neopravil, přestože BIOLIB termdb.db (246k termínů) správné názvy obsahuje.

**Root cause byl systémový:** pre_resolve_species() byl volán až ve Phase 3, ale nový Python-first verifier (V2) parametr ignoroval jako DEPRECATED. Databáze se tak de facto pro biologické druhy v překladu vůbec nepoužívala.

**ADOBE-AUTOMAT je v riziku stejného patternu**, protože:
- `backend/services/translation_service.py` používá **stejnou** `MULTI_DOMAIN_DB_PATH` (termdb.db)
- Má Translation Memory JSON cache (`TRANSLATION_MEMORY_PATH`) — paralela ke `global_ledger.json` v NG-ROBOT, který se naplnil smetím ("žádné opravy" atd.)
- `get_protected_terms_cached()` existuje — ale audit musí ověřit, zda se **skutečně používá** v překladovém flow a zda je **živý DB lookup**, ne snapshot

---

## Cíl auditu

Ověřit, že pro každý odborný termín v IDML/PDF dokumentu:
1. **Je předem vyhledán v termdb.db** (BIOLIB, 246k termínů) a kanonický český název je **vynucen** v překladu — ne doporučen.
2. **Translation Memory neobsahuje halucinace** z historických běhů (smetí typu "chemický vzorec → mobile phone").
3. **LLM nemůže přepsat kanonický název vlastním překladem**, pokud pro daný termín existuje DB záznam.

---

## Konkrétní kontrolní body

### 1. Používá se termdb.db skutečně v překladu, nebo jen deklaratoricky?

**Soubor:** `backend/services/translation_service.py`

```bash
# Najdi, kde se _main_db.lookup() reálně volá v překladovém flow
grep -n "_main_db.lookup\|_main_db\." backend/services/translation_service.py
grep -rn "lookup_canonical\|termdb.*lookup" backend/
```

**Co hledat:**
- ❌ `_main_db` je importovaný, ale nikde se nevolá `.lookup()` → DB je mrtvá deklarace
- ❌ Volání existuje, ale výsledek se jen přidá do kontextu promptu **jako doporučení**, ne jako tvrdá substituce po LLM překladu
- ✅ Existuje deterministický post-step, který po LLM překladu vezme `{en: X, lat: Y}` → `db.lookup(Y)` → `str.replace(nesprávný_cz, kanonický_cz)` v IDML/PDF výstupu

**Reference z NG-ROBOT:** `claude_processor/glossary_enforcer.py` — Phase 1.5 Python-first enforcer, live DB lookup, str.replace. Žádný LLM, žádný JSON snapshot.

### 2. Chrání `get_protected_terms_cached()` skutečně?

**Hledej:**
```bash
grep -rn "get_protected_terms_cached\|_protected_terms" backend/
```

**Co ověřit:**
- Kde se množina volá — v translatoru, v korektoru, v obou?
- Je to **tvrdá whitelist** (termín v tomto seznamu NESMÍ být přeložen ani opraven) nebo jen soft hint?
- Jak velká je množina? 200/doména × kolik domén? Je to opravdu reprezentativní pro typický ADOBE dokument?
- Kolik termínů z konkrétního IDML projde přes seznam vs. mimo? Log počet hits/misses.

### 3. Translation Memory — je čistá nebo obsahuje halucinace?

```bash
python -c "
import json
from pathlib import Path
tm = json.loads(Path('backend/data/translation_memory.json').read_text(encoding='utf-8'))
print(f'TM velikost: {len(tm)} záznamů')
# Podezřelé vzorce:
import re
suspect = {k: v for k, v in tm.items() if
    len(k) < 4 or len(v) < 4 or                    # příliš krátké
    k == v or                                        # en=cs shoda
    re.search(r'^(žádné|ano|ne|hotovo)', v.lower()) # instrukce místo překladu
}
print(f'Podezřelé záznamy: {len(suspect)}')
for k, v in list(suspect.items())[:20]:
    print(f'  {k!r} → {v!r}')
"
```

**Reference z NG-ROBOT:** `claude_processor/unverified_terms.json` obsahoval záznamy jako `"žádné opravy"` — LLM tam vrátil český text instrukce místo skutečného překladu a systém to uložil jako "ověřený termín". Audit musí odhalit podobné.

### 4. URL korupce uvnitř anchorů — relevantní pro IDML s hyperlinky?

**Test:** vezmi jakýkoli zpracovaný IDML a najdi odkazy.

```bash
python -c "
import re, xml.etree.ElementTree as ET
# Z výstupního IDML extrahuj hyperlinks
# Pro každý: zkontroluj, že neobsahuje české znaky nebo českoslova (asi, spojený...)
"
```

**Reference z NG-ROBOT:** `claude_processor/url_restorer.py` — detekuje překlad UVNITŘ URL anchoru (např. "about" → "asi" způsobí 404 CDC linku). Pokud ADOBE překládá dokumenty s URL, stejný bug tu bude.

### 5. Je Phase 0.5 "pre-resolution" aplikovaná PŘED překladem?

V NG-ROBOT byla špatně zapojená — volání existovalo, ale Phase 3 V2 parametr ignoroval (`DEPRECATED`). Výsledek pre-resolution se zahodil.

**V ADOBE-AUTOMAT hledej:**
- Je někde krok typu "vytáhni všechny termíny z dokumentu → DB lookup → vytvoř glossary → injektuj do promptu"?
- Nebo překlad jede "naslepo" a cáska až po-hoc?

Pre-resolution musí běžet **před** LLM voláním a glossary **musí být v system promptu** s tvrdou direktivou:

> "Pro termíny z tabulky níže POUŽIJ POUZE tento český ekvivalent. ZAKÁZÁNO překládat vlastními slovy."

---

## Checklist pro auditora

- [ ] Spustit grep/audit podle bodů 1–5 výše
- [ ] Na 3 reálných IDML/PDF dokumentech: vytáhnout všechny odborné termíny ze vstupu → spustit `_main_db.lookup()` → porovnat s výstupem překladu. Kolik je halucinací?
- [ ] Vyčistit Translation Memory od smetí (dry run, pak schválit)
- [ ] Pokud chybí enforcer: port `glossary_enforcer.py` z NG-ROBOT (odkaz: `C:\Users\stock\Documents\000_NGM\NG-ROBOT\claude_processor\glossary_enforcer.py`)
- [ ] Pokud IDML obsahuje URL: port `url_restorer.py` z NG-ROBOT
- [ ] Zapsat nálezy do `docs/LEARNINGS.md`

---

## Referenční implementace v NG-ROBOT

| Problém | Řešení | Soubor |
|---|---|---|
| LLM halucinace odborných termínů | Phase 1.5 glossary enforcer (live DB lookup) | `claude_processor/glossary_enforcer.py` |
| Překlad uvnitř URL | Phase 1.4 URL restorer (fuzzy match proti originálu) | `claude_processor/url_restorer.py` |
| Phase 1 prompt direktiva | Vynuť Latin binomen po prvním zmínění druhu | `projects/1-PREKLAD-FORMAT/00_MASTER_v42.2.6.md` |
| Deprecated parametr ignoruje DB | Fix: Phase 3 V2 `verify_unmatched_via_llm` vrací tuple, tokens akumulované | `claude_processor/term_verifier.py` |

**Commit s implementací:** `2c33998..a6858b4` v https://github.com/cetej/NG-ROBOT

---

## Kdy audit spustit

- Nyní (preventivně — NG-ROBOT odhalil systémový pattern)
- Po každém větším overhaul překladového flow
- Když uživatel nahlásí "ten překlad zní divně" u odborných pojmů

## Odhad práce

- Audit bodů 1–5: 2–4 hodiny
- Port `glossary_enforcer.py` (pokud chybí): 1 den
- Port `url_restorer.py` (pokud relevantní): 4 hodiny
- E2E test na 3 reálných dokumentech: 2–3 hodiny
