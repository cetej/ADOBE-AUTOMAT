"""Unpack a repack IDML souboru (ZIP archive).

IDML = ZIP s XML soubory. Kriticke pravidlo:
- 'mimetype' musi byt PRVNI soubor v archivu a NEKOMPRIMOVANY (ZIP_STORED).
- Vsechny ostatni soubory komprimovane (ZIP_DEFLATED).
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import shutil
import zipfile
import logging
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def unpack_idml(idml_path: str | Path, dest_dir: str | Path | None = None) -> Path:
    """Rozbal IDML do adresare.

    Args:
        idml_path: Cesta k .idml souboru.
        dest_dir: Cilovy adresar. Pokud None, vytvori temp adresar.

    Returns:
        Path k rozbalenemu adresari.
    """
    idml_path = Path(idml_path)
    if not idml_path.exists():
        raise FileNotFoundError(f"IDML file not found: {idml_path}")

    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix="idml_"))
    else:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(idml_path, "r") as zf:
        zf.extractall(dest_dir)

    logger.info("Unpacked IDML to %s (%d files)", dest_dir, len(list(dest_dir.rglob("*"))))
    return dest_dir


def pack_idml(source_dir: str | Path, output_path: str | Path) -> Path:
    """Zabal adresar zpet do IDML.

    Mimetype MUSI byt prvni soubor a NEKOMPRIMOVANY.

    Args:
        source_dir: Adresar s rozbalenym IDML.
        output_path: Cesta k vysledenmu .idml souboru.

    Returns:
        Path k vytvrenemu IDML souboru.
    """
    source_dir = Path(source_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w") as zf:
        # 1. mimetype — prvni, nekomprimovany
        mt = source_dir / "mimetype"
        if mt.exists():
            zf.write(mt, "mimetype", compress_type=zipfile.ZIP_STORED)
        else:
            # Pokud chybi, vytvorime defaultni
            zf.writestr(
                zipfile.ZipInfo("mimetype"),
                "application/vnd.adobe.indesign-idml-package",
            )

        # 2. Vsechny ostatni soubory — komprimovane
        for root, _dirs, files in os.walk(source_dir):
            for fname in sorted(files):
                if fname == "mimetype":
                    continue
                full = Path(root) / fname
                arcname = full.relative_to(source_dir).as_posix()
                zf.write(full, arcname, compress_type=zipfile.ZIP_DEFLATED)

    logger.info("Packed IDML to %s", output_path)
    return output_path


def cleanup_temp(temp_dir: str | Path) -> None:
    """Smaze docasny adresar."""
    temp_dir = Path(temp_dir)
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info("Cleaned up temp dir: %s", temp_dir)


def get_master_story_ids(unpacked_dir: str | Path) -> set[str]:
    """Vrati mnozinu story ID referencovanych POUZE z MasterSpreads.

    Master pages obsahuji template/placeholder texty (pseudo-latina),
    ktere nejsou soucasti redakcniho obsahu.
    """
    unpacked_dir = Path(unpacked_dir)
    master_dir = unpacked_dir / "MasterSpreads"
    spread_dir = unpacked_dir / "Spreads"

    def _collect_parent_stories(directory: Path) -> set[str]:
        stories = set()
        if not directory.exists():
            return stories
        for xml_file in directory.glob("*.xml"):
            try:
                tree = ET.parse(xml_file)
                for elem in tree.getroot().iter():
                    ps = elem.get("ParentStory", "")
                    if ps:
                        stories.add(ps)
            except ET.ParseError:
                logger.warning("Failed to parse %s", xml_file)
        return stories

    master_stories = _collect_parent_stories(master_dir)
    spread_stories = _collect_parent_stories(spread_dir)

    # Stories referencovane POUZE z master pages (ne ze spreadu)
    master_only = master_stories - spread_stories
    if master_only:
        logger.info(
            "Found %d master-page-only stories (will be skipped): %s",
            len(master_only), sorted(master_only)[:5],
        )
    return master_only


def list_stories(unpacked_dir: str | Path, skip_master: bool = True) -> list[Path]:
    """Vrati seznam Story XML souboru v rozbalenem IDML.

    Stories jsou serazene podle vizualniho poradi na spreadu (Y pozice
    textoveho ramce). Stories bez ramce na spreadu jsou na konci.

    Args:
        skip_master: Pokud True, preskoci stories patrici pouze master pages
                     (template/placeholder texty).
    """
    unpacked_dir = Path(unpacked_dir)
    stories_dir = unpacked_dir / "Stories"
    if not stories_dir.exists():
        return []

    all_stories = sorted(stories_dir.glob("Story_*.xml"))

    if not skip_master:
        master_ids = set()
    else:
        master_ids = get_master_story_ids(unpacked_dir)

    if master_ids:
        filtered = [
            s for s in all_stories
            if s.stem.replace("Story_", "") not in master_ids
        ]
        logger.info(
            "Stories: %d total, %d after master page filtering",
            len(all_stories), len(filtered),
        )
    else:
        filtered = all_stories

    # Seřadí stories podle Y pozice textových rámců na spreadu
    story_order = _get_story_visual_order(unpacked_dir)
    filtered.sort(key=lambda s: story_order.get(s.stem.replace("Story_", ""), 9999))

    return filtered


def _get_story_visual_order(unpacked_dir: Path) -> dict[str, float]:
    """Vrátí mapování story_id → Y pozice z TextFrame na spreadech.

    Umožňuje řadit stories podle vizuálního pořadí na stránce (shora dolů).
    """
    spread_dir = unpacked_dir / "Spreads"
    if not spread_dir.exists():
        return {}

    order = {}
    for xml_file in spread_dir.glob("*.xml"):
        try:
            tree = ET.parse(xml_file)
            for elem in tree.getroot().iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag != "TextFrame":
                    continue
                story_id = elem.get("ParentStory", "")
                transform = elem.get("ItemTransform", "")
                if story_id and transform:
                    parts = transform.split()
                    if len(parts) >= 6:
                        y = float(parts[-1])
                        # Pokud story už má pozici, vezmi nižší Y (vyšší na stránce)
                        if story_id not in order or y < order[story_id]:
                            order[story_id] = y
        except (ET.ParseError, ValueError) as e:
            logger.warning("Failed to parse spread %s: %s", xml_file, e)

    return order
