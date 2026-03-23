"""PDF Preview — renderování layout plánu do PDF pro náhled bez InDesignu.

Používá ReportLab pro generování multi-page PDF.
Každý spread = 1 strana PDF (double-page spreads jako landscape).
Image sloty zobrazují thumbnaily fotek, text sloty barevné obdélníky s labely.
"""

import logging
from pathlib import Path
from typing import Optional

from models_layout import NG_PAGE_WIDTH, NG_SPREAD_WIDTH, NG_SPREAD_HEIGHT

logger = logging.getLogger(__name__)

# Barvy pro typy slotů (RGB 0-1)
SLOT_COLORS = {
    "hero_image": (0.53, 0.94, 0.68),    # zelená
    "body_image": (0.73, 0.97, 0.83),    # světle zelená
    "body_text": (0.75, 0.86, 0.99),     # modrá
    "headline": (0.77, 0.71, 0.99),      # fialová
    "deck": (0.87, 0.84, 0.99),          # světle fialová
    "byline": (0.91, 0.84, 1.0),         # levandulová
    "caption": (0.65, 0.95, 0.98),       # cyan
    "pull_quote": (0.99, 0.90, 0.54),    # žlutá
    "folio": (0.90, 0.91, 0.93),         # šedá
    "credit": (0.90, 0.91, 0.93),        # šedá
    "sidebar": (0.98, 0.81, 0.91),       # růžová
}

SLOT_LABELS = {
    "hero_image": "Hero",
    "body_image": "Foto",
    "body_text": "Text",
    "headline": "Headline",
    "deck": "Deck",
    "byline": "Byline",
    "caption": "Caption",
    "pull_quote": "Pull Quote",
    "folio": "Folio",
    "credit": "Credit",
    "sidebar": "Sidebar",
}

# NG standard spread rozměry (pt) — importovány z models_layout
SPREAD_WIDTH = NG_SPREAD_WIDTH
SPREAD_HEIGHT = NG_SPREAD_HEIGHT
PAGE_WIDTH = NG_PAGE_WIDTH
MARGIN = {"top": 75, "bottom": 84, "left": 57, "right": 48}


def generate_preview_pdf(
    plan_detail: dict,
    project_dir: str | Path,
    style_profile_id: str = "ng_feature",
) -> Path:
    """Vygeneruje PDF náhled layoutu.

    Args:
        plan_detail: Výstup z /api/layout/plan-detail/{id} (dict se spreads + slots)
        project_dir: Cesta k adresáři projektu (pro image thumbnaily)
        style_profile_id: ID stylu (pro rozměry stránek)

    Returns:
        Cesta k vygenerovanému PDF souboru.
    """
    try:
        from reportlab.lib.pagesizes import landscape
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import Color, HexColor, white, black, lightgrey
        from reportlab.lib.utils import ImageReader
    except ImportError:
        raise RuntimeError(
            "ReportLab není nainstalován. Spusť: pip install reportlab"
        )

    project_dir = Path(project_dir)
    images_dir = project_dir / "images"
    output_path = project_dir / "preview.pdf"

    spreads = plan_detail.get("spreads", [])
    if not spreads:
        raise ValueError("Plán neobsahuje žádné spready")

    # PDF page size = spread v reálném měřítku (pt)
    page_size = (SPREAD_WIDTH, SPREAD_HEIGHT)

    c = canvas.Canvas(str(output_path), pagesize=page_size)
    c.setTitle(f"Layout Preview — {plan_detail.get('project_id', 'layout')}")
    c.setAuthor("NGM Layout Generator")

    for spread_idx, spread in enumerate(spreads):
        _draw_spread(c, spread, images_dir, spread_idx, len(spreads))
        c.showPage()

    c.save()
    logger.info("PDF preview vygenerován: %s (%d spreadů)", output_path, len(spreads))
    return output_path


