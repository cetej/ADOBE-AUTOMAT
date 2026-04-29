"""AI preklad pomoci Claude API + Translation Memory.

Podporuje:
- Batch preklad (vice elementu najednou pro efektivitu)
- Translation memory (cache prekladu pro konzistenci a uspora tokenu)
- Kontextovy preklad (kategorie, paragraph style informuji prompt)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import logging
import os
import re
from pathlib import Path

from config import (
    TRANSLATION_MEMORY_PATH, MULTI_DOMAIN_DB_PATH,
    TRANSLATION_MODEL, TRANSLATION_MAX_TOKENS,
)
from models import TextElement

logger = logging.getLogger(__name__)

# Terminologická databáze (ngm-terminology v2.0 — 244K+ ověřených překladů)
try:
    from ngm_terminology import NormalizedTermDB
    _main_db = NormalizedTermDB(MULTI_DOMAIN_DB_PATH) if Path(MULTI_DOMAIN_DB_PATH).exists() else None
    if _main_db:
        logger.info("TermDB: načtena referenční DB (%s)", MULTI_DOMAIN_DB_PATH)
except (ImportError, Exception) as e:
    _main_db = None
    logger.info("TermDB: nedostupná (%s)", e)

# === Protected terms cache (TermDB → CzechCorrector) ===

_protected_terms: set[str] | None = None


def get_protected_terms_cached() -> set[str]:
    """Vrátí chráněné termíny z TermDB (lazy load, cached).

    Používá se v CzechCorrector pro ochranu odborných termínů před
    falešnými korekcemi. Cache pro celý lifetime procesu.
    """
    global _protected_terms
    if _protected_terms is not None:
        return _protected_terms
    if not _main_db:
        _protected_terms = set()
        return _protected_terms
    try:
        from ngm_terminology.corrector import get_protected_terms
        _protected_terms = get_protected_terms(_main_db, max_per_domain=200)
        logger.info("Protected terms: %d termínů načteno z TermDB", len(_protected_terms))
    except Exception as e:
        logger.warning("Protected terms: chyba načítání (%s) — pokračuji bez ochrany", e)
        _protected_terms = set()
    return _protected_terms


# === Translation Memory ===

def load_translation_memory() -> dict[str, str]:
    """Nacte translation memory z JSON souboru."""
    if TRANSLATION_MEMORY_PATH.exists():
        try:
            return json.loads(TRANSLATION_MEMORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Chyba pri cteni translation memory, zacinam s prazdnou")
    return {}


def save_translation_memory(memory: dict[str, str]) -> None:
    """Ulozi translation memory do JSON souboru."""
    TRANSLATION_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATION_MEMORY_PATH.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_translation_memory(elements: list[TextElement]) -> int:
    """Aktualizuje TM z potvrzenych prekladu (status=OK)."""
    memory = load_translation_memory()
    added = 0
    for el in elements:
        if el.czech and el.status == "OK" and el.contents:
            key = el.contents.strip().lower()
            if key and key not in memory:
                memory[key] = el.czech
                added += 1
    if added:
        save_translation_memory(memory)
        logger.info("Translation memory aktualizovana: +%d zaznamu (celkem %d)", added, len(memory))
    return added


def write_back_to_termdb(elements: list[TextElement]) -> int:
    """Zapíše schválené překlady (status=OK) zpět do termdb.db (246K+).

    Slouží jako zpětná vazba z ADOBE-AUTOMAT do sdílené terminologické DB.
    Zapisuje přímo do NormalizedTermDB (termdb.db) — jediný zdroj pravdy.
    """
    if not _main_db:
        return 0

    added = 0
    skipped_conflict = 0
    for el in elements:
        if el.czech and el.status == "OK" and el.contents:
            en = el.contents.strip()
            cz = el.czech.strip()
            if en and cz and len(en) >= 2 and en.lower() != cz.lower():
                # Write-protection: pokud DB už kanonický CZ má a liší se,
                # nezapisuj — chráníme sdílenou DB před kontaminací halucinacemi
                try:
                    existing = _main_db.batch_translate([en], from_lang="en", to_lang="cs")
                    if existing and en in existing:
                        canon = existing[en]
                        if canon.lower().strip() != cz.lower().strip():
                            logger.info("TermDB write-back SKIP (konflikt): %r → db=%r, ours=%r",
                                        en, canon, cz)
                            skipped_conflict += 1
                            continue
                except Exception:
                    pass  # pokud lookup selže, pokračuj do add_term (zachovej původní chování)

                domain = _category_to_domain(el.category)
                try:
                    is_new = _main_db.add_term(
                        canonical_name=en, domain=domain,
                        en=en, cz=cz,
                        source="adobe-automat"
                    )
                    if is_new:
                        added += 1
                except Exception as e:
                    logger.warning("TermDB write-back chyba: %s — %s", en, e)

    if skipped_conflict:
        logger.info("TermDB write-back: %d termínů přeskočeno (konflikt s kanonem)",
                    skipped_conflict)

    if added:
        logger.info("TermDB write-back: +%d novych terminu z ADOBE-AUTOMAT", added)
    return added


def _category_to_domain(category: str) -> str:
    """Mapuje ADOBE-AUTOMAT TextCategory na termdb doménu."""
    if not category:
        return "general"
    cat = category.upper()
    geo_cats = {"OCEANS_SEAS", "CONTINENTS", "COUNTRIES_FULL", "COUNTRIES_ABBREV",
                "REGIONS", "CITIES", "WATER_BODIES", "LANDFORMS", "PLACES", "SETTLEMENTS"}
    if cat in geo_cats:
        return "geography"
    if cat in {"PERIODS", "EVENTS", "DATES", "TIMELINE"}:
        return "history"
    return "general"


# === Claude API preklad ===

SYSTEM_PROMPT = """Jsi profesionální překladatel pro National Geographic Česko.
Překládáš krátké anglické texty z tiskových podkladů (IDML soubory časopisu, mapové popisky).
Elementy jsou KRÁTKÉ — typicky 1–15 slov: popisky map, nadpisy, legendy, datace, zkratky.

