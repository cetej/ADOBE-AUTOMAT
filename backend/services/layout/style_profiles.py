"""Typografické profily extrahované z NG IDML šablon.

Dva hardcoded profily + podpora custom profilů (Style Transfer):
- NG Feature — pro velké reportáže (FEA_* styly, Marden headlines)
- NG Short — pro frontmatter / medium features (INT_* styly, Grosvenor headlines)
- Custom — importované z libovolného IDML přes template_analyzer

Profily obsahují IDML paragraph a character style definice pro:
headline, deck, body, caption, byline, folio, credit, pull_quote.

Generováno z analýzy 15 IDML souborů květnového čísla NG 05/2026.
"""

import json
import logging
from pathlib import Path

from models_layout import StyleInfo, StyleProfile

logger = logging.getLogger(__name__)

# Adresář pro uložení custom profilů (JSON)
CUSTOM_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "templates" / "custom_profiles"
CUSTOM_PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _build_profiles() -> list[StyleProfile]:
    """Sestaví typografické profily z dat NG analýzy."""

    profiles = []

    # =========================================================================
    # NG FEATURE — velké reportáže (Bees, Aral, S Sudan, Fecal Archive...)
    # Headline: Marden, Earle
    # Body: Grosvenor Book 9/12
    # Deck: Geograph Edit Bold
    # Caption: Geograph Edit 8/9.25
    # Folio: Grosvenor Book Medium 6pt, tracking 300
    # =========================================================================
    profiles.append(StyleProfile(
        profile_id="ng_feature",
        profile_name="NG Feature",
        description="Typografický profil pro velké reportáže National Geographic. "
                    "Marden/Earle headlines, Grosvenor Book body, Geograph Edit captions.",
        # NG standard page
        page_width=495,
        page_height=720,
        margin_top=75,
        margin_bottom=84,
        margin_left=57,
        margin_right=48,
        column_count=12,
        column_gutter=24,

        headline_styles=[
            StyleInfo(
                style_name="FEA_Head_1",
                font_family="Marden",
                font_style="Book",
                point_size=38,
                leading=32,
            ),
            StyleInfo(
                style_name="FEA_Head_2",
                font_family="Marden",
                font_style="Bold",
                point_size=28,
                leading=24,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="FEA_Head_3",
                font_family="Earle",
                font_style="Book",
                point_size=30,
                leading=27,
            ),
            StyleInfo(
                style_name="FEA_Head_4",
                font_family="Earle",
                font_style="Book",
                point_size=27,
                leading=24,
                capitalization="AllCaps",
            ),
        ],

        deck_styles=[
            StyleInfo(
                style_name="FEA_Deck_1",
                font_family="Geograph Edit",
                font_style="Bold",
                point_size=11,
                leading=12,
            ),
            StyleInfo(
                style_name="FEA_Deck_2",
                font_family="Geograph Edit",
                font_style="Bold",
                point_size=8,
                leading=13,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="FEA_Deck_3",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=8.5,
                leading=12,
                capitalization="AllCaps",
            ),
            # Callout (pull-quote variant)
            StyleInfo(
                style_name="FEA_Callout_1",
                font_family="Marden",
                font_style="Bold",
                point_size=14,
                leading=12,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="FEA_Callout_2",
                font_family="Earle",
                font_style="Bold",
                point_size=18,
                leading=15,
            ),
        ],

        body_styles=[
            StyleInfo(
                style_name="ALL_Body_Justified",
                font_family="Grosvenor Book",
                point_size=9,
                leading=12,
            ),
            StyleInfo(
                style_name="ALL_Body_Justified_Rev",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=9,
                leading=12,
                fill_color="Color/Paper",
            ),
            StyleInfo(
                style_name="ALL_Body_Fl",
                font_family="Grosvenor Book",
                point_size=9,
                leading=12,
            ),
            StyleInfo(
                style_name="ALL_Body_DCap",
                font_family="Grosvenor Book",
                point_size=9,
                leading=12,
                # Drop cap character: Turnpike Regular 8.75pt, tracking 300
            ),
        ],

        caption_styles=[
            StyleInfo(
                style_name="ALL_Caption_Reg",
                font_family="Geograph Edit",
                point_size=8,
                leading=9.25,
            ),
            StyleInfo(
                style_name="ALL_Caption_Med",
                font_family="Geograph Edit",
                font_style="Medium",
                point_size=8,
                leading=9.25,
            ),
            StyleInfo(
                style_name="ALL_Caption_Bold",
                font_family="Geograph Edit",
                font_style="Bold",
                point_size=8,
                leading=9.25,
            ),
            StyleInfo(
                style_name="ALL_Caption_Directional",
                font_family="Grosvenor Book",
                font_style="Regular Italic",
                point_size=7,
                leading=9.25,
            ),
            StyleInfo(
                style_name="ALL_Caption_Directional_Rev",
                font_family="Grosvenor Book",
                font_style="Medium Italic",
                point_size=7,
                leading=9.25,
                fill_color="Color/Paper",
            ),
            StyleInfo(
                style_name="ALL_Credit",
                font_family="Geograph Edit",
                point_size=4.75,
                leading=6,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="ALL_Credit_Rev",
                font_family="Geograph Edit",
                font_style="Medium",
                point_size=4.75,
                leading=6,
                capitalization="AllCaps",
                fill_color="Color/Paper",
            ),
        ],

        byline_styles=[
            StyleInfo(
                style_name="FEA_Byline_1",
                font_family="Geograph Edit",
                point_size=7,
                leading=18,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="FEA_Byline_2",
                font_family="Geograph Edit",
                font_style="Bold",
                point_size=7,
                leading=18,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="ALL_Bio_Reg_Rule",
                font_family="Geograph Edit",
                point_size=7,
                leading=9,
            ),
        ],

        folio_styles=[
            StyleInfo(
                style_name="FEA_Footer",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=6,
                tracking=300,
                leading=11,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="FEA_Footer_Rev",
                font_family="Grosvenor Book",
                font_style="Semibold",
                point_size=6,
                tracking=300,
                leading=11,
                capitalization="AllCaps",
                fill_color="Color/Paper",
            ),
        ],
    ))

    # =========================================================================
    # NG SHORT — frontmatter, medium features, interstitials
    # Headline: Grosvenor Book (AllCaps), Marden (pro BOB)
    # Body: Grosvenor Book 9/12 (sdílený s Feature)
    # Deck: Geograph Edit Medium 8/12
    # Caption: Geograph Edit 8/9.25 + Grosvenor Book varianty
    # Folio: Grosvenor Book Medium 6pt, tracking 300
    # =========================================================================
    profiles.append(StyleProfile(
        profile_id="ng_short",
        profile_name="NG Short",
        description="Typografický profil pro frontmatter, medium features a interstitials. "
                    "Grosvenor Book headlines (AllCaps), Geograph Edit deck/captions.",
        page_width=495,
        page_height=720,
        margin_top=75,
        margin_bottom=84,
        margin_left=57,
        margin_right=48,
        column_count=12,
        column_gutter=24,

        headline_styles=[
            StyleInfo(
                style_name="INT_Hed_Ac",
                font_family="Grosvenor Book",
                point_size=20,
                tracking=100,
                leading=23.3,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="INT_Hed_Sc",
                font_family="Grosvenor Book",
                point_size=11,
                tracking=100,
                leading=17,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="INT_Section_Hed",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=8.5,
                tracking=215,
                leading=11,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="INT_Gallery_Hed",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=10.5,
                tracking=170,
                leading=11,
                capitalization="AllCaps",
            ),
            # Back pages — special headline
            StyleInfo(
                style_name="BOB_Hed_1",
                font_family="Marden",
                font_style="Very Condensed Light",
                point_size=70,
                leading=45.5,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="BOB_Hed_2",
                font_family="Geograph",
                font_style="Black",
                point_size=9,
                leading=9.25,
            ),
        ],

        deck_styles=[
            StyleInfo(
                style_name="INT_Dek_1",
                font_family="Geograph Edit",
                font_style="Medium",
                point_size=8,
                tracking=50,
                leading=12,
            ),
            StyleInfo(
                style_name="INT_Section_Dek",
                font_family="Grosvenor Book",
                font_style="Medium Italic",
                point_size=5.5,
                tracking=200,
                leading=11,
                capitalization="AllCaps",
            ),
        ],

        body_styles=[
            # Sdílené s Feature
            StyleInfo(
                style_name="ALL_Body_Justified",
                font_family="Grosvenor Book",
                point_size=9,
                leading=12,
            ),
            StyleInfo(
                style_name="ALL_Body_Fl",
                font_family="Grosvenor Book",
                point_size=9,
                leading=12,
            ),
            # Contrib text
            StyleInfo(
                style_name="INT_Contrib_NGtext",
                font_family="Geograph Edit",
                point_size=8.5,
                leading=10,
            ),
            # TOC text
            StyleInfo(
                style_name="INT_TC_Text",
                font_family="Geograph Edit",
                font_style="Medium",
                point_size=7.75,
                leading=9.5,
                fill_color="Color/Paper",
            ),
        ],

        caption_styles=[
            # Sdílené
            StyleInfo(
                style_name="ALL_Caption_Reg",
                font_family="Geograph Edit",
                point_size=8,
                leading=9.25,
            ),
            StyleInfo(
                style_name="ALL_Caption_Directional",
                font_family="Grosvenor Book",
                font_style="Regular Italic",
                point_size=7,
                leading=9.25,
            ),
            # INT-specific
            StyleInfo(
                style_name="INT_Caption_hed 1",
                font_family="Grosvenor Book",
                font_style="Semibold",
                point_size=6,
                tracking=200,
                leading=9.25,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="INT_Caption_Gros",
                font_family="Grosvenor Book",
                point_size=8,
                tracking=75,
                leading=9.5,
            ),
            StyleInfo(
                style_name="ALL_Credit",
                font_family="Geograph Edit",
                point_size=4.75,
                leading=6,
                capitalization="AllCaps",
            ),
        ],

        byline_styles=[
            StyleInfo(
                style_name="INT_Byline",
                font_family="Grosvenor Book",
                font_style="Regular Italic",
                point_size=8,
                leading=11,
            ),
            StyleInfo(
                style_name="INT_Byline_Rev",
                font_family="Grosvenor Book",
                font_style="Medium Italic",
                point_size=8,
                leading=11,
                fill_color="Color/Paper",
            ),
            StyleInfo(
                style_name="ALL_Bio_Reg_Rule",
                font_family="Geograph Edit",
                point_size=7,
                leading=9,
            ),
        ],

        folio_styles=[
            StyleInfo(
                style_name="INT_footer",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=6,
                tracking=300,
                leading=11,
                capitalization="AllCaps",
            ),
            StyleInfo(
                style_name="INT_footer_rev",
                font_family="Grosvenor Book",
                font_style="Semibold",
                point_size=6,
                tracking=300,
                leading=11,
                capitalization="AllCaps",
                fill_color="Color/Paper",
            ),
            StyleInfo(
                style_name="INT_Page_Label",
                font_family="Grosvenor Book",
                font_style="Medium",
                point_size=6,
                tracking=300,
                leading=11,
                capitalization="AllCaps",
            ),
        ],
    ))

    return profiles