def _draw_spread(c, spread: dict, images_dir: Path, spread_idx: int, total: int):
    """Nakreslí jeden spread do PDF stránky."""
    from reportlab.lib.colors import Color, white, black, lightgrey, HexColor
    from reportlab.lib.utils import ImageReader

    # Pozadí
    c.setFillColor(white)
    c.rect(0, 0, SPREAD_WIDTH, SPREAD_HEIGHT, fill=1, stroke=0)

    # Stránkové hranice (svislá čára uprostřed)
    c.setStrokeColor(lightgrey)
    c.setLineWidth(0.5)
    c.line(PAGE_WIDTH, 0, PAGE_WIDTH, SPREAD_HEIGHT)

    # Marginy (čárkovaně)
    c.setDash(3, 3)
    c.setStrokeColor(Color(0.85, 0.85, 0.85))
    # Levá stránka
    c.rect(MARGIN["left"], MARGIN["bottom"],
           PAGE_WIDTH - MARGIN["left"] - MARGIN["right"],
           SPREAD_HEIGHT - MARGIN["top"] - MARGIN["bottom"],
           fill=0, stroke=1)
    # Pravá stránka
    c.rect(PAGE_WIDTH + MARGIN["left"], MARGIN["bottom"],
           PAGE_WIDTH - MARGIN["left"] - MARGIN["right"],
           SPREAD_HEIGHT - MARGIN["top"] - MARGIN["bottom"],
           fill=0, stroke=1)
    c.setDash()  # Reset dash

    # Sloty
    slots = spread.get("slots", [])
    assigned_images = spread.get("assigned_images", [])

    # Mapa image slotů → přiřazené fotky
    image_slots = [s for s in slots if s.get("slot_type") in ("hero_image", "body_image")]
    img_map = {}
    for i, slot in enumerate(image_slots):
        if i < len(assigned_images):
            img_map[slot["slot_id"]] = assigned_images[i]

    for slot in slots:
        slot_type = slot.get("slot_type", "unknown")
        rx = slot.get("rel_x", 0)
        ry = slot.get("rel_y", 0)
        rw = slot.get("rel_width", 0)
        rh = slot.get("rel_height", 0)

        # Absolutní souřadnice (ReportLab: origin = bottom-left)
        x = rx * SPREAD_WIDTH
        y = SPREAD_HEIGHT - (ry + rh) * SPREAD_HEIGHT  # Flip Y
        w = rw * SPREAD_WIDTH
        h = rh * SPREAD_HEIGHT

        if w < 1 or h < 1:
            continue

        # Barva pozadí slotu
        color = SLOT_COLORS.get(slot_type, (0.9, 0.9, 0.9))
        c.setFillColor(Color(*color, alpha=0.6))
        c.setStrokeColor(Color(color[0] * 0.7, color[1] * 0.7, color[2] * 0.7))
        c.setLineWidth(0.75)
        c.rect(x, y, w, h, fill=1, stroke=1)

        # Zkusit vložit thumbnail fotky pro image sloty
        img_info = img_map.get(slot.get("slot_id"))
        if img_info and slot_type in ("hero_image", "body_image"):
            filename = img_info.get("filename", "")
            img_path = images_dir / filename
            if img_path.exists():
                try:
                    img = ImageReader(str(img_path))
                    # Fit do slotu se zachováním aspect ratio
                    iw, ih = img.getSize()
                    scale = min(w / iw, h / ih)
                    draw_w = iw * scale
                    draw_h = ih * scale
                    draw_x = x + (w - draw_w) / 2
                    draw_y = y + (h - draw_h) / 2
                    c.drawImage(img, draw_x, draw_y, draw_w, draw_h,
                                preserveAspectRatio=True, mask='auto')
                except Exception as e:
                    logger.debug("Nelze vložit fotku %s: %s", filename, e)

        # Label
        label = SLOT_LABELS.get(slot_type, slot_type)
        c.setFillColor(Color(0.3, 0.3, 0.3, alpha=0.8))
        font_size = min(10, h * 0.3, w * 0.15)
        if font_size >= 5:
            c.setFont("Helvetica", font_size)
            c.drawCentredString(x + w / 2, y + h / 2 - font_size / 3, label)

    # Spread info — záhlaví
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(Color(0.4, 0.4, 0.4))
    info_text = f"Spread {spread_idx + 1}/{total}  —  {spread.get('spread_type', '')}  —  pattern: {spread.get('pattern_id', '')}"
    c.drawString(10, SPREAD_HEIGHT - 12, info_text)

    # Počet fotek
    if assigned_images:
        c.setFont("Helvetica", 7)
        c.setFillColor(Color(0.5, 0.5, 0.5))
        img_names = ", ".join(img.get("filename", "?") for img in assigned_images[:4])
        if len(assigned_images) > 4:
            img_names += f" +{len(assigned_images) - 4}"
        c.drawString(10, 8, f"Fotky: {img_names}")
