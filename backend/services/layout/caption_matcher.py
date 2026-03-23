"""Caption Matcher — AI přiřazení popisků k fotkám.

Používá Claude Vision pro analýzu obsahu fotek a sémantické matchování
s textovými popisky (captions) z článku.

Dva režimy:
- AI matching: Claude Vision → popis obsahu fotky → matching s captions
- Fallback: pořadí (1. fotka = 1. caption)
"""

import base64
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Podporované formáty pro Claude Vision
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
# Max velikost pro base64 encoding (Claude limit ~20MB)
MAX_IMAGE_SIZE = 15 * 1024 * 1024  # 15 MB


def match_captions_to_images(
    image_paths: list[str | Path],
    captions: list[str],
    api_key: Optional[str] = None,
) -> list[dict]:
    """Přiřadí captions k fotkám.

    Args:
        image_paths: Cesty k obrázkům
        captions: Seznam textových popisků
        api_key: Anthropic API klíč (None = fallback na pořadí)

    Returns:
        Seznam matchů: [{"image": "file.jpg", "caption": "text...", "confidence": 0.0-1.0, "method": "ai"|"order"}]
    """
    if not image_paths or not captions:
        return []

    # Normalizovat cesty
    paths = [Path(p) for p in image_paths]
    paths = [p for p in paths if p.exists() and p.suffix.lower() in SUPPORTED_FORMATS]

    if not paths:
        logger.warning("Žádné validní fotky pro caption matching")
        return []

    # AI matching pokud je API klíč
    if api_key:
        try:
            return _match_ai(paths, captions, api_key)
        except Exception as e:
            logger.warning("AI matching selhal, fallback na pořadí: %s", e)

    # Fallback: matching podle pořadí
    return _match_by_order(paths, captions)


def _match_by_order(paths: list[Path], captions: list[str]) -> list[dict]:
    """Jednoduchý matching: 1. fotka = 1. caption, 2. = 2., atd."""
    results = []
    for i, path in enumerate(paths):
        caption = captions[i] if i < len(captions) else ""
        results.append({
            "image": path.name,
            "caption": caption,
            "confidence": 0.5 if caption else 0.0,
            "method": "order",
        })
    return results


def _match_ai(paths: list[Path], captions: list[str], api_key: str) -> list[dict]:
    """AI-assisted matching pomocí Claude Vision.

    Krok 1: Pošle všechny fotky + captions Claudeovi
    Krok 2: Claude vrátí JSON s přiřazením
    """
    from core.engine import get_engine, MODEL_SONNET

    engine = get_engine()

    # Připravit obsah zprávy — fotky jako base64 + captions jako text
    content = []

    # Přidat fotky (max 10 kvůli token limitu)
    photo_paths = paths[:10]
    for i, path in enumerate(photo_paths):
        if path.stat().st_size > MAX_IMAGE_SIZE:
            logger.info("Přeskakuji příliš velký obrázek: %s", path.name)
            continue

        # Zjistit MIME typ
        suffix = path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".gif": "image/gif", ".webp": "image/webp"}
        media_type = mime_map.get(suffix, "image/jpeg")

        img_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        content.append({
            "type": "text",
            "text": f"Photo {i + 1}: {path.name}",
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": img_data,
            },
        })

    # Přidat captions
    captions_text = "\n".join(f"Caption {i + 1}: {cap}" for i, cap in enumerate(captions))
    content.append({
        "type": "text",
        "text": f"""Here are {len(captions)} captions from the article. Match each caption to the most relevant photo above.

{captions_text}

Return a JSON array of matches. Each match has:
- "photo_index": 1-based index of the photo
- "caption_index": 1-based index of the caption
- "confidence": 0.0 to 1.0 confidence score
- "reason": brief explanation (1 sentence)

Match each caption to exactly one photo. If a caption doesn't match any photo well, still assign it to the best option but with low confidence.
Return ONLY the JSON array, no other text.""",
    })

    result = engine.generate(
        messages=[{"role": "user", "content": content}],
        model=MODEL_SONNET,
        max_tokens=2000,
    )

    # Parsovat odpověď
    response_text = result.content.strip()
    # Vyčistit markdown wrapper pokud přítomen
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    matches_raw = json.loads(response_text)

    # Sestavit výsledky
    results = []
    assigned_captions = set()

    for match in matches_raw:
        pi = match.get("photo_index", 1) - 1
        ci = match.get("caption_index", 1) - 1
        conf = match.get("confidence", 0.5)

        if pi < 0 or pi >= len(photo_paths) or ci < 0 or ci >= len(captions):
            continue
        if ci in assigned_captions:
            continue
        assigned_captions.add(ci)

        results.append({
            "image": photo_paths[pi].name,
            "caption": captions[ci],
            "confidence": round(conf, 2),
            "method": "ai",
            "reason": match.get("reason", ""),
        })

    # Doplnit fotky bez caption (order fallback)
    matched_images = {r["image"] for r in results}
    remaining_captions = [c for i, c in enumerate(captions) if i not in assigned_captions]
    rc_idx = 0
    for path in photo_paths:
        if path.name not in matched_images:
            cap = remaining_captions[rc_idx] if rc_idx < len(remaining_captions) else ""
            results.append({
                "image": path.name,
                "caption": cap,
                "confidence": 0.3 if cap else 0.0,
                "method": "fallback",
            })
            rc_idx += 1

    return results
