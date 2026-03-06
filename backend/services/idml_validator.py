"""Validace XML souboru v IDML archivu.

Po kazde zmene v Story XML je NUTNE validovat pomoci ET.fromstring().
Toto je jediny zpusob jak zajistit, ze InDesign soubor otevre.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_xml_string(xml_str: str) -> bool:
    """Validuje XML retezec.

    Returns:
        True pokud je XML validni.
    """
    try:
        ET.fromstring(xml_str.encode("utf-8"))
        return True
    except ET.ParseError as e:
        logger.error("XML parse error: %s", e)
        return False


def validate_xml_file(xml_path: str | Path) -> bool:
    """Validuje jeden XML soubor."""
    xml_path = Path(xml_path)
    try:
        data = xml_path.read_bytes()
        ET.fromstring(data)
        return True
    except ET.ParseError as e:
        logger.error("Invalid XML in %s: %s", xml_path.name, e)
        return False
    except Exception as e:
        logger.error("Error reading %s: %s", xml_path.name, e)
        return False


def validate_unpacked_idml(unpacked_dir: str | Path) -> dict:
    """Validuje vsechny XML soubory v rozbalenem IDML.

    Returns:
        dict s klici: valid (bool), errors (list[str]), total (int), passed (int)
    """
    unpacked_dir = Path(unpacked_dir)
    errors = []
    total = 0
    passed = 0

    # Kontrola mimetype
    mt = unpacked_dir / "mimetype"
    if not mt.exists():
        errors.append("Missing 'mimetype' file")
    else:
        content = mt.read_text(encoding="utf-8").strip()
        if "indesign" not in content.lower():
            errors.append(f"Unexpected mimetype content: {content[:100]}")

    # Validace vsech XML souboru
    for xml_file in sorted(unpacked_dir.rglob("*.xml")):
        total += 1
        if validate_xml_file(xml_file):
            passed += 1
        else:
            errors.append(f"Invalid XML: {xml_file.relative_to(unpacked_dir)}")

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "total": total,
        "passed": passed,
    }

    if errors:
        logger.warning("IDML validation: %d/%d XML files valid, %d errors", passed, total, len(errors))
    else:
        logger.info("IDML validation: all %d XML files valid", total)

    return result


def validate_packed_idml(idml_path: str | Path) -> dict:
    """Validuje zabaleny IDML soubor.

    Kontroluje:
    1. Je to validni ZIP
    2. mimetype je prvni soubor
    3. mimetype je nekomprimovany
    4. Vsechny XML soubory jsou parsovatelne
    """
    idml_path = Path(idml_path)
    errors = []
    total = 0
    passed = 0

    try:
        with zipfile.ZipFile(idml_path, "r") as zf:
            names = zf.namelist()

            # mimetype check
            if not names or names[0] != "mimetype":
                errors.append(f"mimetype is not first file (first: {names[0] if names else 'EMPTY'})")

            if "mimetype" in names:
                info = zf.getinfo("mimetype")
                if info.compress_type != zipfile.ZIP_STORED:
                    errors.append(f"mimetype is compressed (type={info.compress_type}), must be STORED")

            # XML validation
            for name in names:
                if not name.endswith(".xml"):
                    continue
                total += 1
                try:
                    data = zf.read(name)
                    ET.fromstring(data)
                    passed += 1
                except ET.ParseError as e:
                    errors.append(f"Invalid XML in {name}: {e}")

    except zipfile.BadZipFile:
        errors.append("File is not a valid ZIP archive")
    except Exception as e:
        errors.append(f"Error opening IDML: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "total": total,
        "passed": passed,
    }
