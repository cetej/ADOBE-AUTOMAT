"""Parsování strukturovaného textu článku pro Layout Planner.

Funkce:
- parse_article_text() — rozpozná sekce (headline, deck, byline, body, captions, pull quotes)
- estimate_text_space() — odhad prostorových nároků textu v layoutu

Podporované formáty vstupu:
- Plain text s konvencí: `# HEADLINE:`, `# DECK:`, `# BYLINE:`, `# CAPTION:`, `# PULLQUOTE:`
- Nestrukturovaný text — první řádek = headline, zbytek = body

Generováno pro Session 4 Layout Generator.
"""

import logging
import re
from math import ceil
from typing import Optional

from models_layout import ArticleText, StyleProfile, TextEstimate

logger = logging.getLogger(__name__)

# NG typografie — konstanty pro odhad prostoru
# Grosvenor Book 9pt, leading 12pt, 2 sloupce na stránku
CHARS_PER_LINE = 40          # ~40 znaků na řádek v NG sloupci
LINES_PER_COLUMN = 55        # ~55 řádků v jednom sloupci (uvnitř marginů)
CHARS_PER_COLUMN = CHARS_PER_LINE * LINES_PER_COLUMN  # ~2200
COLUMNS_PER_PAGE = 2         # NG standard body = 2 sloupce
CHARS_PER_PAGE = CHARS_PER_COLUMN * COLUMNS_PER_PAGE   # ~4400

# Regex patterny pro detekci sekcí
_SECTION_RE = re.compile(
    r"^#\s*(HEADLINE|DECK|BYLINE|CAPTION|PULLQUOTE|PULL_QUOTE|SIDEBAR|CREDIT)\s*:\s*",
    re.IGNORECASE | re.MULTILINE,
)
_BYLINE_RE = re.compile(
    r"^(By\s+.+|Foto:\s*.+|Text:\s*.+|Photographs?\s+by\s+.+|Written\s+by\s+.+)$",
    re.IGNORECASE | re.MULTILINE,
)
# Pull quote kandidáti: krátké věty s uvozovkami nebo silnými výrazy
_QUOTE_CHARS = '""„"‚''«»'
_PULL_QUOTE_MIN = 30
_PULL_QUOTE_MAX = 150


def parse_article_text(raw_text: str) -> ArticleText:
    """Parsuje text článku do strukturovaných sekcí.

    Podporuje dva režimy:
    1. Strukturovaný: řádky začínající `# HEADLINE:`, `# DECK:` atd.
    2. Nestrukturovaný: první řádek = headline, "By ..." = byline, zbytek = body
    """
    if not raw_text or not raw_text.strip():
        return ArticleText()

    raw_text = raw_text.strip()

    # Zkusit strukturovaný formát
    if _SECTION_RE.search(raw_text):
        return _parse_structured(raw_text)

    # Fallback: nestrukturovaný text
    return _parse_unstructured(raw_text)


def _parse_structured(text: str) -> ArticleText:
    """Parsuje strukturovaný text s explicitními sekcemi."""
    headline = ""
    deck = ""
    byline = ""
    body_parts: list[str] = []
    captions: list[str] = []
    pull_quotes: list[str] = []

    current_section = "body"  # Default je body
    current_lines: list[str] = []

    for line in text.split("\n"):
        # Zkontrolovat section header
        match = _SECTION_RE.match(line)
        if match:
            # Uložit předchozí sekci
            _flush_section(current_section, current_lines,
                           body_parts, captions, pull_quotes)
            current_lines = []

            section_type = match.group(1).upper()
            rest = line[match.end():].strip()

            if section_type == "HEADLINE":
                current_section = "headline"
                if rest:
                    headline = rest
                    current_section = "body"  # Pokud inline, pokračuj body
                    continue
            elif section_type == "DECK":
                current_section = "deck"
                if rest:
                    deck = rest
                    current_section = "body"
                    continue
            elif section_type in ("BYLINE",):
                current_section = "byline"
                if rest:
                    byline = rest
                    current_section = "body"
                    continue
            elif section_type == "CAPTION":
                current_section = "caption"
                if rest:
                    captions.append(rest)
                    current_section = "body"
                    continue
            elif section_type in ("PULLQUOTE", "PULL_QUOTE"):
                current_section = "pullquote"
                if rest:
                    pull_quotes.append(rest)
                    current_section = "body"
                    continue
            else:
                current_section = "body"
        else:
            current_lines.append(line)

    # Poslední sekce
    _flush_section(current_section, current_lines,
                   body_parts, captions, pull_quotes)

    # Pokud headline/deck/byline nebyl v section headerech, ale v current_lines
    if current_section == "headline" and not headline:
        headline = "\n".join(current_lines).strip()
    elif current_section == "deck" and not deck:
        deck = "\n".join(current_lines).strip()
    elif current_section == "byline" and not byline:
        byline = "\n".join(current_lines).strip()

    # Filtruj prázdné paragrafy
    body_paragraphs = [p.strip() for p in body_parts if p.strip()]

    # Auto-detekce pull quotes z body textu
    if not pull_quotes:
        pull_quotes = _detect_pull_quotes(body_paragraphs)

    return _build_article_text(headline, deck, byline, body_paragraphs,
                                captions, pull_quotes)