## TERMINOLOGICKÝ GLOSÁŘ (pokud je přiložen níže)
- Termíny v tabulce glosáře jsou OVĚŘENÉ z referenční databáze (246K+ termínů, BIOLIB, geografická data).
- Pokud EN text odpovídá některému řádku glosáře: POUŽIJ POUZE uvedený český ekvivalent.
- ZAKÁZÁNO překládat tyto termíny vlastními slovy, synonymem nebo parafrází.
- Pokud glosář uvádí jiný překlad než se zdá logický: NÁSLEDUJ glosář, ne svůj odhad.

## ZEMĚPISNÉ NÁZVY — TVRDÁ PRAVIDLA

### Pravidlo 1: Generický prvek se VŽDY překládá
Tabulka generik (povinné překlady, NIKDY neponecháváš v angličtině):
| EN | CZ |
|---|---|
| Lake | jezero |
| Arm / Sound / Bay / Inlet / Cove | záliv (zátoka u malých) |
| Mountains / Range | pohoří |
| Mount / Mt. | hora |
| River / R. | řeka |
| Creek / Stream / Brook | potok |
| Highway / Hwy | dálnice (interstate) |
| Road / Rd. / Street / St. | silnice |
| Passage / Strait | průliv |
| Channel | průliv (mořský) / kanál (umělý) |
| Canal | průplav |
| Glacier | ledovec |
| Pass | sedlo / průsmyk |
| Ocean | oceán |
| Sea | moře |
| Cape | mys |
| Peninsula | poloostrov |
| Island / Isle | ostrov |
| Falls | vodopád / vodopády |
| Valley | údolí |
| Plateau | plošina |
| National Park | národní park |

