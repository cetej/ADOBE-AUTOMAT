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

import anthropic

from config import TRANSLATION_MEMORY_PATH, MULTI_DOMAIN_DB_PATH
from models import TextElement

logger = logging.getLogger(__name__)

# Terminologická databáze (ngm-terminology v2.0 — 244K+ ověřených překladů)
try:
    from ngm_terminology import NormalizedTermDB
    _multi_db = NormalizedTermDB(MULTI_DOMAIN_DB_PATH) if Path(MULTI_DOMAIN_DB_PATH).exists() else None
    if _multi_db:
        logger.info("TermDB: načtena referenční DB (%s)", MULTI_DOMAIN_DB_PATH)
except (ImportError, Exception) as e:
    _multi_db = None
    logger.info("TermDB: nedostupná (%s)", e)

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
    """Zapíše schválené překlady (status=OK) zpět do NG-ROBOT terminology.db.

    Slouží jako zpětná vazba z ADOBE-AUTOMAT do sdílené terminologické DB.
    Zapisuje do flat TermDB (operational), ne do referenční NormalizedTermDB.
    """
    try:
        from ngm_terminology import TermDB
        from ngm_terminology.config import find_term_db
    except ImportError:
        return 0

    term_db_path = find_term_db()
    if not term_db_path:
        return 0

    try:
        tdb = TermDB(term_db_path)
    except Exception:
        return 0

    added = 0
    for el in elements:
        if el.czech and el.status == "OK" and el.contents:
            en = el.contents.strip()
            cz = el.czech.strip()
            if en and cz and len(en) >= 2 and en.lower() != cz.lower():
                # Určení domény z kategorie elementu
                domain = _category_to_domain(el.category)
                is_new = tdb.add_term(
                    en=en, cz=cz, domain=domain,
                    source="adobe-automat"
                )
                if is_new:
                    added += 1

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

SYSTEM_PROMPT = """Jsi profesionální překladatel pro National Geographic Česko. Překládáš anglické texty do češtiny.

## Pravidla překladu

### Zeměpisné názvy
- Používej zavedené české exonymy: Germany→Německo, Vienna→Vídeň, Mediterranean Sea→Středozemní moře
- Ponech názvy bez českého ekvivalentu beze změny: Reykjavík, Nuuk, Brattahlíð
- České varianty měst: London→Londýn, Paris→Paříž, Rome→Řím, Moscow→Moskva

### Formáty datací
- A.D. 700 → 700 n. l.
- 700 BC → 700 př. n. l.
- ca./c. → cca
- 1st century → 1. století

### Zkratky států
- U.K. → VB, GER. → NĚM., SPA. → ŠPA., GRE. → ŘEC., SWI. → ŠVÝ., AUT. → RAK.

### Styl
- Přirozená, plynulá čeština bez doslovného překladu
- Zachovej odbornou terminologii (geologie, historie, biologie)
- Zachovej formátování (velká písmena, interpunkce)
- Krátké popisky překládej stručně, delší texty přirozeně
- Diakritika vždy správně

## Výstup
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
    model: str = "claude-sonnet-4-20250514",
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
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY neni nastaven. "
            "Nastavte env promennou nebo vytvorte .env soubor v rootu projektu."
        )

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

    # Rozdelit na batche
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)
    all_results = list(from_memory)

    for i in range(0, len(to_translate), max_batch):
        batch_num = i // max_batch + 1
        batch = to_translate[i:i + max_batch]

        if progress_callback:
            progress_callback(batch_num, total_batches, len(from_memory))

        results = _translate_api_call(client, batch, project_type, model, backgrounder)
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
    if not _multi_db:
        return ""

    try:
        # Extrahuj unikátní texty z elementů
        texts = list({el.contents.strip() for el in elements if el.contents})
        if not texts:
            return ""

        # Batch translate přes referenční DB
        found = _multi_db.batch_translate(texts, from_lang="en", to_lang="cs")
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
    client: anthropic.Anthropic,
    elements: list[TextElement],
    project_type: str,
    model: str,
    backgrounder: str | None = None,
) -> list[dict]:
    """Jedno API volani pro batch elementu."""
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

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    # Parsovat JSON z odpovedi — extrahuj JSON pole z odpovedi
    raw = response.content[0].text.strip()
    logger.info("API response: stop=%s, len=%d, tokens_out=%d",
                response.stop_reason, len(raw), response.usage.output_tokens)

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
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    return results