def _flush_section(
    section: str,
    lines: list[str],
    body_parts: list[str],
    captions: list[str],
    pull_quotes: list[str],
) -> None:
    """Uloží obsah aktuální sekce do příslušného seznamu."""
    content = "\n".join(lines).strip()
    if not content:
        return

    if section == "body":
        # Rozdělit na paragrafy podle prázdných řádků
        paragraphs = re.split(r"\n\s*\n", content)
        body_parts.extend(p.strip() for p in paragraphs if p.strip())
    elif section == "caption":
        captions.append(content)
    elif section == "pullquote":
        pull_quotes.append(content)


def _parse_unstructured(text: str) -> ArticleText:
    """Parsuje nestrukturovaný text — heuristiky pro detekci sekcí."""
    lines = text.split("\n")
    headline = ""
    deck = ""
    byline = ""
    body_lines: list[str] = []

    state = "start"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if state == "start" and headline:
                state = "after_headline"
            elif state == "body":
                body_lines.append("")  # Oddělovač paragrafů
            continue

        if state == "start":
            # První neprázdný řádek = headline
            headline = stripped
            state = "after_headline"
        elif state == "after_headline":
            # Byline detekce
            if _BYLINE_RE.match(stripped):
                byline = stripped
                state = "body"
            # Krátký řádek po headline = deck
            elif len(stripped) < 200 and not deck:
                deck = stripped
                state = "after_deck"
            else:
                body_lines.append(stripped)
                state = "body"
        elif state == "after_deck":
            if _BYLINE_RE.match(stripped):
                byline = stripped
                state = "body"
            else:
                body_lines.append(stripped)
                state = "body"
        elif state == "body":
            body_lines.append(stripped)

    # Rozdělit body na paragrafy
    body_text = "\n".join(body_lines)
    paragraphs = re.split(r"\n\s*\n", body_text)
    body_paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Auto-detekce pull quotes
    pull_quotes = _detect_pull_quotes(body_paragraphs)

    return _build_article_text(headline, deck, byline, body_paragraphs,
                                [], pull_quotes)


def _detect_pull_quotes(paragraphs: list[str], max_quotes: int = 3) -> list[str]:
    """Auto-detekce pull quote kandidátů z body textu.

    Hledá: krátké věty (30-150 znaků) s uvozovkami nebo silnými výrazy.
    """
    candidates: list[tuple[float, str]] = []

    for para in paragraphs:
        # Rozdělit na věty
        sentences = re.split(r'(?<=[.!?])\s+', para)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < _PULL_QUOTE_MIN or len(sent) > _PULL_QUOTE_MAX:
                continue

            score = 0.0
            # Obsahuje uvozovky → pravděpodobně citát
            if any(c in sent for c in _QUOTE_CHARS):
                score += 2.0
            # Krátká, výrazná věta
            if len(sent) < 100:
                score += 0.5
            # Začíná velkým písmenem (ne jako pokračování)
            if sent[0].isupper():
                score += 0.3
            # Obsahuje emotivní slova
            emotivni = ["nikdy", "vždy", "poprvé", "poslední", "jediný",
                        "never", "always", "first", "last", "only",
                        "incredible", "extraordinary", "neuvěřitelné"]
            if any(w in sent.lower() for w in emotivni):
                score += 1.0

            if score >= 1.0:
                candidates.append((score, sent))

    # Seřadit podle score, vrátit top N
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidates[:max_quotes]]


def _build_article_text(
    headline: str,
    deck: str,
    byline: str,
    body_paragraphs: list[str],
    captions: list[str],
    pull_quotes: list[str],
) -> ArticleText:
    """Sestaví ArticleText s vypočítanými statistikami."""
    total_body = sum(len(p) for p in body_paragraphs)
    total = (
        len(headline) + len(deck) + len(byline)
        + total_body
        + sum(len(c) for c in captions)
        + sum(len(q) for q in pull_quotes)
    )

    return ArticleText(
        headline=headline,
        deck=deck,
        byline=byline,
        body_paragraphs=body_paragraphs,
        captions=captions,
        pull_quotes=pull_quotes,
        total_body_chars=total_body,
        total_chars=total,
    )


def estimate_text_space(
    text: ArticleText,
    profile: Optional[StyleProfile] = None,
) -> TextEstimate:
    """Odhadne prostorové nároky textu v layoutu.

    Vrací odhad počtu spreadů potřebných pro body text.
    NG standard: ~2200 znaků/sloupec, 2 sloupce/stránka = ~4400 znaků/stránka.
    """
    body_chars = text.total_body_chars
    if body_chars == 0:
        return TextEstimate(total_body_chars=0, estimated_total_spreads=1)

    # Odhad body stránek
    body_pages = body_chars / CHARS_PER_PAGE

    # Pull quotes zabírají místo (~1/4 sloupce)
    pq_pages = len(text.pull_quotes) * 0.25

    # Captions — minimální prostor (~50 znaků/caption)
    cap_pages = len(text.captions) * 50 / CHARS_PER_PAGE

    total_pages = body_pages + pq_pages + cap_pages

    # Spreads: 2 stránky/spread + 1 opening + 1 closing (oba jsou celé spready)
    body_spreads = ceil(total_pages / 2)
    total_spreads = body_spreads + 2  # +opening +closing

    return TextEstimate(
        total_body_chars=body_chars,
        chars_per_column=CHARS_PER_COLUMN,
        chars_per_page=CHARS_PER_PAGE,
        estimated_body_pages=round(total_pages, 1),
        estimated_total_spreads=max(3, total_spreads),  # Min 3: opening + 1 body + closing
        has_pull_quotes=len(text.pull_quotes) > 0,
        has_captions=len(text.captions) > 0,
    )
