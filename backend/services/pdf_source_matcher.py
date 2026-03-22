"""Matcher: sparovani PDF odstavcu s IDML elementy.

PDF (RTT) obsahuje aktualizovany anglicky text. IDML muze mit starsi verzi.
Matcher porovna texty a ulozi diff do notes pro manualni review.
NIKDY nepise primo do contents — predchazi se tak chybnemu prepsani.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import logging
from difflib import SequenceMatcher

from models import TextElement
from services.pdf_source_parser import PdfParseResult, PdfParagraph

logger = logging.getLogger(__name__)


def match_pdf_to_idml(
    elements: list[TextElement],
    pdf_result: PdfParseResult,
) -> dict:
    """Sparuje PDF odstavce s IDML elementy a aktualizuje contents.

    Strategie: spojí IDML elementy do story-bloků, porovná s PDF odstavci
    pomocí textové similarity. Kde se text liší, aktualizuje IDML.

    Returns:
        dict s match statistikami
    """
    if not pdf_result.paragraphs:
        return {"matched": 0, "updated": 0, "total_elements": len(elements)}

    # Spoj IDML elementy do story-bloku
    story_blocks = _build_story_blocks(elements)

    # Spoj PDF odstavce do větších bloků odpovídajících story-blokům
    pdf_paragraphs = pdf_result.paragraphs

    # Match story-bloky s PDF odstavci
    matches = _match_blocks(story_blocks, pdf_paragraphs)

    # Aplikuj aktualizace
    stats = _apply_updates(elements, matches, story_blocks, pdf_paragraphs)

    logger.info(
        "PDF→IDML matching: %d stories matched, %d elements updated out of %d",
        stats["matched"], stats["updated"], stats["total_elements"],
    )
    return stats


def _build_story_blocks(elements: list[TextElement]) -> list[dict]:
    """Seskupi elementy podle story_id do bloku."""
    blocks = {}
    for el in elements:
        sid = el.story_id or "unknown"
        if sid not in blocks:
            blocks[sid] = {
                "story_id": sid,
                "elements": [],
                "full_text": "",
            }
        blocks[sid]["elements"].append(el)

    for block in blocks.values():
        block["full_text"] = " ".join(
            el.contents for el in block["elements"]
        )

    return list(blocks.values())


def _match_blocks(
    story_blocks: list[dict],
    pdf_paragraphs: list[PdfParagraph],
) -> list[tuple[int, list[int], float]]:
    """Sparuje story-bloky s PDF odstavci.

    Každý story-blok může matchnout 1 nebo více po sobě jdoucích PDF odstavců.

    Returns:
        list of (story_block_idx, [pdf_paragraph_indices], similarity_score)
    """
    matches = []
    used_pdf = set()

    for bi, block in enumerate(story_blocks):
        block_text = block["full_text"]
        if len(block_text) < 10:
            continue

        best_score = 0
        best_range = []

        # Zkus matchnout s jednotlivymi odstavci i se skupinami
        for pi in range(len(pdf_paragraphs)):
            if pi in used_pdf:
                continue

            # Zkus 1-5 po sobe jdoucich odstavcu
            for span in range(1, min(6, len(pdf_paragraphs) - pi + 1)):
                indices = list(range(pi, pi + span))
                if any(idx in used_pdf for idx in indices):
                    break

                combined_pdf = " ".join(
                    pdf_paragraphs[idx].text for idx in indices
                )

                score = _similarity(block_text, combined_pdf)

                if score > best_score:
                    best_score = score
                    best_range = indices

        if best_score >= 0.5:
            matches.append((bi, best_range, best_score))
            used_pdf.update(best_range)

    return matches


def _similarity(text_a: str, text_b: str) -> float:
    """Vypocita similaritu mezi dvema texty.

    Kombinuje anchor words (cisla, vlastni jmena) a SequenceMatcher.
    """
    if not text_a or not text_b:
        return 0.0

    # Normalizuj
    a = _normalize(text_a)
    b = _normalize(text_b)

    # Anchor score — sdilena specificka slova (cisla, vlastni jmena 4+ znaku)
    anchors_a = set(_extract_anchors(a))
    anchors_b = set(_extract_anchors(b))
    if anchors_a and anchors_b:
        anchor_overlap = len(anchors_a & anchors_b) / max(len(anchors_a), len(anchors_b))
    else:
        anchor_overlap = 0.0

    # Delkovy pomer
    len_ratio = min(len(a), len(b)) / max(len(a), len(b)) if max(len(a), len(b)) > 0 else 0

    # SequenceMatcher na prvnich 500 znacich (rychlost)
    seq_score = SequenceMatcher(None, a[:500], b[:500]).ratio()

    # Vazeny soucet
    return anchor_overlap * 0.3 + len_ratio * 0.2 + seq_score * 0.5


def _normalize(text: str) -> str:
    """Normalizuje text pro porovnani."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_anchors(text: str) -> list[str]:
    """Extrahuje anchor tokeny — cisla a vlastni jmena."""
    # Cisla
    numbers = re.findall(r"\b\d[\d,.]+\b", text)
    # Slova zacinajici velkym pismenem (4+ znaku) — v lowercase verzi hledame original
    words = re.findall(r"\b[a-z]{4,}\b", text)
    # Vybíráme méně běžná slova jako anchory
    return numbers + [w for w in words if len(w) >= 6]


def _apply_updates(
    elements: list[TextElement],
    matches: list[tuple[int, list[int], float]],
    story_blocks: list[dict],
    pdf_paragraphs: list[PdfParagraph],
) -> dict:
    """Ulozi PDF diff do notes pro manualni review.

    NIKDY nepise primo do contents — predchazi chybnemu prepsani.
    Vsechny zmeny jdou do notes s prefixem [PDF UPDATE].
    """
    updated = 0
    matched = len(matches)
    changes = []

    for block_idx, pdf_indices, score in matches:
        block = story_blocks[block_idx]
        block_elements = block["elements"]
        pdf_text = " ".join(pdf_paragraphs[pi].text for pi in pdf_indices)

        old_block = " ".join(el.contents for el in block_elements)
        if not _texts_differ(old_block, pdf_text):
            continue  # texty jsou stejne, nic nemen

        # Uloz PDF text do notes prvniho elementu pro manualni review
        first_el = block_elements[0]
        note_prefix = f"\n[PDF UPDATE] (similarity: {score:.0%}, {len(pdf_text)} znaku)"
        first_el.notes = (first_el.notes or "") + f"{note_prefix}: {pdf_text}"
        changes.append({
            "element_id": first_el.id,
            "story_id": block["story_id"],
            "similarity": round(score, 2),
            "old": old_block[:80],
            "new": pdf_text[:80],
        })
        updated += 1

    return {
        "matched": matched,
        "updated": updated,
        "total_elements": len(elements),
        "total_paragraphs": len(pdf_paragraphs),
        "changes_preview": changes[:20],
    }


def _texts_differ(old: str, new: str) -> bool:
    """Zjisti zda se texty vyznamne lisi (ne jen whitespace)."""
    a = re.sub(r"\s+", " ", old).strip()
    b = re.sub(r"\s+", " ", new).strip()
    return a != b


