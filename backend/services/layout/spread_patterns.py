"""Knihovna spread patterns — abstraktní kompozice spreadů extrahované z NG šablon.

Každý pattern definuje sloty (text/image) s relativními pozicemi (0-1) vůči spreadu.
Patterns jsou parametrizované — fungují s libovolnými rozměry stránky.

Generováno z analýzy 15 IDML souborů květnového čísla NG 05/2026.
"""

import json
from pathlib import Path

from backend.models_layout import (
    Bounds, FrameType, SlotSpec, SpreadPattern, SpreadType, StyleProfile,
)

# NG spread = 2 stránky vedle sebe: 990×720 pt (2×495×720)
# Relativní pozice jsou vůči celému spreadu (0-1)
# Levá stránka: x 0.0–0.5, Pravá stránka: x 0.5–1.0

# --- Pomocné konstanty pro relativní pozice ---
# NG marginy v relativních souřadnicích (vůči spreadu 990×720)
LEFT_MARGIN = 57 / 990      # 0.0576
RIGHT_MARGIN = 48 / 990     # 0.0485
TOP_MARGIN = 75 / 720       # 0.1042
BOTTOM_MARGIN = 84 / 720    # 0.1167
# Stránkové hranice
PAGE_MID = 0.5              # Hranice levé/pravé stránky
# Bezpečná textová oblast (uvnitř marginů)
TEXT_LEFT = LEFT_MARGIN
TEXT_RIGHT = 1.0 - RIGHT_MARGIN
TEXT_TOP = TOP_MARGIN
TEXT_BOTTOM = 1.0 - BOTTOM_MARGIN
TEXT_WIDTH = TEXT_RIGHT - TEXT_LEFT
TEXT_HEIGHT = TEXT_BOTTOM - TEXT_TOP


