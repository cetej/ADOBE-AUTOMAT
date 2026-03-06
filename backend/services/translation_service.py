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

from config import TRANSLATION_MEMORY_PATH
from models import TextElement

logger = logging.getLogger(__name__)

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
) -> list[dict]:
    """Prelozi batch elementu pomoci Claude API.

    Args:
        elements: Elementy k prekladu (bez existujiciho prekladu)
        project_type: 'map' nebo 'idml' pro kontextovy prompt
        model: Claude model ID
        max_batch: Max pocet elementu v jednom API volani

    Returns:
        list[dict]: [{"id": "...", "czech": "..."}] — uspesne preklady

    Raises:
        ValueError: Pokud neni nastaven API klic
        anthropic.APIError: Pri chybe API
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

    if not to_translate:
        return from_memory

    # Rozdelit na batche
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)
    all_results = list(from_memory)

    for i in range(0, len(to_translate), max_batch):
        batch = to_translate[i:i + max_batch]
        results = _translate_api_call(client, batch, project_type, model)
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


def _translate_api_call(
    client: anthropic.Anthropic,
    elements: list[TextElement],
    project_type: str,
    model: str,
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
    user_msg = (
        f"Přelož následující texty z {context} do češtiny.\n\n"
        f"```json\n{json.dumps(items, ensure_ascii=False, indent=2)}\n```"
    )

    logger.info("Claude API: preklady %d textu (model=%s)", len(elements), model)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
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
