"""Parser zdrojoveho anglickeho PDF (RTT/backgrounder).

Extrahuje odstavce clanku z PDF, preskoci backgrounder/anotace.
NGM RTT format:
  - Stranky 1-N: backgrounder (format "21: explanation text")
  - Stranky N+: clanek s cislovanymi radky (format "21 article text")
Rozliseni: backgrounder radky maji "cislo:" (s dvojteckou),
clankove radky maji "cislo text" (bez dvojtecky).
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PdfParagraph:
    """Jeden odstavec extrahovaný z PDF."""
    text: str
    line_start: int
    line_end: int


@dataclass
class PdfParseResult:
    """Vysledek parsovani PDF."""
    title: str = ""
    subtitle: str = ""
    author: str = ""
    photographer: str = ""
    paragraphs: list[PdfParagraph] = field(default_factory=list)
    backgrounder_pages: int = 0
    backgrounder_text: str = ""
    total_pages: int = 0


# Clankovy radek: "12 text" (cislo + mezera + text, BEZ dvojtecky za cislem)
_ARTICLE_LINE_RE = re.compile(r"^(\d{1,3})\s+(?!:)(.+)")
# Prazdny clankovy radek: jen cislo
_EMPTY_LINE_RE = re.compile(r"^(\d{1,3})$")
# Backgrounder radek: "12: explanation" (cislo + dvojtecka)
_BG_LINE_RE = re.compile(r"^\d{1,3}:\s")
# Metricka konverze — samostatny radek (cislo + jednotka, nebo jen cislo s carkou)
_METRIC_RE = re.compile(
    r"^(\d[\d,]*\s*(kilometers?|meters?|miles?|feet|inches?|pounds?|kilograms?|"
    r"gallons?|liters?|litres?|acres?|hectares?|square\s+\w+)"
    r"|[\d,]{4,})$",  # samotne cislo s carkou, napr. "930,000"
    re.IGNORECASE,
)
# Page break marker
_PAGE_BREAK_RE = re.compile(r"^Page\s+break$", re.IGNORECASE)
# Header opakujici se na kazde strance (napr. "May 2026: Mohenjo Daro")
_HEADER_RE = re.compile(r"^\w+\s+\d{4}:\s")


def parse_source_pdf(pdf_path: str | Path) -> PdfParseResult:
    """Parsuje zdrojovy anglicky PDF a extrahuje odstavce clanku."""
    import pdfplumber

    pdf_path = Path(pdf_path)
    pdf = pdfplumber.open(pdf_path)
    result = PdfParseResult(total_pages=len(pdf.pages))

    article_start = _find_article_start(pdf)
    result.backgrounder_pages = article_start

    # Backgrounder
    if article_start > 0:
        bg_parts = []
        for page in pdf.pages[:article_start]:
            text = page.extract_text() or ""
            if text.strip():
                bg_parts.append(text.strip())
        result.backgrounder_text = "\n\n".join(bg_parts)

    if article_start >= len(pdf.pages):
        logger.warning("Nenalezen text clanku v PDF %s", pdf_path.name)
        return result

    # Extrahuj cislovane radky clanku
    numbered_lines = _extract_numbered_lines(pdf, article_start)

    if not numbered_lines:
        logger.warning("Zadne cislovane radky v PDF %s", pdf_path.name)
        return result

    # Metadata
    _extract_metadata(numbered_lines, result)

    # Odstavce (skip metadata radky na zacatku)
    content_lines = _skip_metadata_lines(numbered_lines)
    result.paragraphs = _build_paragraphs(content_lines)

    logger.info(
        "PDF parsed: %d pages, backgrounder=%d pages, %d paragraphs, title='%s'",
        result.total_pages, result.backgrounder_pages,
        len(result.paragraphs), result.title,
    )
    return result


def _find_article_start(pdf) -> int:
    """Najde cislo stranky kde zacina text clanku.

    Heuristic: strana s 5+ radky ve formatu "cislo text" (BEZ dvojtecky).
    Backgrounder ma format "cislo: vysvetleni".
    """
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        lines = text.split("\n")

        article_lines = 0
        bg_lines = 0
        for line in lines:
            line = line.strip()
            if _ARTICLE_LINE_RE.match(line) or _EMPTY_LINE_RE.match(line):
                article_lines += 1
            if _BG_LINE_RE.match(line):
                bg_lines += 1

        # Strana s prevazne clankovymi radky (ne backgrounder)
        if article_lines >= 5 and article_lines > bg_lines:
            return i

    return len(pdf.pages)


def _extract_numbered_lines(pdf, start_page: int) -> list[tuple[int, str]]:
    """Extrahuje cislovane radky clanku z PDF.

    Returns: [(line_number, text), ...] serazene podle cisla radku.
    """
    lines = {}  # line_num -> accumulated text
    prev_num = 0

    for page in pdf.pages[start_page:]:
        text = page.extract_text() or ""
        page_lines = text.split("\n")

        current_num = None
        current_parts = []

        for raw_line in page_lines:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            # Preskoc Page break
            if _PAGE_BREAK_RE.match(raw_line):
                continue

            # Preskoc metricke konverze
            if _METRIC_RE.match(raw_line):
                continue

            # Preskoc opakovane hlavicky (napr. "May 2026: Mohenjo Daro")
            if _HEADER_RE.match(raw_line):
                continue

            # Prazdny cislovany radek (jen cislo)
            m_empty = _EMPTY_LINE_RE.match(raw_line)
            if m_empty:
                num = int(m_empty.group(1))
                if _is_valid_line_num(num, prev_num):
                    if current_num is not None:
                        _store_line(lines, current_num, current_parts)
                    current_num = num
                    current_parts = []
                    prev_num = num
                continue

            # Clankovy radek (cislo + text)
            m = _ARTICLE_LINE_RE.match(raw_line)
            if m:
                num = int(m.group(1))
                content = m.group(2).strip()
                if _is_valid_line_num(num, prev_num):
                    if current_num is not None:
                        _store_line(lines, current_num, current_parts)
                    current_num = num
                    current_parts = [content] if content else []
                    prev_num = num
                    continue

            # Necislovany radek — pokracovani (zalomeni v PDF)
            if current_num is not None:
                current_parts.append(raw_line)

        # Uloz posledni radek stranky
        if current_num is not None:
            _store_line(lines, current_num, current_parts)

    return sorted(lines.items())


def _is_valid_line_num(num: int, prev_num: int) -> bool:
    """Overi ze cislo radku je rozumne (sekvencni, ne rok ci jiny kontext)."""
    if num > 500:
        return False
    if prev_num == 0:
        return num < 20  # prvni radek by mel byt nizky
    # Povolena mezera +/- 5 od predchoziho (prazdne radky)
    return abs(num - prev_num) < 10 or num == prev_num + 1


def _store_line(lines: dict, num: int, parts: list[str]):
    """Ulozi text k danemu cislu radku. Spoji rozdělená slova."""
    text = " ".join(p for p in parts if p)
    # Spoj slova rozdelena na konci radku pomlckou (napr. "mois- turized" -> "moisturized")
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    # Ale zachovej em-dash: slovo—slovo (Unicode em-dash neni zasazeno)
    # a zachovej legitimni pomlcky (napr. "wind-whipped")
    if num in lines:
        lines[num] = lines[num] + " " + text if text else lines[num]
    else:
        lines[num] = text


def _extract_metadata(numbered_lines: list[tuple[int, str]], result: PdfParseResult):
    """Extrahuje metadata z prvnich radku (titulek, autor, fotograf)."""
    for num, text in numbered_lines[:15]:
        if not text:
            continue
        upper = text.upper().strip()
        if upper.startswith("WORDS BY "):
            result.author = text[len("WORDS BY "):].strip()
        elif upper.startswith("PHOTOGRAPHS BY "):
            result.photographer = text[len("PHOTOGRAPHS BY "):].strip()
        elif upper.startswith("PHOTOS BY "):
            result.photographer = text[len("PHOTOS BY "):].strip()
        elif text.isupper() and len(text) > 10 and num <= 10:
            if not result.title:
                result.title = text


def _skip_metadata_lines(numbered_lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Preskoci metadata radky na zacatku (titulek, podtitulek, autor, fotograf).

    Clanek zacina prvnim odstavcem za WORDS BY / PHOTOGRAPHS BY.
    """
    skip_until = 0
    for num, text in numbered_lines[:15]:
        upper = (text or "").upper()
        if "WORDS BY" in upper or "PHOTOGRAPHS BY" in upper or "PHOTOS BY" in upper:
            skip_until = num

    if skip_until:
        return [(n, t) for n, t in numbered_lines if n > skip_until]
    return numbered_lines


