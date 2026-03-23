"""Pydantic modely pro Layout Generator."""

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


# NG magazine page dimensions (points)
NG_PAGE_WIDTH = 495.0
NG_PAGE_HEIGHT = 720.0
NG_SPREAD_WIDTH = 990.0
NG_SPREAD_HEIGHT = 720.0


# === Enums pro Layout Planner (Session 4) ===

class ImagePriority(str, Enum):
    """Priorita fotky v layoutu."""
    HERO = "hero"               # Hlavní fotka — opening spread, full-bleed
    SUPPORTING = "supporting"   # Velké fotky pro body spreads
    DETAIL = "detail"           # Menší fotky, do gridu nebo menších rámců


class ImageOrientation(str, Enum):
    """Orientace fotky."""
    LANDSCAPE = "landscape"     # Šířka > výška (poměr > 1.2)
    PORTRAIT = "portrait"       # Výška > šířka (poměr < 0.8)
    SQUARE = "square"           # Přibližně čtvercová (0.8–1.2)


class FrameType(str, Enum):
    """Typ rámce v IDML spreadu."""
    HERO_IMAGE = "hero_image"       # Full-bleed nebo dominantní fotka
    BODY_IMAGE = "body_image"       # Menší fotka v body spreadu
    BODY_TEXT = "body_text"         # Hlavní text článku (threaded)
    HEADLINE = "headline"           # Titulek reportáže
    DECK = "deck"                   # Podtitulek / deck
    BYLINE = "byline"              # Jméno autora / fotografa
    CAPTION = "caption"             # Popisek fotky
    PULL_QUOTE = "pull_quote"       # Vytažená citace
    FOLIO = "folio"                # Číslo stránky / patička
    CREDIT = "credit"              # Photo credit
    SIDEBAR = "sidebar"            # Boční panel
    MAP_ART = "map_art"            # Mapa / infografika
    MAP_LABEL = "map_label"        # Popisek na mapě
    LOGO = "logo"                  # Logo (cover)
    COVER_LINE = "cover_line"      # Titulek na obálce
    UNKNOWN = "unknown"


class SpreadType(str, Enum):
    """Klasifikace typu spreadu."""
    OPENING = "opening"             # Opening spread — full-bleed foto + titulky
    PHOTO_DOMINANT = "photo_dominant"  # Velká fotka + caption
    PHOTO_GRID = "photo_grid"       # Mřížka fotek
    BODY_TEXT = "body_text"         # Text-heavy spread se sloupci
    BODY_MIXED = "body_mixed"       # Text + fotky vyvážené
    MAP_INFOGRAPHIC = "map_infographic"  # Mapa nebo infografika
    CLOSING = "closing"             # Závěrečný spread (bio, credits)
    COVER = "cover"                 # Obálka
    TOC = "toc"                     # Obsah
    FRONTMATTER = "frontmatter"     # Frontmatter rubrika
    BIG_PICTURE = "big_picture"     # Big Picture — full-bleed + minimální text


class Bounds(BaseModel):
    """Absolutní pozice a rozměry rámce v bodech (pt)."""
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 0


class FrameSpec(BaseModel):
    """Specifikace jednoho rámce ve spreadu."""
    frame_id: str
    frame_type: FrameType
    bounds: Bounds
    # Pro text frames
    story_id: Optional[str] = None
    paragraph_style: Optional[str] = None
    text_content: Optional[str] = None
    # Pro image frames
    linked_file: Optional[str] = None
    # Relativní pozice vůči stránce (0-1)
    rel_x: Optional[float] = None
    rel_y: Optional[float] = None
    rel_width: Optional[float] = None
    rel_height: Optional[float] = None


class PageSpec(BaseModel):
    """Specifikace jedné stránky."""
    page_name: str
    width: float        # pt
    height: float       # pt
    margin_top: float = 0
    margin_bottom: float = 0
    margin_left: float = 0
    margin_right: float = 0
    column_count: int = 1
    column_gutter: float = 0


class SpreadAnalysis(BaseModel):
    """Analýza jednoho spreadu z existujícího IDML."""
    spread_index: int
    spread_id: str
    spread_type: SpreadType
    pages: list[PageSpec]
    frames: list[FrameSpec]
    # Statistiky
    text_frame_count: int = 0
    image_frame_count: int = 0
    text_area_ratio: float = 0      # Podíl plochy textu na spreadu
    image_area_ratio: float = 0     # Podíl plochy obrázků na spreadu
    has_bleed_image: bool = False    # Fotka přesahuje okraje stránky


class StyleInfo(BaseModel):
    """Informace o typografickém stylu."""
    style_name: str
    font_family: Optional[str] = None
    font_style: Optional[str] = None
    point_size: Optional[float] = None
    tracking: Optional[int] = None
    leading: Optional[float] = None
    capitalization: Optional[str] = None
    fill_color: Optional[str] = None


class TemplateAnalysis(BaseModel):
    """Kompletní analýza jednoho IDML souboru."""
    source_file: str
    document_type: str = ""         # feature, mf, frontmatter, cover
    page_width: float               # pt
    page_height: float              # pt
    page_count: int
    spread_count: int
    spreads: list[SpreadAnalysis]
    paragraph_styles: list[StyleInfo] = []
    character_styles: list[StyleInfo] = []
    # Souhrnné statistiky
    avg_text_ratio: float = 0
    avg_image_ratio: float = 0
    spread_type_distribution: dict[str, int] = {}


