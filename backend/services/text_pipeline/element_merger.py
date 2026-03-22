"""Element merger — spojuje IDML TextElements do souvislého textu pro pipeline.

Workflow:
  1. merge() — spojí elementy do jednoho textu s ID značkami
  2. Pipeline zpracuje text jako celek
  3. split_back() — parsuje zpracovaný text zpět na elementy

Pořadí: titulek nahoře, body text uprostřed, popisky dole.
ID značky: <!--[elem-ID]--> text <!--[/elem-ID]-->
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Kategorie elementů a jejich řazení do sekcí
_TITLE_CATEGORIES = {"title", "heading"}
_BODY_CATEGORIES = {"body", "lead", "main_text", "subtitle", "bullet"}
_CAPTION_CATEGORIES = {"caption", "annotations", "labels", "info_boxes"}
# Vše ostatní (geografie, legendy, credits...) — řadí se za body


class ElementMerger:
    """Spojuje a rozděluje TextElements pro pipeline zpracování."""

    # Regex pro ID značky — <!--[elem-ID]--> ... <!--[/elem-ID]-->
    TAG_PATTERN = re.compile(
        r'<!--\[elem-(.*?)\]-->\s*(.*?)\s*<!--\[/elem-\1\]-->',
        re.DOTALL
    )

    @staticmethod
    def merge(elements: list, include_original: bool = False) -> str:
        """Spojí elementy do jednoho textu s ID značkami.

        Pořadí:
          1. Titulky (title, heading)
          2. Body text (body, lead, main_text, subtitle, bullet)
          3. Ostatní (geografie, legendy, ...)
          4. Popisky (caption, annotations, labels)

        Args:
            elements: Seznam TextElement objektů (musí mít .czech)
            include_original: True = vložit i originál (pro completeness check)

        Returns:
            Spojený text s ID značkami
        """
        # Rozřadit elementy do sekcí
        titles = []
        body = []
        other = []
        captions = []

        for elem in elements:
            text = elem.czech if elem.czech else ""
            if not text.strip():
                continue

            cat = elem.category.value if elem.category else ""

            if cat in _TITLE_CATEGORIES:
                titles.append(elem)
            elif cat in _BODY_CATEGORIES:
                body.append(elem)
            elif cat in _CAPTION_CATEGORIES:
                captions.append(elem)
            else:
                other.append(elem)

        # Sestavit text
        parts = []

        if titles:
            parts.append("# TITULKY\n")
            for elem in titles:
                parts.append(f'<!--[elem-{elem.id}]-->{elem.czech}<!--[/elem-{elem.id}]-->\n')

        if body:
            parts.append("\n# TEXT ČLÁNKU\n")
            for elem in body:
                parts.append(f'<!--[elem-{elem.id}]-->{elem.czech}<!--[/elem-{elem.id}]-->\n')

        if other:
            parts.append("\n# DOPLŇKOVÝ TEXT\n")
            for elem in other:
                parts.append(f'<!--[elem-{elem.id}]-->{elem.czech}<!--[/elem-{elem.id}]-->\n')

        if captions:
            parts.append("\n# POPISKY\n")
            for elem in captions:
                parts.append(f'<!--[elem-{elem.id}]-->{elem.czech}<!--[/elem-{elem.id}]-->\n')

        merged = '\n'.join(parts)

        # Pokud include_original, připoj originál pro completeness check
        if include_original:
            orig_parts = ["\n\n---\n\n# ORIGINÁLNÍ TEXT (ANGLIČTINA)\n"]
            for elem in elements:
                if elem.contents and elem.contents.strip():
                    orig_parts.append(f'<!--[orig-{elem.id}]-->{elem.contents}<!--[/orig-{elem.id}]-->\n')
            merged += '\n'.join(orig_parts)

        return merged

    @staticmethod
    def merge_original(elements: list) -> str:
        """Spojí originální (EN) texty elementů do jednoho textu.

        Pro Phase 2 (completeness check) — porovnání s překladem.
        """
        parts = []
        for elem in elements:
            if elem.contents and elem.contents.strip():
                parts.append(elem.contents)
        return '\n\n'.join(parts)

    @classmethod
    def split_back(cls, processed_text: str, elements: list) -> dict:
        """Parsuje zpracovaný text zpět na elementy.

        Hledá ID značky <!--[elem-ID]--> v textu a extrahuje obsah.

        Args:
            processed_text: Text zpracovaný pipeline (se značkami)
            elements: Původní seznam elementů (pro fallback)

        Returns:
            Dict {element_id: processed_czech_text}
        """
        result = {}

        # Najdi všechny ID značky
        for match in cls.TAG_PATTERN.finditer(processed_text):
            elem_id = match.group(1)
            text = match.group(2).strip()
            if text:
                result[elem_id] = text

        # Loguj pokrytí
        original_ids = {e.id for e in elements if e.czech}
        found_ids = set(result.keys())
        missing = original_ids - found_ids
        if missing:
            logger.warning(
                f"ElementMerger.split_back: {len(missing)}/{len(original_ids)} "
                f"elementů nenalezeno ve zpracovaném textu"
            )

        return result

    @staticmethod
    def count_processable(elements: list) -> int:
        """Spočítá elementy s českým textem (k zpracování pipeline)."""
        return sum(1 for e in elements if e.czech and e.czech.strip())

    @staticmethod
    def estimate_tokens(elements: list) -> int:
        """Odhadne počet tokenů pro spojený text (~4 chars/token)."""
        total_chars = sum(len(e.czech) for e in elements if e.czech)
        return total_chars // 4
