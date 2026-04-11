"""IDML Write-back: zapis ceskych prekladu zpet do IDML souboru.

Workflow:
1. Unpack IDML do temp adresare
2. Pro kazdy story: batch replace originalu za ceske preklady
3. Pack zpet do noveho IDML
4. Validace vysledku
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from collections import defaultdict
from pathlib import Path

from config import EXPORTS_DIR
from services.idml_processor import unpack_idml, pack_idml, cleanup_temp, list_stories
from services.idml_writer import safe_batch_replace
from services.idml_validator import validate_packed_idml
from services.text_pipeline.element_merger import strip_pipeline_markers

logger = logging.getLogger(__name__)


def writeback_idml(
    idml_path: str | Path,
    elements: list,
    project_id: str,
    output_suffix: str = "_CZ",
) -> dict:
    """Zapise ceske preklady zpet do IDML a vytvori novy soubor.

    Args:
        idml_path: Cesta k originalnimu IDML.
        elements: Seznam TextElement s preklady.
        project_id: ID projektu (pro nazev exportu).
        output_suffix: Suffix pro nazev vystupniho souboru (default "_CZ",
                       pro korektury "_CZ_r01" apod.)

    Returns:
        dict s vysledkem: output_path, replaced, skipped, errors
    """
    idml_path = Path(idml_path)
    if not idml_path.exists():
        raise FileNotFoundError(f"IDML soubor nenalezen: {idml_path}")

    # Pripravit elementy s preklady, seskupit podle story
    stories_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    skipped = 0
    for el in elements:
        if not el.czech or not el.contents.strip():
            skipped += 1
            continue
        if not el.story_id:
            skipped += 1
            continue
        stories_map[el.story_id].append((el.contents, strip_pipeline_markers(el.czech)))

    if not stories_map:
        return {"output_path": None, "replaced": 0, "skipped": skipped, "errors": ["Zadne preklady k zapisu"]}

    # Unpack
    temp_dir = unpack_idml(idml_path)
    logger.info("Writeback: unpacked to %s, %d stories to update", temp_dir, len(stories_map))

    try:
        total_replaced = 0
        errors = []

        # Aplikovat preklady
        stories_dir = temp_dir / "Stories"
        for story_id, replacements in stories_map.items():
            story_file = stories_dir / f"{story_id}.xml"
            if not story_file.exists():
                errors.append(f"Story {story_id} nenalezen")
                continue

            replaced = safe_batch_replace(story_file, replacements)
            if replaced == 0 and len(replacements) > 0:
                errors.append(f"Story {story_id}: 0/{len(replacements)} nahrazeno")
            total_replaced += replaced

        # Pack zpet
        stem = idml_path.stem
        output_name = f"{stem}{output_suffix}.idml"
        output_path = EXPORTS_DIR / project_id / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pack_idml(temp_dir, output_path)

        # Validace
        validation = validate_packed_idml(output_path)
        if not validation.get("valid", False):
            errors.extend(validation.get("errors", []))
            logger.warning("Writeback IDML validace: %s", validation.get("errors"))

        logger.info(
            "Writeback hotov: %d nahrazeno, %d preskoceno, %d chyb",
            total_replaced, skipped, len(errors),
        )

        return {
            "output_path": str(output_path),
            "output_name": output_name,
            "replaced": total_replaced,
            "total_elements": len(elements),
            "skipped": skipped,
            "errors": errors,
            "validation": validation,
        }

    finally:
        cleanup_temp(temp_dir)