class SpreadPattern(BaseModel):
    """Abstraktní vzor spreadu — parametrizovaný, ne fixní pixely."""
    pattern_id: str
    pattern_name: str
    spread_type: SpreadType
    description: str = ""
    # Sloty — relativní pozice (0-1) vůči spread ploše
    slots: list["SlotSpec"]
    # Constraints
    min_images: int = 0
    max_images: int = 10
    min_text_chars: int = 0
    preferred_for: list[str] = []   # ["opening", "body", "closing"]


class SlotSpec(BaseModel):
    """Slot v spread patternu — relativní pozice pro text nebo obrázek."""
    slot_id: str
    slot_type: FrameType
    # Relativní pozice vůči spreadu (0-1)
    rel_x: float
    rel_y: float
    rel_width: float
    rel_height: float
    # Je povinný?
    required: bool = True
    # Pro text sloty
    default_style: Optional[str] = None
    # Pro image sloty
    allow_bleed: bool = False


class StyleProfile(BaseModel):
    """Typografický profil — definuje vizuální styl layoutu."""
    profile_id: str
    profile_name: str
    description: str = ""
    # Rozměry stránky
    page_width: float = 495         # pt (NG standard)
    page_height: float = 720        # pt
    # Marginy
    margin_top: float = 75
    margin_bottom: float = 84
    margin_left: float = 57
    margin_right: float = 48
    # Grid
    column_count: int = 12
    column_gutter: float = 24
    # Styly pro různé elementy
    headline_styles: list[StyleInfo] = []
    deck_styles: list[StyleInfo] = []
    body_styles: list[StyleInfo] = []
    caption_styles: list[StyleInfo] = []
    byline_styles: list[StyleInfo] = []
    folio_styles: list[StyleInfo] = []


class LayoutPlan(BaseModel):
    """Plán layoutu — sekvence spreadů s přiřazeným obsahem."""
    project_id: str
    style_profile: str
    total_pages: int
    spreads: list["PlannedSpread"]


class PlannedSpread(BaseModel):
    """Jeden naplánovaný spread s přiřazeným obsahem."""
    spread_index: int
    pattern_id: str
    spread_type: SpreadType
    assigned_images: list[str] = []      # Cesty k fotkám
    assigned_image_infos: list["ImageInfo"] = []  # Detailní info o fotkách
    assigned_text_sections: list[str] = []  # ID textových sekcí
    notes: str = ""


# === Modely pro Layout Planner (Session 4) ===

class ImageInfo(BaseModel):
    """Metadata o jedné nahráné fotce."""
    path: str
    filename: str = ""
    width: int = 0              # px
    height: int = 0             # px
    orientation: ImageOrientation = ImageOrientation.LANDSCAPE
    aspect_ratio: float = 1.0   # width / height
    priority: ImagePriority = ImagePriority.SUPPORTING
    megapixels: float = 0.0
    content_hint: str = ""      # Z Claude Vision (volitelné): "landscape", "portrait", "detail"


class ArticleText(BaseModel):
    """Strukturovaný text článku pro layout planner."""
    headline: str = ""
    deck: str = ""
    byline: str = ""
    body_paragraphs: list[str] = []
    captions: list[str] = []
    pull_quotes: list[str] = []
    # Souhrnné statistiky
    total_body_chars: int = 0
    total_chars: int = 0


class ArticleItem(BaseModel):
    """Jeden článek v multi-article layoutu."""
    article_id: str
    headline: str = ""
    deck: str = ""
    byline: str = ""
    body_paragraphs: list[str] = []
    captions: list[str] = []
    pull_quotes: list[str] = []
    style_profile_id: str = "ng_feature"
    total_body_chars: int = 0
    total_chars: int = 0


class MultiArticleText(BaseModel):
    """Kolekce článků pro multi-article layout."""
    articles: list[ArticleItem]
    credits: str = ""


class MultiArticlePlan(BaseModel):
    """Plán layoutu pro více článků — jeden LayoutPlan per article."""
    project_id: str
    total_pages: int
    article_plans: list[LayoutPlan]
    article_boundaries: list[dict] = []  # [{article_id, start_page, end_page}]


class MapInfo(BaseModel):
    """Info o detekované nebo editované mapě v layout projektu."""
    slot_id: str = ""
    filename: str = ""
    path: str = ""
    confidence: float = 0.0
    map_type: str = "map"        # "map" | "infographic" | "diagram"
    reasons: list[str] = []
    status: str = "detected"     # "detected" | "exporting" | "editing" | "edited"
    width: int = 0
    height: int = 0
    aspect_ratio: float = 1.0


class TextEstimate(BaseModel):
    """Odhad prostorových nároků textu v layoutu."""
    total_body_chars: int = 0
    chars_per_column: int = 2200    # NG: ~40 znaků/řádek × 55 řádků
    chars_per_page: int = 4400      # 2 sloupce na stránku
    estimated_body_pages: float = 0.0
    estimated_total_spreads: int = 1  # Včetně opening + closing
    has_pull_quotes: bool = False
    has_captions: bool = False
