"""Detektor map a infografik v obrázcích layout projektu.

Heuristická detekce + volitelná Claude Vision analýza.
"""

import logging
import re
from typing import Optional

from models_layout import ImageInfo, Bounds

logger = logging.getLogger(__name__)

# Klíčová slova v názvech souborů
FILENAME_KEYWORDS = {
    "map", "mapa", "mapy", "infographic", "infografika", "diagram",
    "schema", "schemat", "chart", "graf", "prehled", "overview",
}

# Klíčová slova v popiscích
CAPTION_KEYWORDS = {
    "mapa", "mapy", "diagram", "přehled", "infografika", "schéma",
    "graf", "rozložení", "rozmístění", "trasa", "cesta", "oblast",
    "národní park", "chráněná oblast", "poloha", "lokace",
}


class MapCandidate:
    """Kandidát na mapu/infografiku."""

    def __init__(
        self,
        image: ImageInfo,
        confidence: float,
        map_type: str = "map",
        reasons: list[str] | None = None,
    ):
        self.image = image
        self.confidence = min(max(confidence, 0.0), 1.0)
        self.map_type = map_type  # "map" | "infographic" | "diagram"
        self.reasons = reasons or []

    def to_dict(self) -> dict:
        return {
            "filename": self.image.filename,
            "path": self.image.path,
            "confidence": round(self.confidence, 2),
            "map_type": self.map_type,
            "reasons": self.reasons,
            "width": self.image.width,
            "height": self.image.height,
            "aspect_ratio": round(self.image.aspect_ratio, 2),
        }


def detect_maps(
    images: list[ImageInfo],
    captions: list[str] | None = None,
    threshold: float = 0.3,
) -> list[MapCandidate]:
    """Detekuje mapy/infografiky v seznamu obrázků.

    Heuristiky:
    1. Filename klíčová slova (+0.5 confidence)
    2. Aspect ratio blízký 1:1 (0.7–1.3) (+0.2)
    3. Caption klíčová slova (+0.3)

    Args:
        images: Seznam obrázků s metadata.
        captions: Volitelné popisky (párované s images nebo obecné).
        threshold: Minimální confidence pro vrácení kandidáta.

    Returns:
        Seznam MapCandidate seřazený podle confidence (desc).
    """
    captions = captions or []
    caption_text = " ".join(captions).lower()

    candidates = []

    for idx, img in enumerate(images):
        confidence = 0.0
        reasons = []
        map_type = "map"

        # 1. Filename keywords
        fname_lower = img.filename.lower()
        fname_base = re.sub(r"\.[^.]+$", "", fname_lower)  # bez přípony
        for kw in FILENAME_KEYWORDS:
            if kw in fname_base:
                confidence += 0.5
                reasons.append(f"filename contains '{kw}'")
                if kw in ("infographic", "infografika"):
                    map_type = "infographic"
                elif kw in ("diagram", "schema", "schemat", "chart", "graf"):
                    map_type = "diagram"
                break

        # 2. Aspect ratio blízký 1:1
        ar = img.aspect_ratio
        if 0.7 <= ar <= 1.3:
            confidence += 0.2
            reasons.append(f"near-square aspect ratio ({ar:.2f})")

        # 3. Caption keywords
        # Zkusit párovaný caption (pokud existuje)
        img_caption = captions[idx] if idx < len(captions) else ""
        search_text = (img_caption + " " + caption_text).lower()
        for kw in CAPTION_KEYWORDS:
            if kw in search_text:
                confidence += 0.3
                reasons.append(f"caption contains '{kw}'")
                break

        # 4. Content hint z image_analyzer (pokud byl spuštěn Claude Vision)
        if img.content_hint:
            hint = img.content_hint.lower()
            if any(kw in hint for kw in ("map", "mapa", "infographic", "diagram")):
                confidence += 0.4
                reasons.append(f"content_hint: '{img.content_hint}'")

        if confidence >= threshold:
            candidates.append(MapCandidate(
                image=img,
                confidence=confidence,
                map_type=map_type,
                reasons=reasons,
            ))

    # Seřadit podle confidence (highest first)
    candidates.sort(key=lambda c: c.confidence, reverse=True)

    logger.info(
        "Map detection: %d images → %d candidates (threshold=%.1f)",
        len(images), len(candidates), threshold,
    )
    return candidates