# Redakcni anotace v hranatych zavorkach
_ANNOTATION_RE = re.compile(
    r"\[(?:(?:GRAPHIC|page|pages)\s+)?(?:page|pages)?\s*[\d\s\-–]+\]\s*"  # [page 47], [GRAPHIC pages 50 - 53]
    r"|\[(?:PULL\s+QUOTE|CAPTIONS?|opener|photo\s+credit|VIDEO|GRAPHIC)\]\s*",
    re.IGNORECASE,
)


def _join_parts(parts: list[str]) -> str:
    """Spoji casti odstavce. Dehyphenuje a vycisti redakcni anotace."""
    text = " ".join(parts)
    # "mois- turized" -> "moisturized"
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    # Odstran redakcni anotace [page X], [PULL QUOTE] atd.
    text = _ANNOTATION_RE.sub("", text)
    return text.strip()


def _build_paragraphs(numbered_lines: list[tuple[int, str]]) -> list[PdfParagraph]:
    """Spoji cislovane radky do odstavcu.

    Prazdny radek = konec odstavce. Filtruje metadata-like texty.
    """
    paragraphs = []
    current_parts = []
    current_start = None

    for num, text in numbered_lines:
        if not text:
            # Prazdny radek = konec odstavce
            if current_parts:
                paragraphs.append(PdfParagraph(
                    text=_join_parts(current_parts),
                    line_start=current_start,
                    line_end=num - 1,
                ))
                current_parts = []
                current_start = None
        else:
            if current_start is None:
                current_start = num
            current_parts.append(text)

    # Posledni odstavec
    if current_parts and current_start is not None:
        paragraphs.append(PdfParagraph(
            text=_join_parts(current_parts),
            line_start=current_start,
            line_end=numbered_lines[-1][0],
        ))

    # Filtruj velmi krátké odstavce (metadata, credity apod.)
    # a odstavce zacinajici na [credit], -END- apod.
    filtered = []
    for p in paragraphs:
        if p.text.startswith("[credit]") or p.text.strip() == "-END-":
            continue
        filtered.append(p)

    return filtered
