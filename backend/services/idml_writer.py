"""Bezpecny zapis textu do IDML Story XML.

KRITICKE PRAVIDLO: NIKDY nepouzivat ElementTree.write()!
- Nici XML deklaraci (standalone="yes")
- Konvertuje uvozovky
- Maze Processing Instructions (<?aid ...?>)
- InDesign odmitne otevrit takovy soubor

Vzdy pouzivat string replace na raw XML stringu.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def xml_escape(text: str) -> str:
    """Escapuje specialni znaky pro XML obsah."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
    )



def _build_content_pattern(escaped_text: str) -> str:
    """Vytvori regex pattern pro <Content> s toleranci na whitespace okolo textu.

    Extrakce stripuje whitespace, ale XML muze mit mezery/taby/U+2028 na zacatku/konci.
    Pattern matchuje volitelny whitespace pred a za textem.
    """
    # Escapovat regex specialni znaky v textu
    regex_safe = re.escape(escaped_text)
    # Tolerovat &apos; i literal ' (InDesign pouziva obe formy)
    regex_safe = regex_safe.replace(re.escape("&apos;"), "(?:&apos;|')")
    return r"<Content>(\s*)" + regex_safe + r"(\s*)</Content>"


def safe_batch_replace(
    story_path: str | Path,
    replacements: list[tuple[str, str]],
) -> int:
    """Provede vice nahrazeni v jednom Story XML souboru.

    Pouziva whitespace-tolerantni matching — extrakce stripuje whitespace,
    ale XML muze mit mezery okolo textu. Zachovava puvodni whitespace.

    Args:
        story_path: Cesta k Story_*.xml.
        replacements: Seznam (old_text, new_text) dvojic.

    Returns:
        Pocet uspesnych nahrazeni.
    """
    story_path = Path(story_path)

    data = story_path.read_bytes()
    xml_str = data.decode("utf-8")

    replaced = 0
    for old_text, new_text in replacements:
        escaped_old = xml_escape(old_text)
        escaped_new = xml_escape(new_text)

        # 1. Zkus presny match (nejrychlejsi)
        old_content = f"<Content>{escaped_old}</Content>"
        if old_content in xml_str:
            xml_str = xml_str.replace(old_content, f"<Content>{escaped_new}</Content>", 1)
            replaced += 1
            continue

        # 2. Zkus whitespace-tolerantni regex match
        pattern = _build_content_pattern(escaped_old)
        match = re.search(pattern, xml_str)
        if match:
            # Zachovat puvodni whitespace (leading/trailing)
            ws_before = match.group(1)
            ws_after = match.group(2)
            new_content = f"<Content>{ws_before}{escaped_new}{ws_after}</Content>"
            xml_str = xml_str[:match.start()] + new_content + xml_str[match.end():]
            replaced += 1
        else:
            logger.warning("Content not found: '%s'", old_text[:50])

    if replaced == 0:
        return 0

    # Validace po vsech zmenach
    from services.idml_validator import validate_xml_string
    if not validate_xml_string(xml_str):
        logger.error("XML validation failed after batch replace in %s", story_path.name)
        # Nezapisujeme — vracime 0
        return 0

    story_path.write_bytes(xml_str.encode("utf-8"))
    logger.info("Replaced %d/%d contents in %s", replaced, len(replacements), story_path.name)
    return replaced


def safe_regex_in_content(
    story_path: str | Path,
    pattern: str,
    replacement: str,
    min_length: int = 20,
) -> int:
    """Aplikuje regex JEN uvnitr <Content> elementu.

    Args:
        story_path: Cesta k Story_*.xml.
        pattern: Regex vzor.
        replacement: Nahrazovaci retezec.
        min_length: Minimalni delka obsahu pro aplikaci (guard pro kratke tech. texty).

    Returns:
        Pocet zmenenych Content elementu.
    """
    story_path = Path(story_path)

    data = story_path.read_bytes()
    xml_str = data.decode("utf-8")
    changes = 0

    def fix_content(match):
        nonlocal changes
        content = match.group(1)

        # Guard: preskocit kratke technicke texty
        if len(content) < min_length:
            return match.group(0)

        fixed = re.sub(pattern, replacement, content)
        if fixed != content:
            changes += 1
        return f"<Content>{fixed}</Content>"

    xml_str = re.sub(
        r"<Content>(.*?)</Content>",
        fix_content,
        xml_str,
        flags=re.DOTALL,
    )

    if changes == 0:
        return 0

    from services.idml_validator import validate_xml_string
    if not validate_xml_string(xml_str):
        logger.error("XML validation failed after regex fix in %s", story_path.name)
        return 0

    story_path.write_bytes(xml_str.encode("utf-8"))
    return changes
