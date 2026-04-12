"""Extrakce textovych elementu z IDML Story XML souboru.

Parsuje <Content> elementy z ParagraphStyleRange/CharacterStyleRange
a klasifikuje je podle stylu (lead, body, subtitle, heading, atd.).
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from models import TextElement, TextCategory

logger = logging.getLogger(__name__)


def parse_story(story_path: str | Path) -> list[dict]:
    """Parsuje jeden Story XML soubor a vrati seznam elementu.

    Returns:
        list[dict]: Kazdy element ma klice:
            type ('Content' | 'Br'), text, ps (paragraph style),
            cap, pt, bl, fc, cs (character style), trk
    """
    story_path = Path(story_path)
    tree = ET.parse(story_path)
    elements = []

    for psr in tree.getroot().iter():
        tag = _local_tag(psr.tag)
        if tag != "ParagraphStyleRange":
            continue

        ps = _style_name(psr.get("AppliedParagraphStyle", ""))

        # Sbírá CharacterStyleRange přímo i uvnitř <Change> (Track Changes)
        # Change může být: (A) potomek PSR, (B) potomek CSR uvnitř PSR
        csr_sources = []
        for child in psr:
            ctag = _local_tag(child.tag)
            if ctag == "CharacterStyleRange":
                csr_sources.append(child)
            elif ctag == "Change":
                if child.get("ChangeType", "") == "DeletedText":
                    continue
                for grandchild in child:
                    if _local_tag(grandchild.tag) == "CharacterStyleRange":
                        csr_sources.append(grandchild)

        for csr in csr_sources:
            cap = csr.get("Capitalization", "")
            pt = csr.get("PointSize", "")
            bl = csr.get("BaselineShift", "")
            fc = csr.get("FillColor", "")
            cs = _style_name(csr.get("AppliedCharacterStyle", ""))
            trk = csr.get("Tracking", "")

            # Sbírá Content/Br — pokud CSR nemá přímý Content,
            # hledá i v <Change> (Track Changes varianta B, např. u6085)
            direct_nodes = []
            change_nodes = []
            for e in csr:
                etag = _local_tag(e.tag)
                if etag in ("Content", "Br"):
                    direct_nodes.append(e)
                elif etag == "Change":
                    if e.get("ChangeType", "") == "DeletedText":
                        continue
                    for ce in e:
                        if _local_tag(ce.tag) in ("Content", "Br"):
                            change_nodes.append(ce)

            # Preferuj přímý Content; Change content jen když CSR je prázdný
            content_nodes = direct_nodes if direct_nodes else change_nodes

            for e in content_nodes:
                etag = _local_tag(e.tag)
                if etag == "Content":
                    text = e.text or ""
                    elements.append({
                        "type": "Content",
                        "text": text,
                        "len": len(text),
                        "ps": ps,
                        "cap": cap,
                        "pt": pt,
                        "bl": bl,
                        "fc": fc,
                        "cs": cs,
                        "trk": trk,
                    })
                elif etag == "Br":
                    elements.append({"type": "Br", "ps": ps})

    return elements


def extract_stories(unpacked_dir: str | Path) -> list[TextElement]:
    """Extrahuje textove elementy ze vsech Story souboru v rozbalenem IDML.

    Returns:
        list[TextElement]: Plochy seznam textovych elementu.
    """
    from services.idml_processor import list_stories

    stories = list_stories(unpacked_dir)
    all_elements = []

    for story_path in stories:
        story_id = story_path.stem  # "Story_u123"
        raw_elements = parse_story(story_path)

        content_idx = 0
        for raw in raw_elements:
            if raw["type"] == "Br":
                content_idx += 1  # Br vytváří mezeru v indexech → signál pro odstavcový break v exportu
                continue
            if raw["type"] != "Content":
                continue

            text = raw["text"].strip()
            if not text:
                content_idx += 1
                continue

            elem_id = f"{story_id}/{content_idx}"
            category = _classify_element(raw)

            all_elements.append(TextElement(
                id=elem_id,
                contents=text,
                story_id=story_id,
                paragraph_style=raw["ps"],
                category=category,
                fontSize=_safe_float(raw["pt"]),
            ))
            content_idx += 1

    logger.info(
        "Extracted %d text elements from %d stories",
        len(all_elements), len(stories),
    )
    return all_elements


def _classify_element(raw: dict) -> TextCategory | None:
    """Klasifikuje element podle IDML stylu."""
    cs = raw.get("cs", "").lower()
    ps = raw.get("ps", "").lower()
    cap = raw.get("cap", "")
    pt = _safe_float(raw.get("pt", ""))
    bl = _safe_float(raw.get("bl", ""))

    # Subtitle
    if cs == "subtitle" or "subtitle" in ps:
        return TextCategory.SUBTITLE

    # Heading (velke pismo)
    if pt and pt > 20:
        return TextCategory.HEADING

    # Lead/Perex (AllCaps nebo barevny)
    if cap == "AllCaps":
        return TextCategory.LEAD

    # Bullet marker (BaselineShift > 0 + barevny)
    fc = raw.get("fc", "")
    if bl and bl > 0 and fc and "Black" not in fc:
        return TextCategory.BULLET

    # Separator (zaporny BaselineShift)
    if bl and bl < 0:
        return TextCategory.SEPARATOR

    # Caption (maly text)
    if pt and pt < 8:
        return TextCategory.CAPTION

    # Body (default)
    if raw.get("len", 0) > 10:
        return TextCategory.BODY

    return None


def _local_tag(tag: str) -> str:
    """Odstrani namespace z XML tagu."""
    return tag.split("}")[-1] if "}" in tag else tag


def _style_name(full_name: str) -> str:
    """Extrahuje jmeno stylu z plneho IDML path (napr. 'ParagraphStyle/Body')."""
    return full_name.split("/")[-1] if "/" in full_name else full_name


def _safe_float(val) -> float | None:
    """Bezpecny prevod na float."""
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