def _build_patterns() -> list[SpreadPattern]:
    """Sestaví knihovnu spread patterns z dat NG analýzy."""

    patterns = []

    # =========================================================================
    # 1. OPENING — full-bleed fotka přes celý spread + overlay titulky
    # Typické: 1 hero_image (full spread), deck×3, caption, folio
    # Použití: první spread reportáže
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="opening_fullbleed",
        pattern_name="Opening — Full-Bleed",
        spread_type=SpreadType.OPENING,
        description="Opening spread reportáže: full-bleed fotka přes oba stránky, "
                    "overlay titulek + deck + byline na pravé stránce.",
        slots=[
            # Hero image — celý spread + bleed
            SlotSpec(
                slot_id="hero",
                slot_type=FrameType.HERO_IMAGE,
                rel_x=0.0, rel_y=0.0, rel_width=1.0, rel_height=1.0,
                required=True, allow_bleed=True,
            ),
            # Headline — overlay, pravá stránka, dolní třetina
            SlotSpec(
                slot_id="headline",
                slot_type=FrameType.HEADLINE,
                rel_x=0.52, rel_y=0.55, rel_width=0.40, rel_height=0.15,
                required=True, default_style="FEA_Head_1",
            ),
            # Deck — pod titulkem
            SlotSpec(
                slot_id="deck",
                slot_type=FrameType.DECK,
                rel_x=0.52, rel_y=0.72, rel_width=0.35, rel_height=0.08,
                required=True, default_style="FEA_Deck_1",
            ),
            # Byline — pod deckem
            SlotSpec(
                slot_id="byline",
                slot_type=FrameType.BYLINE,
                rel_x=0.52, rel_y=0.82, rel_width=0.35, rel_height=0.04,
                required=False, default_style="FEA_Byline_1",
            ),
            # Caption — levý dolní roh
            SlotSpec(
                slot_id="caption",
                slot_type=FrameType.CAPTION,
                rel_x=TEXT_LEFT, rel_y=0.90, rel_width=0.30, rel_height=0.05,
                required=False, default_style="ALL_Caption_Directional_Rev",
            ),
            # Folio — patička
            SlotSpec(
                slot_id="folio",
                slot_type=FrameType.FOLIO,
                rel_x=TEXT_LEFT, rel_y=0.96, rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer_Rev",
            ),
        ],
        min_images=1,
        max_images=1,
        min_text_chars=50,
        preferred_for=["opening"],
    ))

    # =========================================================================
    # 2. BIG PICTURE — full-bleed fotka + minimální text (caption)
    # Typické: 1 hero_image, 1 caption
    # Použití: vizuálně silné fotky uvnitř reportáže
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="big_picture",
        pattern_name="Big Picture",
        spread_type=SpreadType.BIG_PICTURE,
        description="Celostránková/celospreadová fotka s minimálním textem — "
                    "caption v dolním rohu.",
        slots=[
            SlotSpec(
                slot_id="hero",
                slot_type=FrameType.HERO_IMAGE,
                rel_x=0.0, rel_y=0.0, rel_width=1.0, rel_height=1.0,
                required=True, allow_bleed=True,
            ),
            SlotSpec(
                slot_id="caption",
                slot_type=FrameType.CAPTION,
                rel_x=0.55, rel_y=0.92, rel_width=0.35, rel_height=0.05,
                required=False, default_style="ALL_Caption_Directional_Rev",
            ),
        ],
        min_images=1,
        max_images=1,
        min_text_chars=0,
        preferred_for=["big_picture", "photo_dominant"],
    ))

    # =========================================================================
    # 3. BODY MIXED — text + 1-2 fotky, nejčastější typ (31% spreadů)
    # Typické: 4-7 text frames, 1-2 body images, caption
    # Dva sloupce textu na jedné stránce, fotka na druhé
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="body_mixed_2col",
        pattern_name="Body Mixed — 2 sloupce + fotka",
        spread_type=SpreadType.BODY_MIXED,
        description="Dva sloupce body textu na levé stránce, "
                    "jedna větší fotka na pravé stránce s caption.",
        slots=[
            # Body text — levá stránka, 2 sloupce (jeden TextFrame, InDesign dělí)
            SlotSpec(
                slot_id="body_text",
                slot_type=FrameType.BODY_TEXT,
                rel_x=TEXT_LEFT, rel_y=TEXT_TOP,
                rel_width=PAGE_MID - TEXT_LEFT - 0.02,
                rel_height=TEXT_HEIGHT,
                required=True, default_style="ALL_Body_Justified",
            ),
            # Image — pravá stránka, velká
            SlotSpec(
                slot_id="image_1",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=PAGE_MID + 0.02, rel_y=TEXT_TOP,
                rel_width=0.46 - RIGHT_MARGIN,
                rel_height=0.65,
                required=True,
            ),
            # Caption — pod fotkou
            SlotSpec(
                slot_id="caption_1",
                slot_type=FrameType.CAPTION,
                rel_x=PAGE_MID + 0.02, rel_y=0.78,
                rel_width=0.30, rel_height=0.05,
                required=True, default_style="ALL_Caption_Reg",
            ),
            # Deck/subhead — nad body textem
            SlotSpec(
                slot_id="deck",
                slot_type=FrameType.DECK,
                rel_x=TEXT_LEFT, rel_y=TEXT_TOP - 0.05,
                rel_width=0.35, rel_height=0.04,
                required=False, default_style="FEA_Deck_2",
            ),
            # Folio — levá patička
            SlotSpec(
                slot_id="folio_l",
                slot_type=FrameType.FOLIO,
                rel_x=TEXT_LEFT, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
            # Folio — pravá patička
            SlotSpec(
                slot_id="folio_r",
                slot_type=FrameType.FOLIO,
                rel_x=1.0 - RIGHT_MARGIN - 0.10, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
        ],
        min_images=1,
        max_images=2,
        min_text_chars=500,
        preferred_for=["body"],
    ))

    # =========================================================================
    # 4. BODY MIXED — varianta s 2 fotkami
    # Fotka nahoře přes celý spread + text dole ve 3 sloupcích
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="body_mixed_top_photo",
        pattern_name="Body Mixed — fotka nahoře + text dole",
        spread_type=SpreadType.BODY_MIXED,
        description="Větší fotka v horní polovině spreadu, "
                    "text ve 2-3 sloupcích dole + menší fotka.",
        slots=[
            # Hlavní fotka — horní polovina
            SlotSpec(
                slot_id="image_1",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=TEXT_LEFT, rel_y=TEXT_TOP,
                rel_width=TEXT_WIDTH, rel_height=0.42,
                required=True,
            ),
            # Caption k hlavní fotce
            SlotSpec(
                slot_id="caption_1",
                slot_type=FrameType.CAPTION,
                rel_x=TEXT_LEFT, rel_y=0.55,
                rel_width=0.30, rel_height=0.04,
                required=True, default_style="ALL_Caption_Reg",
            ),
            # Body text — spodní část, levá strana
            SlotSpec(
                slot_id="body_text",
                slot_type=FrameType.BODY_TEXT,
                rel_x=TEXT_LEFT, rel_y=0.60,
                rel_width=0.55, rel_height=0.28,
                required=True, default_style="ALL_Body_Justified",
            ),
            # Menší fotka — pravý dolní roh
            SlotSpec(
                slot_id="image_2",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=0.62, rel_y=0.60,
                rel_width=0.30, rel_height=0.28,
                required=False,
            ),
            # Caption k menší fotce
            SlotSpec(
                slot_id="caption_2",
                slot_type=FrameType.CAPTION,
                rel_x=0.62, rel_y=0.89,
                rel_width=0.25, rel_height=0.04,
                required=False, default_style="ALL_Caption_Reg",
            ),
            # Folio
            SlotSpec(
                slot_id="folio_l",
                slot_type=FrameType.FOLIO,
                rel_x=TEXT_LEFT, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
        ],
        min_images=1,
        max_images=2,
        min_text_chars=300,
        preferred_for=["body"],
    ))

    # =========================================================================
    # 5. BODY TEXT — text-heavy spread (3 sloupce, 1 malá fotka)
    # Typické: 5 text frames, 1 body image
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="body_text_3col",
        pattern_name="Body Text — 3 sloupce",
        spread_type=SpreadType.BODY_TEXT,
        description="Text-heavy spread: 3 sloupce textu přes celý spread, "
                    "1 menší fotka v horním rohu.",
        slots=[
            # Body text — přes celý spread (InDesign 3-column)
            SlotSpec(
                slot_id="body_text",
                slot_type=FrameType.BODY_TEXT,
                rel_x=TEXT_LEFT, rel_y=TEXT_TOP,
                rel_width=TEXT_WIDTH, rel_height=TEXT_HEIGHT,
                required=True, default_style="ALL_Body_Justified",
            ),
            # Malá fotka — pravý horní roh (inset)
            SlotSpec(
                slot_id="image_1",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=0.68, rel_y=TEXT_TOP,
                rel_width=0.25, rel_height=0.30,
                required=False,
            ),
            # Caption
            SlotSpec(
                slot_id="caption_1",
                slot_type=FrameType.CAPTION,
                rel_x=0.68, rel_y=TEXT_TOP + 0.31,
                rel_width=0.20, rel_height=0.04,
                required=False, default_style="ALL_Caption_Reg",
            ),
            # Folio — levá
            SlotSpec(
                slot_id="folio_l",
                slot_type=FrameType.FOLIO,
                rel_x=TEXT_LEFT, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
            # Folio — pravá
            SlotSpec(
                slot_id="folio_r",
                slot_type=FrameType.FOLIO,
                rel_x=1.0 - RIGHT_MARGIN - 0.10, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
        ],
        min_images=0,
        max_images=1,
        min_text_chars=1500,
        preferred_for=["body", "body_text"],
    ))

    # =========================================================================
    # 6. PHOTO GRID — 3-6 fotek v mřížce + krátké texty
    # Typické: 3+ body images, caption ke každé, sidebar
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="photo_grid_3x2",
        pattern_name="Photo Grid — 3×2",
        spread_type=SpreadType.PHOTO_GRID,
        description="Mřížka 6 fotek (3×2) s captions, "
                    "volitelný sidebar s textem.",
        slots=[
            # Řada 1 — 3 fotky
            SlotSpec(
                slot_id="image_1",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=TEXT_LEFT, rel_y=TEXT_TOP,
                rel_width=0.28, rel_height=0.32,
                required=True,
            ),
            SlotSpec(
                slot_id="image_2",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=0.35, rel_y=TEXT_TOP,
                rel_width=0.28, rel_height=0.32,
                required=True,
            ),
            SlotSpec(
                slot_id="image_3",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=0.66, rel_y=TEXT_TOP,
                rel_width=0.28, rel_height=0.32,
                required=True,
            ),
            # Řada 2 — 3 fotky
            SlotSpec(
                slot_id="image_4",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=TEXT_LEFT, rel_y=0.48,
                rel_width=0.28, rel_height=0.32,
                required=False,
            ),
            SlotSpec(
                slot_id="image_5",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=0.35, rel_y=0.48,
                rel_width=0.28, rel_height=0.32,
                required=False,
            ),
            SlotSpec(
                slot_id="image_6",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=0.66, rel_y=0.48,
                rel_width=0.28, rel_height=0.32,
                required=False,
            ),
            # Captions — pod fotkami
            SlotSpec(
                slot_id="caption_row1",
                slot_type=FrameType.CAPTION,
                rel_x=TEXT_LEFT, rel_y=0.43,
                rel_width=0.88, rel_height=0.04,
                required=True, default_style="ALL_Caption_Reg",
            ),
            SlotSpec(
                slot_id="caption_row2",
                slot_type=FrameType.CAPTION,
                rel_x=TEXT_LEFT, rel_y=0.81,
                rel_width=0.88, rel_height=0.04,
                required=False, default_style="ALL_Caption_Reg",
            ),
            # Sidebar / text blok dole
            SlotSpec(
                slot_id="sidebar",
                slot_type=FrameType.SIDEBAR,
                rel_x=TEXT_LEFT, rel_y=0.86,
                rel_width=0.40, rel_height=0.08,
                required=False, default_style="ALL_Body_Justified",
            ),
            # Folio
            SlotSpec(
                slot_id="folio_l",
                slot_type=FrameType.FOLIO,
                rel_x=TEXT_LEFT, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
        ],
        min_images=3,
        max_images=6,
        min_text_chars=100,
        preferred_for=["photo_grid"],
    ))

    # =========================================================================
    # 7. PHOTO DOMINANT — 1 velká fotka přes 60%+ spreadu
    # Typické: MF layout — 1 hero + mnoho menších body images
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="photo_dominant",
        pattern_name="Photo Dominant",
        spread_type=SpreadType.PHOTO_DOMINANT,
        description="Jedna dominantní fotka přes většinu spreadu, "
                    "volitelně menší fotky kolem + caption/byline.",
        slots=[
            SlotSpec(
                slot_id="hero",
                slot_type=FrameType.HERO_IMAGE,
                rel_x=0.0, rel_y=0.0, rel_width=0.65, rel_height=1.0,
                required=True, allow_bleed=True,
            ),
            # Text oblast — pravá strana
            SlotSpec(
                slot_id="body_text",
                slot_type=FrameType.BODY_TEXT,
                rel_x=0.67, rel_y=TEXT_TOP,
                rel_width=0.28, rel_height=0.50,
                required=False, default_style="ALL_Body_Justified",
            ),
            SlotSpec(
                slot_id="headline",
                slot_type=FrameType.HEADLINE,
                rel_x=0.67, rel_y=TEXT_TOP - 0.05,
                rel_width=0.28, rel_height=0.08,
                required=False, default_style="INT_Hed_Ac",
            ),
            SlotSpec(
                slot_id="caption",
                slot_type=FrameType.CAPTION,
                rel_x=0.67, rel_y=0.68,
                rel_width=0.28, rel_height=0.05,
                required=False, default_style="ALL_Caption_Reg",
            ),
            SlotSpec(
                slot_id="byline",
                slot_type=FrameType.BYLINE,
                rel_x=0.67, rel_y=0.75,
                rel_width=0.20, rel_height=0.04,
                required=False, default_style="FEA_Byline_1",
            ),
            # Folio
            SlotSpec(
                slot_id="folio",
                slot_type=FrameType.FOLIO,
                rel_x=1.0 - RIGHT_MARGIN - 0.10, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
        ],
        min_images=1,
        max_images=1,
        min_text_chars=100,
        preferred_for=["photo_dominant"],
    ))

    # =========================================================================
    # 8. CLOSING — závěrečný spread (bio, credits, menší fotky)
    # Typické: body text, sidebar (bio), 1-2 body images, caption, credit
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="closing",
        pattern_name="Closing",
        spread_type=SpreadType.CLOSING,
        description="Závěrečný spread reportáže: zbývající text, "
                    "bio/credits sidebar, 1-2 menší fotky.",
        slots=[
            # Body text — levá stránka
            SlotSpec(
                slot_id="body_text",
                slot_type=FrameType.BODY_TEXT,
                rel_x=TEXT_LEFT, rel_y=TEXT_TOP,
                rel_width=PAGE_MID - TEXT_LEFT - 0.02,
                rel_height=0.55,
                required=True, default_style="ALL_Body_Justified",
            ),
            # Image — pravá stránka nahoře
            SlotSpec(
                slot_id="image_1",
                slot_type=FrameType.BODY_IMAGE,
                rel_x=PAGE_MID + 0.02, rel_y=TEXT_TOP,
                rel_width=0.35, rel_height=0.40,
                required=False,
            ),
            # Caption
            SlotSpec(
                slot_id="caption_1",
                slot_type=FrameType.CAPTION,
                rel_x=PAGE_MID + 0.02, rel_y=0.53,
                rel_width=0.30, rel_height=0.04,
                required=False, default_style="ALL_Caption_Reg",
            ),
            # Sidebar — bio / grant note
            SlotSpec(
                slot_id="sidebar",
                slot_type=FrameType.SIDEBAR,
                rel_x=PAGE_MID + 0.02, rel_y=0.60,
                rel_width=0.35, rel_height=0.25,
                required=False, default_style="ALL_Bio_Reg_Rule",
            ),
            # Credit
            SlotSpec(
                slot_id="credit",
                slot_type=FrameType.CREDIT,
                rel_x=TEXT_LEFT, rel_y=0.70,
                rel_width=0.40, rel_height=0.10,
                required=False, default_style="ALL_Credit",
            ),
            # Folio
            SlotSpec(
                slot_id="folio_l",
                slot_type=FrameType.FOLIO,
                rel_x=TEXT_LEFT, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
            SlotSpec(
                slot_id="folio_r",
                slot_type=FrameType.FOLIO,
                rel_x=1.0 - RIGHT_MARGIN - 0.10, rel_y=0.96,
                rel_width=0.10, rel_height=0.03,
                required=False, default_style="FEA_Footer",
            ),
        ],
        min_images=0,
        max_images=2,
        min_text_chars=200,
        preferred_for=["closing"],
    ))

    # =========================================================================
    # 9. COVER — obálka s full-bleed fotkou a overlay titulky
    # Typické: 1 hero image, 5-6 cover lines, logo pozice
    # =========================================================================
    patterns.append(SpreadPattern(
        pattern_id="cover",
        pattern_name="Cover",
        spread_type=SpreadType.COVER,
        description="Obálka: full-bleed fotka, logo nahoře, "
                    "cover lines v dolní třetině.",
        slots=[
            SlotSpec(
                slot_id="hero",
                slot_type=FrameType.HERO_IMAGE,
                rel_x=0.0, rel_y=0.0, rel_width=1.0, rel_height=1.0,
                required=True, allow_bleed=True,
            ),
            # Logo — horní střed (single page, takže x vůči 1-page spreadu)
            SlotSpec(
                slot_id="logo",
                slot_type=FrameType.LOGO,
                rel_x=0.15, rel_y=0.02, rel_width=0.70, rel_height=0.10,
                required=True,
            ),
            # Hlavní cover line
            SlotSpec(
                slot_id="cover_line_main",
                slot_type=FrameType.COVER_LINE,
                rel_x=0.10, rel_y=0.70, rel_width=0.80, rel_height=0.10,
                required=True, default_style="COV_title",
            ),
            # Cover dek
            SlotSpec(
                slot_id="cover_dek",
                slot_type=FrameType.DECK,
                rel_x=0.10, rel_y=0.81, rel_width=0.80, rel_height=0.05,
                required=False, default_style="COV_dek",
            ),
            # Sekundární cover lines
            SlotSpec(
                slot_id="cover_line_2",
                slot_type=FrameType.COVER_LINE,
                rel_x=0.10, rel_y=0.87, rel_width=0.35, rel_height=0.04,
                required=False, default_style="COV_text",
            ),
            SlotSpec(
                slot_id="cover_line_3",
                slot_type=FrameType.COVER_LINE,
                rel_x=0.55, rel_y=0.87, rel_width=0.35, rel_height=0.04,
                required=False, default_style="COV_text",
            ),
            # Folio — číslo/měsíc
            SlotSpec(
                slot_id="folio",
                slot_type=FrameType.FOLIO,
                rel_x=0.10, rel_y=0.93, rel_width=0.30, rel_height=0.03,
                required=False, default_style="COV_month/vol",
            ),
        ],
        min_images=1,
        max_images=1,
        min_text_chars=20,
        preferred_for=["cover"],
    ))

    return patterns


