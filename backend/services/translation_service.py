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
    for el in elements:
        if el.czech and el.status == "OK" and el.contents:
            en = el.contents.strip()
            cz = el.czech.strip()
            if en and cz and len(en) >= 2 and en.lower() != cz.lower():
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

## ZEMĚPISNÉ NÁZVY
- Zavedené české exonymy: Germany→Německo, Vienna→Vídeň, Mediterranean Sea→Středozemní moře
- Města: London→Londýn, Paris→Paříž, Rome→Řím, Moscow→Moskva, Prague→Praha
- Bez českého ekvivalentu ponech beze změny: Reykjavík, Nuuk, Brattahlíð

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

## FALSE FRIENDS
| EN | Špatně | Správně |
|---|---|---|
| billion | bilion | miliarda |
| evidence | evidence | důkazy, doklady |
| actual/actually | aktuální/aktuálně | skutečný/ve skutečnosti |
| eventually | eventuálně | nakonec |
| dramatic (change) | dramatický | výrazný, zásadní |

## STYL
- Přirozená čeština — ne doslovný překlad
- Zachovej velká písmena (ALL CAPS) pokud jsou v originále — jde o layout
- Zachovej zkratky a odbornou terminologii (geologie, biologie, geografie)
- Diakritika vždy správně

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

    return all_results


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
            "\n## Terminologický glosář (ověřené překlady z referenční databáze)",
            "Použij tyto překlady — jsou ověřené a správné:",
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
    items = []
    for el in elements:
        item = {"id": el.id, "text": el.contents}
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

    # Sanitize Unicode control chars
    text = text.replace("\u2028", " ").replace("\u2029", " ")

    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        # Claude obcas pouzije neescapovane " uvnitr JSON stringu.
        # Opravime: najdeme vsechny " co nejsou JSON strukturalni
        # a nahradime je za typograficke uvozovky.
        fixed = _fix_unescaped_quotes(text)
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