### Pravidlo 2: Vlastní jméno se NEPŘEKLÁDÁ
Slova jako Index, Barry, Knik, Glenn, Glacier (jako vlastní jméno), Chugach, Prince William zůstávají v originále. Diakritiku zachovej u zavedených tvarů (Reykjavík, Brattahlíð).

### Pravidlo 3: Pořadí — generikum PŘED vlastním jménem
EN: `[Vlastní] [generikum]` → CZ: `[generikum] [Vlastní]`

Závazné příklady:
- Index Lake → jezero Index
- Barry Arm → záliv Barry (NIKDY ne „Barry Arm" v české mapě)
- Knik Arm → záliv Knik
- Turnagain Arm → záliv Turnagain
- Prince William Sound → záliv Prince William
- Chugach Mountains → pohoří Chugach
- Esther Passage → průliv Esther
- Passage Canal → průplav Passage
- Glenn Highway → dálnice Glenn (NIKDY ne „Glenn Highway")
- Seward Highway → dálnice Seward
- Pacific Ocean → Tichý oceán (zavedené exonymum)
- Arctic Ocean → Severní ledový oceán

### Pravidlo 4: Skloňování s předložkou
S českou předložkou se skloňuje POUZE generikum, vlastní jméno zůstává v 1. pádě.
- „to Prince William Sound" → „k zálivu Prince William" (NE „Ke Prince William Sound")
- „from Knik Arm" → „ze zálivu Knik"
- „across Glenn Highway" → „přes dálnici Glenn"

### Pravidlo 5: Sídla — výjimka, NEPŘEKLÁDAJÍ se
Sídla (města, vesnice, kempy, body zájmu jako proper noun) zůstávají v originále:
- Glacier View → Glacier View
- Victory Bible Camp → Victory Bible Camp
- Anchorage → Anchorage
- New York → New York

Výjimka: zavedená historická exonyma (London → Londýn, Vienna → Vídeň, Moscow → Moskva, Prague → Praha)

### Pravidlo 6: Konzistence v rámci dokumentu
Pokud se stejný název objeví víckrát (např. „Barry Arm" v několika vrstvách mapy), MUSÍŠ použít stejný překlad pokaždé. Žádné výjimky.

## ZKRATKY STÁTŮ
- U.K.→VB, GER.→NĚM., SPA.→ŠPA., GRE.→ŘEC., SWI.→ŠVÝ., AUT.→RAK.

## DATACE A ČÍSLA
- A.D. 700 → 700 n. l. | 700 BC → 700 př. n. l. | ca./c. → cca
- 1st century → 1. století | 10th–15th centuries → 10.–15. století
- Tisíce s mezerou: 1 000 000 (ne 1,000,000)
- Desetinná čárka: 3,14 (ne 3.14)

## TYPOGRAFIE
- České uvozovky: „text" (ne "text")
- Pomlčka v rozsazích: 1990–2000 (ne 1990-2000)
- Interpunkční pomlčka: VŽDY en-dash (–), NIKDY em-dash (—). Čeština používá – s mezerami: „text – pokračování"
- Procenta: 50 % (mezera před %)
- Jednotky: 5 km, 3 °C (mezera před jednotkou)
- Nedělitelná mezera za jednopísmennými předložkami: k, s, v, z, o, u

## FALSE FRIENDS A IDIOMY
| EN | Špatně (doslovně) | Správně (idiomaticky) |
|---|---|---|
| billion | bilion | miliarda |
| evidence | evidence | důkazy, doklady |
| actual/actually | aktuální/aktuálně | skutečný/ve skutečnosti |
| eventually | eventuálně | nakonec |
| dramatic (change) | dramatický | výrazný, zásadní |
| **of interest** | **zájmu / zájmový** | **sledovaný / kritický / vyznačený** |
| of concern | zájmu/obavy | znepokojující / sledovaný |
| of note | poznámky | významný / pozoruhodný |
| in question | v otázce | dotyčný / sledovaný |
| at hand | po ruce | aktuální / dotyčný |

POZOR na `landslide of interest`: NE „sesuv zájmu"; ANO „sledovaný sesuv".

## ODBORNÉ TERMÍNY — geologie a přírodní rizika
Tato doména v TermDB chybí, dodržuj následující kanonické překlady:

| EN | CZ |
|---|---|
| **deep-seated landslide** | **hlubinný sesuv** (preferováno) / hluboko založený sesuv |
| shallow landslide | mělký sesuv |
| active landslide | aktivní sesuv |
| earlier / former landslide | starší sesuv |
| **landslide of interest** | **sledovaný / zkoumaný sesuv** (NE „sesuv zájmu") |
| rock fall / rockfall | skalní řícení |
| debris flow | proudový sesuv / mura |
| tsunami arrival time | čas příchodu tsunami |
| permafrost (thawing/active) | (tající/aktivní) permafrost |
| glacier retreat | ústup ledovce |
| ice-marginal | okraj ledovce / okrajový (k ledovci) |
| moraine | moréna |
| bedrock | skalní podloží |

**Příklad celé fráze:** `Deep-seated landslide of interest` → `Zkoumaný hlubinný sesuv` (nebo `Sledovaný hlubinný sesuv`).

## STYL
- **Hlavní cíl: český čtenář musí rozumět.** Doslovný překlad bez pochopení kontextu = chyba, i když je gramaticky správný.
- Přirozená čeština, ne doslovný překlad.
- Zachovej zkratky a odbornou terminologii (geologie, biologie, geografie).
- Diakritika vždy správně.

## KAPITALIZACE — ZÁVISÍ NA TYPU TEXTU
České typografické pravidlo se v anglických mapových popiscích NEPOUŽÍVÁ (angličtina dává Title Case na popisky, čeština ne). Důsledně rozliš:

### Popisek (ne věta, ne titulek) — malé počáteční písmeno
Popisek = krátká fráze na mapě, bez tečky, není to věta ani název objektu jako celek.
Velká písmena POUZE u vlastních jmen.

| EN (Title Case) | CZ správně | CZ špatně |
|---|---|---|
| Direction of View | směr pohledu | ~~Směr pohledu~~ |
| Active landslides | aktivní sesuvy | ~~Aktivní sesuvy~~ |
| Deep-seated landslide | hlubinný sesuv | ~~Hlubinný sesuv~~ |
| Earlier landslide | starší sesuv | ~~Starší sesuv~~ |
| Thawing permafrost | tající permafrost | ~~Tající permafrost~~ |
| Other landslide with tsunami potential | jiný sesuv s potenciálem tsunami | ~~Jiný sesuv...~~ |
| Passenger ship traffic | provoz osobních lodí | ~~Provoz osobních lodí~~ |

### Titulek / nadpis sekce — velké počáteční písmeno
| Key | Legenda |
| LEGEND | LEGENDA |

### Vlastní jména — vždy velké
Glacier View, Glenn Highway → dálnice Glenn (vlastní jméno), Barry Arm → záliv Barry.

### Celé věty (s tečkou nebo plnou syntaktickou strukturou) — velké počáteční písmeno
„Sledování probíhá od roku 2020." (věta s tečkou) — velké S.

## ABECEDA — KRITICKÉ
- Výstup MUSÍ být VÝHRADNĚ v latince s českou diakritikou (a–z, á, č, ď, é, ě, í, ň, ó, ř, š, ť, ú, ů, ý, ž a velké varianty).
- ZAKÁZÁNO používat cyrilici (а, е, о, р, с, у, х, ы, и, й, А, В, Е, ...) — i když vypadá vizuálně stejně jako latinka, je to chyba. Příklad: "sesuvy" (správně, latinské `y`) vs "sesuvы" (CHYBA, cyrilské `ы` U+044B).
- Když si nejsi jistý, použij ASCII přepis (`y`, `i`, `j`) místo cyrilického znaku.

## VÝSTUP
Vrať JSON pole objektů: [{"id": "...", "czech": "..."}]
DŮLEŽITÉ: V hodnotách "czech" NIKDY nepoužívej rovné uvozovky ("). Místo nich použij české typografické „ " nebo je vynech.
Pouze JSON, žádný další text."""


def get_api_key() -> str | None:
    """Ziska API klic z env nebo .env souboru."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # Zkus .env v rootu projektu
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def translate_batch(
    elements: list[TextElement],
    project_type: str = "idml",
    model: str = TRANSLATION_MODEL,
    max_batch: int = 25,
    backgrounder: str | None = None,
    progress_callback=None,
    project_id: str | None = None,
) -> list[dict]:
    """Prelozi batch elementu pomoci Claude API.

    Args:
        elements: Elementy k prekladu (bez existujiciho prekladu)
        project_type: 'map' nebo 'idml' pro kontextovy prompt
        model: Claude model ID
        max_batch: Max pocet elementu v jednom API volani
        backgrounder: Backgrounder text z PDF pro kontext prekladu
        progress_callback: Volitelny callback(batch_num, total_batches, from_memory_count)

    Returns:
        list[dict]: [{"id": "...", "czech": "..."}] — uspesne preklady
    """
    # API klíč se řeší uvnitř Engine abstrakce (core.engine)

    # Aplikovat translation memory
    memory = load_translation_memory()
    to_translate = []
    from_memory = []

    for el in elements:
        key = el.contents.strip().lower()
        if key in memory:
            from_memory.append({"id": el.id, "czech": memory[key]})
        else:
            to_translate.append(el)

    if from_memory:
        logger.info("Translation memory: %d/%d z cache", len(from_memory), len(elements))

    total_batches = max(1, (len(to_translate) + max_batch - 1) // max_batch) if to_translate else 0

    if progress_callback:
        progress_callback(0, total_batches, len(from_memory))

    if not to_translate:
        return from_memory

    # Engine s trace sledováním
    from core.engine import get_engine
    from core.traces import TraceCollector, get_trace_store

    engine = get_engine()
    collector = TraceCollector(engine, get_trace_store(), module="translation")
    all_results = list(from_memory)

    for i in range(0, len(to_translate), max_batch):
        batch_num = i // max_batch + 1
        batch = to_translate[i:i + max_batch]

        if progress_callback:
            progress_callback(batch_num, total_batches, len(from_memory))

        results = _translate_api_call(collector, batch, project_type, model, backgrounder)
        all_results.extend(results)

    # CyrillicGuard — Claude obcas haluje cyrilici v ceskych prekladech
    # (pozorovany pripad: "sesuvы" misto "sesuvy"). Deterministicky nahradi
    # vizualne identicke homoglyphy latinkou.
    cyrillic_total = 0
    unmapped_total = []
    for r in all_results:
        cz = r.get("czech")
        if cz:
            fixed, n, unmapped = _strip_cyrillic_homoglyphs(cz)
            if n > 0:
                r["czech"] = fixed
                cyrillic_total += n
                logger.debug("CyrillicGuard fix [%s]: %r -> %r", r.get("id"), cz, fixed)
            if unmapped:
                unmapped_total.extend((r.get("id"), c) for c in unmapped)
    if cyrillic_total:
        logger.warning("CyrillicGuard: %d homoglyphu nahrazeno latinkou", cyrillic_total)
    if unmapped_total:
        logger.warning("CyrillicGuard: %d cyrilskych znaku bez mappingu (manualni revize): %s",
                       len(unmapped_total), unmapped_total[:5])

    # Glossary enforcer — post-LLM DB substituce (kanonické názvy z termdb.db)
    try:
        from services.glossary_enforcer import enforce_glossary_on_results
        all_results, fixes = enforce_glossary_on_results(elements, all_results)
        if fixes:
            logger.info("Glossary enforcer: %d překladů vynuceno z termdb.db", len(fixes))
            for fx in fixes[:10]:
                logger.debug("  %s: %r → %r", fx["en"], fx["was"], fx["now"])
            # Ulož fixes do reportu projektu (append-only pro historii)
            if project_id:
                _append_glossary_fixes_report(project_id, fixes)
    except Exception as e:
        logger.warning("Glossary enforcer: chyba (%s) — překlady zůstaly beze změny", e)

    return all_results


def _append_glossary_fixes_report(project_id: str, fixes: list[dict]) -> None:
    """Zapíše glossary enforcer fixes do JSON logu projektu (append)."""
    from datetime import datetime
    from config import PROJECTS_DIR
    try:
        project_dir = PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        log_path = project_dir / "glossary_fixes.json"
        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except (json.JSONDecodeError, OSError):
                existing = []
        ts = datetime.now().isoformat(timespec="seconds")
        entry = {"timestamp": ts, "fixes": fixes}
        existing.append(entry)
        log_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.warning("Nelze uložit glossary_fixes.json: %s", e)


# === CyrillicGuard: deterministicky strip cyrilskych homoglyphu ===
#
# Claude obcas haluje cyrilici v ceskem prekladu (typicky u slov podobnych
# rustine — "sesuvы" misto "sesuvy", U+044B misto U+0079). Cestina cyrilici
# nepouziva, takze jakykoliv cyrilsky znak v prekladu = chyba.
#
# Mapping pokryva vizualne identicke nebo skoro identicke znaky. Cyrilice
# bez mappingu (typicky cisty rusky znak) se necha a logujeme warning —
# editor je ukaze, uzivatel resi manualne.
_CYRILLIC_TO_LATIN = {
    # Lowercase — vizualne identicke / skoro identicke s latinkou
    "а": "a",  # U+0430
    "е": "e",  # U+0435
    "о": "o",  # U+043E
    "р": "p",  # U+0440
    "с": "c",  # U+0441
    "у": "y",  # U+0443
    "х": "x",  # U+0445
    "і": "i",  # U+0456
    "ј": "j",  # U+0458
    "ѕ": "s",  # U+0455
    # Lowercase — nejsou identicke, ale Claude je casto haluje
    # (pozorovane pripady: "sesuvы"→"sesuvy", "нить myšlenky"→"nit myšlenky")
    "ы": "y",  # U+044B (yeru)
    "и": "i",  # U+0438
    "й": "j",  # U+0439
    "н": "n",  # U+043D — H-shape v lowercase, Claude haluje pro n
    "т": "t",  # U+0442 — T-shape
    "к": "k",  # U+043A
    "м": "m",  # U+043C
    # Mekky/tvrdy znak — v cestine bez vyznamu, vyhodit
    "ь": "",  # U+044C (myagkiy znak)
    "ъ": "",  # U+044A (tvyordyy znak)
    # Uppercase — vizualne identicke / skoro identicke
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
    "І": "I", "Ј": "J", "Ѕ": "S",
    "Ы": "Y", "И": "I", "Й": "J",
}


def _strip_cyrillic_homoglyphs(text: str) -> tuple[str, int, list[str]]:
    """Nahradi cyrilske homoglyphy latinkou.

    Returns:
        (fixed_text, num_replaced, unmapped_chars)
        unmapped_chars = cyrilske znaky, ktere mapping neumi resit (logujeme warning).
    """
    if not text:
        return text, 0, []
    out = []
    replaced = 0
    unmapped = []
    for ch in text:
        if ch in _CYRILLIC_TO_LATIN:
            out.append(_CYRILLIC_TO_LATIN[ch])
            replaced += 1
        elif 0x0400 <= ord(ch) <= 0x04FF:
            # Cyrilice bez mappingu — necham
            out.append(ch)
            unmapped.append(ch)
        else:
            out.append(ch)
    return "".join(out), replaced, unmapped


def _escape_control_chars_in_strings(text: str) -> str:
    """Escapuje raw control chars (LF, CR, TAB...) JEN uvnitr JSON stringu.

    JSON spec (RFC 8259):
    - Whitespace mezi tokens (mimo string): LF, CR, TAB, space jsou OK.
    - Uvnitr stringu: control chars musi byt escapovane (\\n, \\r, \\t, \\uXXXX).

    Claude obcas vraci raw LF uvnitr stringu pri prekladu viceradkoveho vstupu
    (napr. vstup "Direction" + LF + "of View" → preklad "Smer" + LF + "pohledu").
    Tento helper opravi pouze tyto chyby a ponecha strukturalni whitespace.
    """
    out = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            out.append(ch)
            escape_next = False
            continue
        if in_string:
            if ch == "\\":
                out.append(ch)
                escape_next = True
            elif ch == '"':
                out.append(ch)
                in_string = False
            elif ord(ch) < 0x20:
                out.append(f"\\u{ord(ch):04x}")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _fix_unescaped_quotes(text: str) -> str:
    """Opravi neescapovane uvozovky uvnitr JSON string hodnot.

    Iterativne: zkusi json.loads, pri chybe na pozici escapuje " a zkusi znovu.
    Max 50 iteraci.
    """
    for _ in range(50):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            pos = e.pos
            if pos < len(text) and text[pos] != '"':
                # Chyba neni na uvozovce — najdi posledni " pred pozici
                prev_quote = text.rfind('"', 0, pos)
                if prev_quote > 0:
                    text = text[:prev_quote] + '\\"' + text[prev_quote + 1:]
                else:
                    break
            elif pos < len(text):
                text = text[:pos] + '\\"' + text[pos + 1:]
            else:
                break
    return text


def _build_term_hints(elements: list[TextElement]) -> str:
    """Vygeneruje terminologický glosář pro batch elementů z referenční DB.

    Extrahuje EN texty, batch-přeloží přes NormalizedTermDB,
    vrátí markdown tabulku nalezených překladů.
    """
    if not _main_db:
        return ""

    try:
        # Extrahuj unikátní texty z elementů
        texts = list({el.contents.strip() for el in elements if el.contents})
        if not texts:
            return ""

        # Batch translate přes referenční DB
        found = _main_db.batch_translate(texts, from_lang="en", to_lang="cs")
        if not found:
            return ""

        lines = [
            "\n## TERMINOLOGICKÝ GLOSÁŘ — OVĚŘENÉ PŘEKLADY (termdb.db, 246K+ termínů)",
            "",
            "⚠️ POVINNÉ: Pro termíny z tabulky níže POUŽIJ POUZE tento český ekvivalent.",
            "ZAKÁZÁNO překládat vlastními slovy, hledat synonyma nebo parafrázovat.",
            "Tyto překlady jsou ověřené z BIOLIB, geografických databází a odborných zdrojů.",
            "Pokud glosář uvádí překlad — je to ta správná volba, nediskutuj.",
            "",
            "| EN | CZ |",
            "|---|---|",
        ]
        for en, cz in sorted(found.items()):
            lines.append(f"| {en} | {cz} |")

        lines.append("")
        logger.info("TermDB hints: %d/%d textů nalezeno v referenční DB", len(found), len(texts))
        return "\n".join(lines)
    except Exception as e:
        logger.warning("TermDB hints: chyba — %s", e)
        return ""


def _translate_api_call(
    collector,
    elements: list[TextElement],
    project_type: str,
    model: str,
    backgrounder: str | None = None,
) -> list[dict]:
    """Jedno API volání pro batch elementů — přes Engine abstrakci."""
    from core.engine import resolve_model

    # Sestavit user prompt
    # Vstupni klic je "en" (ne "text") aby Claude nezachoval stejny klic ve vystupu —
    # opakovane halucinoval [{"id": "...", "text": "<preklad>"}] misto "czech".
    items = []
    for el in elements:
        item = {"id": el.id, "en": el.contents}
        if el.category:
            item["category"] = el.category
        if el.paragraph_style:
            item["style"] = el.paragraph_style
        items.append(item)

    context = "článku v časopise" if project_type == "idml" else "mapy"

    # Terminologický glosář z referenční DB
    term_hints = _build_term_hints(elements)

    user_msg = (
        f"Přelož následující texty z {context} do češtiny.\n\n"
        f"VSTUP používá klíč `en` (anglický originál). "
        f"VÝSTUP MUSÍ používat klíč `czech` (český překlad). "
        f"Vrať: `[{{\"id\": \"...\", \"czech\": \"...\"}}]` — nikdy `text`, `en` ani `translation`.\n\n"
        f"```json\n{json.dumps(items, ensure_ascii=False, indent=2)}\n```"
    )

    # System prompt + term hints + backgrounder
    system = SYSTEM_PROMPT
    if term_hints:
        system += term_hints
    if backgrounder:
        # Omezit backgrounder na ~3000 znaku aby nezabiral prilis tokenu
        bg_text = backgrounder[:3000]
        if len(backgrounder) > 3000:
            bg_text += "\n[...zkráceno]"
        system += (
            "\n\n## Kontext článku (backgrounder pro překladatele)\n"
            "Následující poznámky vysvětlují kontext, výrazy a fakta z článku. "
            "Použij je pro přesnější překlad:\n\n"
            f"{bg_text}"
        )

    logger.info("Claude API: preklady %d textu (model=%s, term_hints=%s)",
                len(elements), model, "yes" if term_hints else "no")

    result = collector.generate(
        messages=[{"role": "user", "content": user_msg}],
        model=resolve_model(model) if len(model) < 20 else model,
        system=system,
        max_tokens=TRANSLATION_MAX_TOKENS,
    )

    logger.info("Překlad: %.1fs, $%.4f, %d+%d tokenů",
                result.latency_seconds, result.cost_usd,
                result.input_tokens, result.output_tokens)

    # Parsovat JSON z odpovedi — extrahuj JSON pole z odpovedi
    raw = result.content.strip()
    logger.info("API response: stop=%s, len=%d, tokens_out=%d",
                result.stop_reason, len(raw), result.output_tokens)

    # Najdi prvni [ a posledni ] — spolehlivejsi nez regex na code fences
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.error("Zadny JSON array v odpovedi: %s", raw[:300])
        raise ValueError(f"Claude API neobsahuje JSON pole: {raw[:200]}...")

    text = raw[start:end + 1]

    # Sanitize Unicode line/paragraph separators (vne i uvnitr stringu)
    text = text.replace("\u2028", " ").replace("\u2029", " ")

    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        # Recovery 1: raw control chars uvnitr JSON stringu
        # (typicky pri prekladu viceradkoveho vstupu "Direction" + LF + "of View")
        text2 = _escape_control_chars_in_strings(text)
        try:
            results = json.loads(text2)
            if text2 != text:
                logger.warning("JSON parse uspel az po escape control chars v stringu")
        except json.JSONDecodeError:
            # Recovery 2: neescapovane uvozovky uvnitr JSON stringu
            fixed = _fix_unescaped_quotes(text2)
            try:
                results = json.loads(fixed)
                logger.warning("JSON parse uspel az po oprave uvozovek")
            except json.JSONDecodeError as exc:
                logger.error("Neplatny JSON (len=%d): %s", len(text), exc)
                raise ValueError(f"Claude API vratil neplatny JSON: {text[:200]}...")

    if not isinstance(results, list):
        raise ValueError(f"Ocekavan JSON pole, dostal: {type(results)}")

    logger.info(
        "Claude API: prelozeno %d textu (input_tokens=%d, output_tokens=%d)",
        len(results),
        result.input_tokens,
        result.output_tokens,
    )

    return results
