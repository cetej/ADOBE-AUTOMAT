"""Analýza nahraných fotek pro Layout Planner.

Funkce:
- analyze_image() — rozměry, orientace, aspect ratio (Pillow)
- classify_images() — přiřazení priorit (hero/supporting/detail)
- analyze_image_content() — volitelná Claude Vision analýza obsahu

Generováno pro Session 4 Layout Generator.
"""

import logging
import os
from math import ceil
from pathlib import Path
from typing import Optional

from backend.models_layout import ImageInfo, ImageOrientation, ImagePriority

logger = logging.getLogger(__name__)

# Minimální rozlišení pro hero fotku (px) — landscape hero potřebuje alespoň ~3000px šířku
HERO_MIN_WIDTH = 2400
HERO_MIN_HEIGHT = 1600
# Minimální rozlišení pro supporting fotku
SUPPORTING_MIN_WIDTH = 1200
SUPPORTING_MIN_HEIGHT = 800


def analyze_image(path: str | Path) -> ImageInfo:
    """Analyzuje jednu fotku — rozměry, orientace, aspect ratio.

    Používá Pillow pro čtení metadat, respektuje EXIF orientaci.
    """
    from PIL import Image, ExifTags

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fotka nenalezena: {path}")

    with Image.open(path) as img:
        # Respektuj EXIF orientaci (fotky z telefonu mohou být otočené)
        width, height = img.size

        try:
            exif = img.getexif()
            if exif:
                orientation_tag = None
                for tag_id, tag_name in ExifTags.TAGS.items():
                    if tag_name == "Orientation":
                        orientation_tag = tag_id
                        break
                if orientation_tag and orientation_tag in exif:
                    exif_orient = exif[orientation_tag]
                    # Orientace 5-8 = otočeno o 90° → prohodit w/h
                    if exif_orient in (5, 6, 7, 8):
                        width, height = height, width
        except Exception:
            pass  # EXIF není povinný

    aspect_ratio = width / height if height > 0 else 1.0
    megapixels = round((width * height) / 1_000_000, 1)

    # Klasifikace orientace
    if aspect_ratio > 1.2:
        orientation = ImageOrientation.LANDSCAPE
    elif aspect_ratio < 0.8:
        orientation = ImageOrientation.PORTRAIT
    else:
        orientation = ImageOrientation.SQUARE

    return ImageInfo(
        path=str(path),
        filename=path.name,
        width=width,
        height=height,
        orientation=orientation,
        aspect_ratio=round(aspect_ratio, 3),
        megapixels=megapixels,
    )


def classify_images(images: list[ImageInfo]) -> list[ImageInfo]:
    """Přiřadí priority fotkám na základě rozměrů a orientace.

    Strategie:
    - Hero: největší landscape fotka (pokud splňuje min rozlišení)
    - Supporting: velké fotky vhodné pro body spreads
    - Detail: menší fotky, čtvercové, portrétní → grid nebo menší rámce

    Modifikuje priority in-place a vrací seřazený seznam (hero first).
    """
    if not images:
        return images

    # Seřadit podle plochy (největší první)
    sorted_imgs = sorted(images, key=lambda img: img.width * img.height, reverse=True)

    hero_assigned = False
    for img in sorted_imgs:
        # Hero: největší landscape fotka s dostatečným rozlišením
        if (not hero_assigned
            and img.orientation == ImageOrientation.LANDSCAPE
            and img.width >= HERO_MIN_WIDTH
            and img.height >= HERO_MIN_HEIGHT):
            img.priority = ImagePriority.HERO
            hero_assigned = True
        # Supporting: velké fotky (landscape nebo portrait)
        elif (img.width >= SUPPORTING_MIN_WIDTH
              and img.height >= SUPPORTING_MIN_HEIGHT):
            img.priority = ImagePriority.SUPPORTING
        # Detail: vše ostatní
        else:
            img.priority = ImagePriority.DETAIL

    # Pokud žádná fotka nesplnila hero podmínky, vezmi největší landscape
    if not hero_assigned:
        for img in sorted_imgs:
            if img.orientation == ImageOrientation.LANDSCAPE:
                img.priority = ImagePriority.HERO
                hero_assigned = True
                break

    # Stále žádný hero? Vezmi prostě největší fotku
    if not hero_assigned and sorted_imgs:
        sorted_imgs[0].priority = ImagePriority.HERO

    # Seřadit: hero first, pak supporting, pak detail
    priority_order = {ImagePriority.HERO: 0, ImagePriority.SUPPORTING: 1, ImagePriority.DETAIL: 2}
    result = sorted(sorted_imgs, key=lambda img: priority_order.get(img.priority, 9))

    logger.info(
        "Klasifikováno %d fotek: %d hero, %d supporting, %d detail",
        len(result),
        sum(1 for i in result if i.priority == ImagePriority.HERO),
        sum(1 for i in result if i.priority == ImagePriority.SUPPORTING),
        sum(1 for i in result if i.priority == ImagePriority.DETAIL),
    )
    return result


def analyze_batch(paths: list[str | Path]) -> list[ImageInfo]:
    """Analyzuje a klasifikuje dávku fotek.

    Convenience wrapper: analyze_image() na každou + classify_images().
    """
    images = []
    for p in paths:
        try:
            img = analyze_image(p)
            images.append(img)
        except Exception as e:
            logger.warning("Nelze analyzovat %s: %s", p, e)

    if not images:
        logger.warning("Žádné fotky k analýze!")
        return []

    return classify_images(images)


async def analyze_image_content_ai(
    path: str | Path,
    api_key: Optional[str] = None,
) -> str:
    """Volitelná Claude Vision analýza obsahu fotky.

    Vrátí content_hint string: "landscape_scenic", "portrait_person",
    "detail_macro", "aerial", "underwater", "wildlife", "architecture" atd.

    Používá Claude API s vision capability.
    """
    import anthropic
    import base64

    path = Path(path)
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY nedostupný, přeskakuji AI analýzu")
        return ""

    # Načti obrázek jako base64
    suffix = path.suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "image/jpeg")

    with open(path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Classify this photo for magazine layout. "
                            "Return ONLY one word from: "
                            "landscape, portrait, wildlife, aerial, underwater, "
                            "architecture, detail, macro, crowd, abstract, map."
                        ),
                    },
                ],
            }],
        )
        hint = response.content[0].text.strip().lower()
        logger.info("AI content hint pro %s: %s", path.name, hint)
        return hint
    except Exception as e:
        logger.warning("AI analýza selhala pro %s: %s", path.name, e)
        return ""
