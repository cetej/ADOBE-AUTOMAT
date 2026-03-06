"""Auto-kategorizace textovych elementu podle nazvu vrstvy a vlastnosti textu."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import logging
from models import TextElement, TextCategory

logger = logging.getLogger(__name__)

# Mapovani nazvu vrstev na kategorie
LAYER_CATEGORY_MAP = {
    "T-Water": TextCategory.OCEANS_SEAS,
    "T-Ocean": TextCategory.OCEANS_SEAS,
    "T-Sea": TextCategory.OCEANS_SEAS,
    "T-Continents": TextCategory.CONTINENTS,
    "T-Countries": TextCategory.COUNTRIES_FULL,
    "T-Modern Countries": TextCategory.COUNTRIES_FULL,
    "T-Countries Abbrev": TextCategory.COUNTRIES_ABBREV,
    "T-Regions": TextCategory.REGIONS,
    "T-Cities": TextCategory.CITIES,
    "T-Other Cities": TextCategory.CITIES,
    "T-Capital Cities": TextCategory.CITIES,
    "T-Settlements": TextCategory.SETTLEMENTS,
    "T-Rivers": TextCategory.WATER_BODIES,
    "T-Lakes": TextCategory.WATER_BODIES,
    "T-Mountains": TextCategory.LANDFORMS,
    "T-Landforms": TextCategory.LANDFORMS,
    "T-Places": TextCategory.PLACES,
    "T-Labels": TextCategory.LABELS,
    "T-Annotations": TextCategory.ANNOTATIONS,
    "T-Title": TextCategory.TITLE,
    "T-Info": TextCategory.INFO_BOXES,
    "Map Key": TextCategory.LEGEND,
    "Legend": TextCategory.LEGEND,
    "T-Scale": TextCategory.SCALE,
    "T-Timeline": TextCategory.TIMELINE,
    "T-Credits": TextCategory.CREDITS,
    "T-Dates": TextCategory.DATES,
    "T-Events": TextCategory.EVENTS,
    "T-Periods": TextCategory.PERIODS,
}

# Regex vzory pro heuristickou kategorizaci
HEURISTIC_PATTERNS = [
    (re.compile(r"^\d+\s*(mi|km|miles|kilometers)", re.I), TextCategory.SCALE),
    (re.compile(r"^(ca?\.\s*)?\d{3,4}\s*(B\.?C\.?|A\.?D\.?|n\.\s*l\.|př)", re.I), TextCategory.DATES),
    (re.compile(r"^(Atlantic|Pacific|Indian|Arctic|Mediterranean|Black|Caspian|Red)\b", re.I), TextCategory.OCEANS_SEAS),
    (re.compile(r"(ocean|sea|gulf|strait|bay)\b", re.I), TextCategory.OCEANS_SEAS),
    (re.compile(r"(river|lake|creek)\b", re.I), TextCategory.WATER_BODIES),
    (re.compile(r"(mountain|mount|mt\.|range|peak|volcano)\b", re.I), TextCategory.LANDFORMS),
    (re.compile(r"^(AFRICA|EUROPE|ASIA|NORTH AMERICA|SOUTH AMERICA|AUSTRALIA|ANTARCTICA)$"), TextCategory.CONTINENTS),
]


def categorize_element(elem: TextElement) -> TextCategory | None:
    """Urcit kategorii jednoho elementu."""
    # 1. Podle nazvu vrstvy (presna shoda)
    if elem.layer_name and elem.layer_name in LAYER_CATEGORY_MAP:
        return LAYER_CATEGORY_MAP[elem.layer_name]

    # 2. Podle prefixu nazvu vrstvy (castecna shoda)
    if elem.layer_name:
        for prefix, cat in LAYER_CATEGORY_MAP.items():
            if elem.layer_name.startswith(prefix):
                return cat

    # 3. Heuristiky podle obsahu
    text = elem.contents.replace("\r", " ").strip()
    for pattern, cat in HEURISTIC_PATTERNS:
        if pattern.search(text):
            return cat

    # 4. Podle velikosti pisma (velke = titulky, male = anotace)
    if elem.fontSize:
        if elem.fontSize >= 14:
            return TextCategory.TITLE
        elif elem.fontSize <= 5:
            return TextCategory.ANNOTATIONS

    # 5. CAPS = zeme nebo kontinenty
    if text.isupper() and len(text) > 2:
        return TextCategory.COUNTRIES_FULL

    return None


def categorize_elements(elements: list[TextElement]) -> int:
    """Auto-kategorizuje vsechny elementy. Vraci pocet kategorizovanych."""
    categorized = 0
    for elem in elements:
        if elem.category is None:
            cat = categorize_element(elem)
            if cat:
                elem.category = cat
                categorized += 1

    logger.info("Auto-categorized %d/%d elements", categorized, len(elements))
    return categorized
