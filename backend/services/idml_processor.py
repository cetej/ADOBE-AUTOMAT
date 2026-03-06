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


def list_stories(unpacked_dir: str | Path) -> list[Path]:
    """Vrati seznam Story XML souboru v rozbalenem IDML."""
    stories_dir = Path(unpacked_dir) / "Stories"
    if not stories_dir.exists():
        return []
    return sorted(stories_dir.glob("Story_*.xml"))