# --- Profile Registry ---

_PROFILES: list[StyleProfile] | None = None
_CUSTOM_PROFILES: dict[str, StyleProfile] = {}


def _load_custom_profiles():
    """Načte custom profily z JSON souborů v data/templates/custom_profiles/."""
    global _CUSTOM_PROFILES
    _CUSTOM_PROFILES = {}
    if not CUSTOM_PROFILES_DIR.exists():
        return
    for f in CUSTOM_PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profile = StyleProfile(**data)
            _CUSTOM_PROFILES[profile.profile_id] = profile
            logger.info("Načten custom profil: %s", profile.profile_id)
        except Exception as e:
            logger.warning("Nelze načíst profil %s: %s", f.name, e)


def get_all_profiles() -> list[StyleProfile]:
    """Vrátí všechny dostupné style profiles (hardcoded + custom)."""
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = _build_profiles()
        _load_custom_profiles()
    return _PROFILES + list(_CUSTOM_PROFILES.values())


def get_profile(profile_id: str) -> StyleProfile | None:
    """Vrátí profil podle ID."""
    for p in get_all_profiles():
        if p.profile_id == profile_id:
            return p
    return None


def register_profile(profile: StyleProfile) -> None:
    """Zaregistruje nový custom profil a uloží do JSON."""
    _CUSTOM_PROFILES[profile.profile_id] = profile
    # Uložit na disk
    out_path = CUSTOM_PROFILES_DIR / f"{profile.profile_id}.json"
    out_path.write_text(
        json.dumps(profile.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Registrován custom profil: %s → %s", profile.profile_id, out_path)


def delete_profile(profile_id: str) -> bool:
    """Smaže custom profil. Hardcoded profily nelze smazat."""
    if profile_id in ("ng_feature", "ng_short"):
        return False
    if profile_id in _CUSTOM_PROFILES:
        del _CUSTOM_PROFILES[profile_id]
        out_path = CUSTOM_PROFILES_DIR / f"{profile_id}.json"
        out_path.unlink(missing_ok=True)
        logger.info("Smazán custom profil: %s", profile_id)
        return True
    return False


def profile_from_analysis(analysis, source_name: str = "custom") -> StyleProfile:
    """Vytvoří StyleProfile z TemplateAnalysis (výstup template_analyzer).

    Extrahuje dominantní styly z analýzy — hledá headline, body, caption,
    deck, byline, folio styly podle názvů paragraph stylů.
    """
    # Sbírat styly podle typu frame z analyzovaných spreadů
    headline_styles = []
    deck_styles = []
    body_styles = []
    caption_styles = []
    byline_styles = []
    folio_styles = []
    seen_styles = set()

    # Mapování klíčových slov na kategorii
    STYLE_CATEGORIES = {
        "headline": headline_styles,
        "head": headline_styles,
        "hed": headline_styles,
        "deck": deck_styles,
        "dek": deck_styles,
        "display": deck_styles,
        "callout": deck_styles,
        "body": body_styles,
        "caption": caption_styles,
        "credit": caption_styles,
        "byline": byline_styles,
        "bio": byline_styles,
        "folio": folio_styles,
        "footer": folio_styles,
    }

    # Projít paragraph styly z analýzy
    for spread_data in getattr(analysis, 'spreads', []):
        for frame in getattr(spread_data, 'frames', []):
            style_name = getattr(frame, 'primary_style', '') or ''
            if not style_name or style_name in seen_styles:
                continue
            seen_styles.add(style_name)

            # Klasifikovat styl podle klíčových slov v názvu
            style_lower = style_name.lower()
            target_list = None
            for keyword, lst in STYLE_CATEGORIES.items():
                if keyword in style_lower:
                    target_list = lst
                    break

            if target_list is not None:
                # Zkusit najít font info z frame
                font_family = getattr(frame, 'font_family', '') or 'Grosvenor Book'
                font_style = getattr(frame, 'font_style', '') or ''
                point_size = getattr(frame, 'point_size', 0) or 9
                leading = getattr(frame, 'leading', 0) or 12

                target_list.append(StyleInfo(
                    style_name=style_name,
                    font_family=font_family,
                    font_style=font_style if font_style else None,
                    point_size=point_size,
                    leading=leading,
                ))

    # Extrahovat page dimensions z analýzy
    page_width = getattr(analysis, 'page_width', 495) or 495
    page_height = getattr(analysis, 'page_height', 720) or 720

    # Fallback styly pokud žádné nebyly nalezeny
    if not headline_styles:
        headline_styles = [StyleInfo(style_name="Head_1", font_family="Grosvenor Book", point_size=24, leading=28)]
    if not body_styles:
        body_styles = [StyleInfo(style_name="Body_1", font_family="Grosvenor Book", point_size=9, leading=12)]
    if not caption_styles:
        caption_styles = [StyleInfo(style_name="Caption_1", font_family="Geograph Edit", point_size=8, leading=9.25)]

    # Generovat unikátní ID
    import re
    safe_name = re.sub(r'[^a-z0-9_-]', '_', source_name.lower())[:40]
    profile_id = f"custom_{safe_name}"

    return StyleProfile(
        profile_id=profile_id,
        profile_name=f"Custom: {source_name}",
        description=f"Automaticky extrahovaný profil z {source_name}. "
                    f"{len(headline_styles)} headline, {len(body_styles)} body, {len(caption_styles)} caption stylů.",
        page_width=page_width,
        page_height=page_height,
        margin_top=75,
        margin_bottom=84,
        margin_left=57,
        margin_right=48,
        column_count=12,
        column_gutter=24,
        headline_styles=headline_styles,
        deck_styles=deck_styles or [StyleInfo(style_name="Deck_1", font_family="Geograph Edit", font_style="Bold", point_size=11, leading=12)],
        body_styles=body_styles,
        caption_styles=caption_styles,
        byline_styles=byline_styles or [StyleInfo(style_name="Byline_1", font_family="Geograph Edit", point_size=7, leading=18, capitalization="AllCaps")],
        folio_styles=folio_styles or [StyleInfo(style_name="Footer_1", font_family="Grosvenor Book", font_style="Medium", point_size=6, tracking=300, leading=11, capitalization="AllCaps")],
    )


def get_style_for_frame_type(
    profile: StyleProfile,
    style_name: str,
) -> StyleInfo | None:
    """Najde konkrétní styl v profilu podle jména."""
    all_styles = (
        profile.headline_styles
        + profile.deck_styles
        + profile.body_styles
        + profile.caption_styles
        + profile.byline_styles
        + profile.folio_styles
    )
    for s in all_styles:
        if s.style_name == style_name:
            return s
    return None


def get_primary_headline(profile: StyleProfile) -> StyleInfo | None:
    """Vrátí primární headline styl profilu (první v seznamu)."""
    return profile.headline_styles[0] if profile.headline_styles else None


def get_primary_body(profile: StyleProfile) -> StyleInfo | None:
    """Vrátí primární body styl profilu."""
    return profile.body_styles[0] if profile.body_styles else None
