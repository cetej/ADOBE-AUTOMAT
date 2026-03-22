"""Typografické profily extrahované z NG IDML šablon.

Dva profily:
- NG Feature — pro velké reportáže (FEA_* styly, Marden headlines)
- NG Short — pro frontmatter / medium features (INT_* styly, Grosvenor headlines)

Profily obsahují IDML paragraph a character style definice pro:
headline, deck, body, caption, byline, folio, credit, pull_quote.

Generováno z analýzy 15 IDML souborů květnového čísla NG 05/2026.
"""

from backend.models_layout import StyleInfo, StyleProfile


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


def get_all_profiles() -> list[StyleProfile]:
    """Vrátí všechny dostupné style profiles."""
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = _build_profiles()
    return _PROFILES


def get_profile(profile_id: str) -> StyleProfile | None:
    """Vrátí profil podle ID."""
    for p in get_all_profiles():
        if p.profile_id == profile_id:
            return p
    return None


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
