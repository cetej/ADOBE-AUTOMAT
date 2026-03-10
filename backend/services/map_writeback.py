"""Zapis prelozenych textu zpet do Illustratoru (MAP projekty).

Workflow:
1. Filtruj elementy s prekladem (czech != None)
2. Seskup podle layer_name
3. Po davkach (adaptivne podle velikosti payloadu) posli ExtendScript do Illustratoru
4. Volitelne uloz dokument
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import logging
from pathlib import Path

from services.illustrator_bridge import execute_script

logger = logging.getLogger(__name__)

MAX_BATCH_ITEMS = 30        # Horni limit poctu polozek v davce
MAX_BATCH_BYTES = 50_000    # ~50 KB — bezpecny limit pro ExtendScript string
_SCRIPT_PATH = Path(__file__).parent.parent / "extendscripts" / "write_texts.jsx"


def _load_script():
    """Nacte script vzdy cerstvy z disku (kvuli reload pri vyvoji)."""
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def _make_batches(writable: list) -> list[list]:
    """Rozdeli polozky do davek podle velikosti payloadu i poctu.

    Kratke texty (mapove popisky) jdou ve vetsi davce,
    dlouhe texty (clanky) se automaticky rozloží do mensich davek.
    """
    batches = []
    current = []
    current_size = 2  # zaciname s "[]"

    for item in writable:
        # Odhadni velikost JSON pro tuto polozku
        item_json = json.dumps(
            [item[0], item[1], item[2], item[3]], ensure_ascii=False
        )
        item_size = len(item_json.encode("utf-8")) + 2  # +2 za carku a mezeru

        # Novy batch pokud by prekrocil limit
        if current and (
            current_size + item_size > MAX_BATCH_BYTES
            or len(current) >= MAX_BATCH_ITEMS
        ):
            batches.append(current)
            current = []
            current_size = 2

        current.append(item)
        current_size += item_size

    if current:
        batches.append(current)

    return batches


def writeback_map(elements: list, save_document: bool = True) -> dict:
    """Zapise prelozene texty zpet do Illustratoru.

    Args:
        elements: Seznam TextElement s czech preklady.
        save_document: Zda po zapisu ulozit .ai dokument.

    Returns:
        Dict s vysledky: changed, total, skipped, errors.
    """
    # Filtruj elementy s prekladem a layer_name
    writable = []
    for elem in elements:
        if not elem.czech or not elem.layer_name:
            continue
        # ID format: "LayerName/0" nebo "LayerName#4/0" (deduplikovany)
        parts = elem.id.rsplit("/", 1)
        if len(parts) != 2:
            continue
        try:
            index = int(parts[1])
        except ValueError:
            continue
        # Parsuj layerId z deduplikovaneho ID
        layer_part = parts[0]
        layer_id = -1  # -1 = hledej jen podle jmena
        if "#" in layer_part:
            name_part, id_part = layer_part.rsplit("#", 1)
            try:
                layer_id = int(id_part)
            except ValueError:
                pass
        # \n -> \r pro Illustrator
        text = elem.czech.replace("\n", "\r")
        writable.append((elem.layer_name, layer_id, index, text))

    if not writable:
        return {"changed": 0, "total": 0, "skipped": len(elements), "errors": []}

    # Adaptivni davkovani — podle velikosti payloadu i poctu
    batches = _make_batches(writable)
    total_changed = 0
    all_errors = []

    logger.info("Writeback: %d textu v %d davkach", len(writable), len(batches))

    for batch_idx, batch in enumerate(batches):
        translations_json = json.dumps(
            [[layer, lid, idx, text] for layer, lid, idx, text in batch],
            ensure_ascii=False,
        )
        script = _load_script().replace("%%TRANSLATIONS%%", translations_json)

        logger.debug(
            "Batch %d/%d: %d polozek, %d B payload",
            batch_idx + 1, len(batches), len(batch), len(translations_json.encode("utf-8")),
        )

        try:
            result = execute_script(script, timeout=120)
            text_content = _extract_text(result)
            if text_content:
                data = json.loads(text_content)
                total_changed += data.get("changed", 0)
                all_errors.extend(data.get("errors", []))
            else:
                all_errors.append({"batch": batch_idx, "error": "Empty response from Illustrator"})
        except Exception as e:
            logger.error("Batch %d/%d selhal: %s", batch_idx + 1, len(batches), e)
            all_errors.append({"batch": batch_idx, "error": str(e)})

    # Ulozit dokument
    if save_document and total_changed > 0:
        try:
            execute_script("app.activeDocument.save(); return JSON.stringify({saved: true});", timeout=30)
            logger.info("Dokument ulozen")
        except Exception as e:
            logger.warning("Ulozeni dokumentu selhalo: %s", e)
            all_errors.append({"error": f"Document save failed: {e}"})

    skipped = len(elements) - len(writable)
    return {
        "changed": total_changed,
        "total": len(writable),
        "skipped": skipped,
        "errors": all_errors,
    }


def preview_map(elements: list) -> dict:
    """Nahled: kolik textu bude zapsano."""
    total = len(elements)
    with_czech = sum(1 for e in elements if e.czech)
    writable = sum(
        1 for e in elements
        if e.czech and e.layer_name and "/" in e.id
    )
    no_translation = sum(
        1 for e in elements
        if not e.czech and e.contents and e.contents.strip()
    )

    return {
        "total_elements": total,
        "with_translation": with_czech,
        "writable": writable,
        "missing_translation": no_translation,
        "coverage_pct": round(with_czech / total * 100, 1) if total else 0,
    }


def _extract_text(response: dict) -> str | None:
    """Vytahne textovy obsah z proxy response."""
    if not response:
        return None
    # Format: {"content": [{"type": "text", "text": "..."}]}
    content = response.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text")
    # Fallback — primo text
    if isinstance(response, str):
        return response
    return None
