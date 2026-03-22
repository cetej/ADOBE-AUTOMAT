"""Pydantic modely pro NGM Localizer."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    MAP = "map"
    IDML = "idml"


class ProjectPhase(str, Enum):
    CREATED = "created"
    EXTRACTED = "extracted"
    CATEGORIZED = "categorized"
    TRANSLATED = "translated"
    REVIEWED = "reviewed"
    EXPORTED = "exported"
    WRITTEN_BACK = "written_back"


class TextStatus(str, Enum):
    OK = "OK"
    OPRAVIT = "OPRAVIT"
    OVERIT = "OVERIT"
    PREVZIT = "PREVZIT"
    CHYBI = "CHYBI"


class TextCategory(str, Enum):
    # Geografie
    OCEANS_SEAS = "oceans_seas"
    CONTINENTS = "continents"
    COUNTRIES_FULL = "countries_full"
    COUNTRIES_ABBREV = "countries_abbrev"
    REGIONS = "regions"
    CITIES = "cities"
    WATER_BODIES = "water_bodies"
    LANDFORMS = "landforms"
    PLACES = "places"
    # Obsah
    TITLE = "title"
    INFO_BOXES = "info_boxes"
    LABELS = "labels"
    ANNOTATIONS = "annotations"
    MAIN_TEXT = "main_text"
    # Reference
    LEGEND = "legend"
    SCALE = "scale"
    TIMELINE = "timeline"
    CREDITS = "credits"
    # Historicke
    PERIODS = "periods"
    EVENTS = "events"
    DATES = "dates"
    SETTLEMENTS = "settlements"
    # IDML specificke
    LEAD = "lead"
    BODY = "body"
    SUBTITLE = "subtitle"
    HEADING = "heading"
    BULLET = "bullet"
    SEPARATOR = "separator"
    CAPTION = "caption"


class TextElement(BaseModel):
    """Textovy element — spolecny pro MAP i IDML."""
    id: str
    contents: str
    czech: Optional[str] = None
    status: Optional[TextStatus] = None
    category: Optional[TextCategory] = None
    notes: Optional[str] = None
    auto_translated: bool = False
    # MAP specificke
    position: Optional[list[float]] = None
    fontSize: Optional[float] = None
    layer_name: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    kind: Optional[str] = None
    # IDML specificke
    story_id: Optional[str] = None
    paragraph_style: Optional[str] = None


class LayerData(BaseModel):
    """Vrstva z Illustratoru."""
    layerName: str
    layerId: int
    texts: list[TextElement] = []


class Project(BaseModel):
    """Projekt lokalizace."""
    id: str
    name: str
    type: ProjectType
    source_file: Optional[str] = None
    phase: ProjectPhase = ProjectPhase.CREATED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    elements: list[TextElement] = []
    exports: dict[str, str] = {}
    # IDML specificke
    idml_path: Optional[str] = None
    translation_doc: Optional[str] = None
    source_pdf: Optional[str] = None
    backgrounder: Optional[str] = None
    issues: list[dict] = []


# --- Request/Response modely ---

class ProjectCreate(BaseModel):
    name: str
    type: ProjectType
    source_file: Optional[str] = None


class TextUpdate(BaseModel):
    czech: Optional[str] = None
    status: Optional[TextStatus] = None
    category: Optional[TextCategory] = None
    notes: Optional[str] = None


class BulkTextUpdate(BaseModel):
    ids: list[str]
    status: Optional[TextStatus] = None
    category: Optional[TextCategory] = None


class TranslateRequest(BaseModel):
    """Pozadavek na AI preklad."""
    ids: Optional[list[str]] = None  # None = vsechny neprelozene
    model: str = "claude-sonnet-4-20250514"
    overwrite: bool = False  # True = prelozit i uz prelozene
