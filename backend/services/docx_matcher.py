"""Matching engine: Páruje DOCX české sekce s IDML anglickými stories.

Strategie:
1. IDML elementy seskupí po story_id → EN story bloky
2. DOCX sekce (segmentované podle stránkových markerů) → CZ bloky
3. Párování pomocí:
   a) Anchor keywords (vlastní jména, čísla, zkratky v obou jazycích)
   b) Typ sekce (legenda→body/caption, sloupek→sidebar, citát→lead/quote)
   c) Sekvenční pozice v rámci stránky
4. Spárovaný CZ text se přiřadí na první element story (nebo distribuuje)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import logging
from dataclasses import dataclass, field

from models import TextElement, TextStatus
from services.docx_parser import DocxSection, DocxParseResult, get_all_filtered_sections

logger = logging.getLogger(__name__)


@dataclass
class StoryBlock:
    """Seskupené IDML elementy jedné story."""
    story_id: str
    elements: list[TextElement]
    full_text: str  # spojený text všech elementů
    categories: set[str] = field(default_factory=set)

    @property
    def main_category(self) -> str | None:
        """Nejčastější kategorie v story."""
        if not self.categories:
            return None
        # Preferuj konkrétní kategorie před None
        cats = [c for c in self.categories if c]
        return cats[0] if cats else None


@dataclass
class MatchResult:
    """Výsledek matchingu."""
    matched_stories: int
    total_stories: int
    total_elements: int
    elements_with_czech: int
    matches: list[dict]  # [{story_id, section_type, page, confidence, preview_en, preview_cz}]


def _group_stories(elements: list[TextElement]) -> list[StoryBlock]:
    """Seskupí elementy podle story_id."""
    stories_map: dict[str, list[TextElement]] = {}
    for el in elements:
        sid = el.story_id or "unknown"
        stories_map.setdefault(sid, []).append(el)

    blocks = []
    for sid, elems in stories_map.items():
        full_text = " ".join(e.contents for e in elems)
        cats = {e.category for e in elems if e.category}
        blocks.append(StoryBlock(
            story_id=sid,
            elements=elems,
            full_text=full_text,
            categories=cats,
        ))
    return blocks


def _extract_anchors(text: str) -> set[str]:
    """Extrahuje anchor tokeny z textu — vlastní jména, čísla, zkratky.
    Tyto tokeny jsou jazykově nezávislé a pomohou párovat EN↔CZ.
    """
    anchors = set()

    # Čísla (roky, procenta, stránky)
    for m in re.finditer(r'\b\d{2,}\b', text):
        anchors.add(m.group())

    # Vlastní jména — slova začínající velkým písmenem uprostřed věty
    # (2+ písmena, ne na začátku věty)
    for m in re.finditer(r'(?<=[a-záčďéěíňóřšťúůýž]\s)([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽA-z][a-záčďéěíňóřšťúůýžA-Z]{2,})', text):
        anchors.add(m.group().lower())

    # Zkratky (2+ velká písmena)
    for m in re.finditer(r'\b[A-Z]{2,}\b', text):
        anchors.add(m.group())

    # Specifické anchor patterny pro NGM Memory special
    for name in ["EP", "Miller", "Alzheimer", "PTSD", "MCI", "Loftus", "Ebbinghaus",
                  "Kandel", "Squire", "hippocampus", "hipokampus", "amygdala"]:
        if name.lower() in text.lower():
            anchors.add(name.lower())

    return anchors


def _section_type_matches_category(section_type: str, categories: set[str]) -> bool:
    """Kontroluje kompatibilitu typu DOCX sekce s IDML kategorií."""
    if section_type == "legenda":
        # Legendy matchují body, caption, heading
        return bool(categories & {"body", "caption", "heading", "lead", None, ""})
    elif section_type == "sloupek":
        # Sloupky matchují sidebar texty
        return True  # sidebar elementy nemají specifickou kategorii
    elif section_type == "citát":
        # Citáty matchují lead, quote
        return bool(categories & {"lead", "subtitle", "heading", None, ""})
    return True  # body matchuje vše


def _compute_similarity(story: StoryBlock, section: DocxSection) -> float:
    """Spočítá podobnost mezi EN story a CZ sekcí. Vrací 0.0 - 1.0."""
    score = 0.0

    # 1. Anchor overlap (40% váhy)
    en_anchors = _extract_anchors(story.full_text)
    cz_anchors = _extract_anchors(section.full_text)
    if en_anchors and cz_anchors:
        overlap = en_anchors & cz_anchors
        union = en_anchors | cz_anchors
        anchor_score = len(overlap) / max(len(union), 1)
        score += anchor_score * 0.4

    # 2. Délková podobnost (20% váhy) — EN a CZ by měly mít podobnou délku
    en_len = len(story.full_text)
    cz_len = len(section.full_text)
    if en_len > 0 and cz_len > 0:
        ratio = min(en_len, cz_len) / max(en_len, cz_len)
        # Čeština bývá o 10-30% delší než angličtina
        adjusted_ratio = min(1.0, ratio * 1.15)
        score += adjusted_ratio * 0.2

    # 3. Typ sekce vs kategorie (20% váhy)
    if _section_type_matches_category(section.section_type, story.categories):
        score += 0.2

    # 4. Počet odstavců vs elementů (20% váhy)
    n_paras = len(section.paragraphs)
    n_elems = len(story.elements)
    if n_paras > 0 and n_elems > 0:
        count_ratio = min(n_paras, n_elems) / max(n_paras, n_elems)
        score += count_ratio * 0.2

    return score


def match_docx_to_idml(
    elements: list[TextElement],
    docx_result: DocxParseResult,
    page_min: int | None = None,
    page_max: int | None = None,
    min_confidence: float = 0.15,
) -> MatchResult:
    """Hlavní matching funkce. Páruje DOCX sekce s IDML stories.

    Strategie: greedy matching — pro každou IDML story najde nejlepší DOCX sekci.
    Každá sekce může být přiřazena max jedné story (1:1).

    Pokud page_min/page_max nejsou zadány, pouzije vsechny sekce z DOCX.
    """
    stories = _group_stories(elements)

    # Bez explicitniho rozsahu pouzij vsechny sekce
    if page_min is not None and page_max is not None:
        sections = get_all_filtered_sections(docx_result, page_min, page_max)
    else:
        sections = docx_result.sections
    # Filtruj prazdne sekce
    sections = [s for s in sections if s.paragraphs]

    p_min = min((s.page_start for s in sections), default=0)
    p_max = max((s.page_end for s in sections), default=0)
    logger.info("Matching: %d stories vs %d DOCX sections (str. %d-%d)",
                len(stories), len(sections), p_min, p_max)

    # Spočítat similarity matici
    scores: list[tuple[float, int, int]] = []  # (score, story_idx, section_idx)
    for si, story in enumerate(stories):
        for sj, section in enumerate(sections):
            score = _compute_similarity(story, section)
            if score >= min_confidence:
                scores.append((score, si, sj))

    # Greedy matching — od nejvyššího score
    scores.sort(reverse=True)
    matched_stories_idx: set[int] = set()
    matched_sections_idx: set[int] = set()
    matches: list[dict] = []

    for score, si, sj in scores:
        if si in matched_stories_idx or sj in matched_sections_idx:
            continue

        story = stories[si]
        section = sections[sj]

        # Přiřadit CZ text na elementy story
        _assign_czech_to_elements(story, section)

        matched_stories_idx.add(si)
        matched_sections_idx.add(sj)
        matches.append({
            "story_id": story.story_id,
            "section_type": section.section_type,
            "page": section.page_start,
            "confidence": round(score, 3),
            "n_elements": len(story.elements),
            "n_paragraphs": len(section.paragraphs),
            "preview_en": story.full_text[:80],
            "preview_cz": section.full_text[:80],
        })

    # Statistiky
    elements_with_czech = sum(1 for el in elements if el.czech)

    result = MatchResult(
        matched_stories=len(matches),
        total_stories=len(stories),
        total_elements=len(elements),
        elements_with_czech=elements_with_czech,
        matches=matches,
    )

    logger.info("Matching hotovo: %d/%d stories matched, %d/%d elements s CZ textem",
                result.matched_stories, result.total_stories,
                result.elements_with_czech, result.total_elements)

    return result


def _assign_czech_to_elements(story: StoryBlock, section: DocxSection):
    """Přiřadí CZ text ze sekce na elementy story.

    Strategie:
    - 1 element → celý CZ text sekce
    - N elementů, M odstavců kde N==M → 1:1
    - N elementů, M odstavců kde N!=M → první element dostane vše,
      ostatní dostanou poznámku že CZ je na prvním elementu
    """
    cz_text = section.full_text
    n_elems = len(story.elements)
    n_paras = len(section.paragraphs)

    if n_elems == 1:
        # Jednoduchý případ — celý CZ text na jediný element
        story.elements[0].czech = cz_text
        story.elements[0].status = TextStatus.OVERIT
        story.elements[0].notes = f"DOCX match (str. {section.page_start}, {section.section_type})"

    elif n_elems == n_paras:
        # 1:1 mapování — každý odstavec na jeden element
        for elem, para in zip(story.elements, section.paragraphs):
            elem.czech = para
            elem.status = TextStatus.OVERIT
            elem.notes = f"DOCX match 1:1 (str. {section.page_start})"

    else:
        # Různý počet — CZ text na první element, ostatní dostanou odkaz
        story.elements[0].czech = cz_text
        story.elements[0].status = TextStatus.OVERIT
        story.elements[0].notes = (
            f"DOCX match (str. {section.page_start}, {section.section_type}) — "
            f"celý CZ blok ({n_paras} odst.) pro {n_elems} EN elementů"
        )
        for elem in story.elements[1:]:
            elem.notes = f"CZ viz první element story {story.story_id}"
