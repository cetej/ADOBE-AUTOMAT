"""Export map šablon do Illustratoru a re-import editovaných map.

Komunikace s Illustratorem přes illustrator_bridge (Socket.IO → CEP proxy → AI).
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from models_layout import Bounds, StyleProfile

logger = logging.getLogger(__name__)

# Cesta k ExtendScript šabloně
SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "extendscripts"
MAP_TEMPLATE_SCRIPT = SCRIPT_DIR / "create_map_template.jsx"

# Bleed pro mapy (v pt)
MAP_BLEED_PT = 8.5  # ~3mm


async def check_illustrator() -> dict:
    """Zkontroluje připojení k Illustratoru."""
    from services.illustrator_bridge import check_connection
    return await check_connection()


def export_map_template(
    slot_bounds: Bounds,
    output_dir: Path,
    slot_id: str = "map",
    style_profile: Optional[StyleProfile] = None,
    label_text: str = "",
    bleed: float = MAP_BLEED_PT,
) -> Path:
    """Vytvoří .ai šablonu pro mapu/infografiku v Illustratoru.

    Args:
        slot_bounds: Rozměry slotu z layout plánu (pt).
        output_dir: Adresář pro uložení .ai souboru.
        slot_id: ID slotu (pro pojmenování souboru).
        style_profile: Typografický profil (pro font labelu).
        label_text: Volitelný popisek v šabloně.
        bleed: Velikost bleedu v pt.

    Returns:
        Path k vytvořenému .ai souboru.

    Raises:
        RuntimeError: Pokud Illustrator není připojený nebo script selže.
    """
    from services.illustrator_bridge import execute_script

    output_dir.mkdir(parents=True, exist_ok=True)
    ai_filename = f"map_template_{slot_id}.ai"
    ai_path = output_dir / ai_filename

    # Forward slashes pro ExtendScript
    save_path_str = str(ai_path).replace("\\", "/")

    # Font z style profile
    font_family = "MinionPro-Regular"
    if style_profile and style_profile.caption_styles:
        first_caption = style_profile.caption_styles[0]
        if first_caption.font_family:
            font_family = first_caption.font_family

    # Načíst a parametrizovat ExtendScript
    script_template = MAP_TEMPLATE_SCRIPT.read_text(encoding="utf-8")
    script = (
        script_template
        .replace("%%WIDTH%%", str(round(slot_bounds.width, 2)))
        .replace("%%HEIGHT%%", str(round(slot_bounds.height, 2)))
        .replace("%%SAVE_PATH%%", save_path_str)
        .replace("%%BLEED%%", str(round(bleed, 2)))
        .replace("%%LABEL_TEXT%%", label_text.replace('"', '\\"'))
        .replace("%%FONT_FAMILY%%", font_family)
    )

    logger.info(
        "Exporting map template: %s (%.0f × %.0f pt, bleed=%.1f)",
        ai_filename, slot_bounds.width, slot_bounds.height, bleed,
    )

    result = execute_script(script, timeout=30)

    # Parsovat výsledek
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            pass

    if isinstance(result, dict):
        if result.get("success") is False:
            raise RuntimeError(f"Illustrator script error: {result.get('error', 'unknown')}")
    elif isinstance(result, str) and "error" in result.lower():
        raise RuntimeError(f"Illustrator error: {result}")

    # Ověřit, že soubor byl vytvořen
    if not ai_path.exists():
        raise RuntimeError(f"Template file was not created: {ai_path}")

    logger.info("Map template created: %s", ai_path)
    return ai_path


def import_edited_map(
    source_path: Path,
    project_dir: Path,
    slot_id: str,
) -> Path:
    """Importuje editovanou mapu do layout projektu.

    Podporované formáty: .png, .jpg, .jpeg, .tif, .tiff, .pdf, .ai, .eps

    Args:
        source_path: Cesta k uploadovanému souboru.
        project_dir: Adresář layout projektu.
        slot_id: ID slotu, ke kterému se mapa vztahuje.

    Returns:
        Path k uložené mapě v projektu.
    """
    maps_dir = project_dir / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_path.suffix.lower()
    allowed = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".ai", ".eps"}
    if suffix not in allowed:
        raise ValueError(f"Nepodporovaný formát mapy: {suffix} (povolené: {', '.join(sorted(allowed))})")

    dest_filename = f"{slot_id}{suffix}"
    dest_path = maps_dir / dest_filename

    # Kopírovat soubor
    shutil.copy2(source_path, dest_path)

    logger.info("Imported edited map: %s → %s", source_path.name, dest_path)
    return dest_path


def get_project_maps(project_dir: Path) -> list[dict]:
    """Vrátí seznam map v projektu (detekované + editované).

    Returns:
        Seznam dicts s info o mapách.
    """
    maps_dir = project_dir / "maps"
    maps = []

    if not maps_dir.exists():
        return maps

    for f in sorted(maps_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".ai", ".eps",
        }:
            # Slot ID = filename bez přípony
            slot_id = f.stem
            maps.append({
                "slot_id": slot_id,
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "format": f.suffix.lower().lstrip("."),
                "status": "edited",
            })

    return maps


def resolve_image_with_maps(
    image_path: str,
    slot_id: str,
    maps_dir: Path,
) -> str:
    """Resolve cestu k obrázku — pokud existuje editovaná mapa, použij ji.

    Args:
        image_path: Původní cesta k obrázku.
        slot_id: ID slotu.
        maps_dir: Adresář s editovanými mapami.

    Returns:
        Cesta k souboru (mapa nebo originální obrázek).
    """
    if not maps_dir.exists():
        return image_path

    # Hledat soubor s názvem slot_id.*
    for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"):
        map_file = maps_dir / f"{slot_id}{ext}"
        if map_file.exists():
            logger.debug("Using edited map for slot %s: %s", slot_id, map_file)
            return str(map_file)

    return image_path