# --- Pattern Registry ---

_PATTERNS: list[SpreadPattern] | None = None


def get_all_patterns() -> list[SpreadPattern]:
    """Vrátí všechny dostupné spread patterns."""
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = _build_patterns()
    return _PATTERNS


def get_pattern(pattern_id: str) -> SpreadPattern | None:
    """Vrátí pattern podle ID."""
    for p in get_all_patterns():
        if p.pattern_id == pattern_id:
            return p
    return None


def get_patterns_for_type(spread_type: SpreadType) -> list[SpreadPattern]:
    """Vrátí všechny patterns pro daný typ spreadu."""
    return [p for p in get_all_patterns() if p.spread_type == spread_type]


def get_patterns_for_role(role: str) -> list[SpreadPattern]:
    """Vrátí patterns vhodné pro danou roli (opening, body, closing...)."""
    return [p for p in get_all_patterns() if role in p.preferred_for]


def instantiate_pattern(
    pattern: SpreadPattern,
    spread_width: float = 990.0,
    spread_height: float = 720.0,
) -> list[dict]:
    """Převede relativní sloty patternu na absolutní Bounds.

    Returns:
        List of dicts s klíči: slot_id, slot_type, bounds (Bounds), ...
    """
    result = []
    for slot in pattern.slots:
        bounds = Bounds(
            x=round(slot.rel_x * spread_width, 2),
            y=round(slot.rel_y * spread_height, 2),
            width=round(slot.rel_width * spread_width, 2),
            height=round(slot.rel_height * spread_height, 2),
        )
        result.append({
            "slot_id": slot.slot_id,
            "slot_type": slot.slot_type.value,
            "bounds": bounds,
            "required": slot.required,
            "default_style": slot.default_style,
            "allow_bleed": slot.allow_bleed,
        })
    return result


def export_patterns_json(output_path: str | Path | None = None) -> dict:
    """Exportuje celou knihovnu patterns jako JSON-serializovatelný dict.

    Pokud output_path zadáno, uloží do souboru.
    """
    patterns = get_all_patterns()
    data = {
        "version": "1.0",
        "source": "NG 05/2026 — 15 IDML analýz",
        "page_dimensions": {
            "width_pt": 495,
            "height_pt": 720,
            "spread_width_pt": 990,
            "spread_height_pt": 720,
        },
        "patterns": [p.model_dump() for p in patterns],
        "pattern_count": len(patterns),
        "spread_types_covered": sorted(set(p.spread_type.value for p in patterns)),
    }

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return data
