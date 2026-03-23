"""Layout Planner — návrh sekvence spreadů z fotek + textu.

Dva režimy:
1. Rule-based (vždy funguje) — deterministická distribuce fotek a textu
2. AI-assisted (volitelné) — Claude API navrhne optimální sekvenci

Vstup: fotky (ImageInfo[]) + text (ArticleText) + styl (StyleProfile)
Výstup: LayoutPlan — sekvence PlannedSpread s přiřazeným obsahem

Generováno pro Session 4 Layout Generator.
"""

import json
import logging
import os
import uuid
from math import ceil
from pathlib import Path
from typing import Optional

from models_layout import (
    ArticleItem, ArticleText, FrameType, ImageInfo, ImageOrientation,
    ImagePriority, LayoutPlan, MultiArticlePlan, MultiArticleText,
    PlannedSpread, SpreadType, TextEstimate,
)
from services.layout.image_analyzer import analyze_batch, classify_images
from services.layout.spread_patterns import (
    get_all_patterns, get_pattern, get_patterns_for_role,
)
from services.layout.style_profiles import get_profile
from services.layout.text_parser import estimate_text_space, parse_article_text

logger = logging.getLogger(__name__)

# Maximální počet spreadů v jednom layoutu
MAX_SPREADS = 40
# Minimální počet spreadů (opening + 1 body + closing)
MIN_SPREADS = 3


def plan_layout(
    images: list[ImageInfo],
    text: ArticleText,
    style_profile_id: str = "ng_feature",
    num_pages: int | str = "auto",
    project_id: Optional[str] = None,
    use_ai: bool = False,
    api_key: Optional[str] = None,
) -> LayoutPlan:
    """Naplánuje layout — sekvenci spreadů s přiřazenými fotkami a textem.

    Args:
        images: Klasifikované fotky (z image_analyzer.classify_images)
        text: Strukturovaný text článku (z text_parser.parse_article_text)
        style_profile_id: ID typografického profilu ("ng_feature" nebo "ng_short")
        num_pages: Počet stran ("auto" pro automatický odhad, nebo číslo)
        project_id: ID projektu (generuje se pokud chybí)
        use_ai: Použít Claude API pro návrh (fallback na rule-based)
        api_key: Anthropic API klíč (nebo z env)

    Returns:
        LayoutPlan s přiřazenými fotkami a textovými sekcemi
    """
    project_id = project_id or str(uuid.uuid4())[:8]
    profile = get_profile(style_profile_id)

    # Odhad prostoru pro text
    text_estimate = estimate_text_space(text, profile)

    # Počet spreadů
    if num_pages == "auto" or num_pages is None:
        target_spreads = _auto_spread_count(images, text_estimate)
    else:
        target_spreads = max(MIN_SPREADS, ceil(int(num_pages) / 2))

    target_spreads = min(target_spreads, MAX_SPREADS)

    logger.info(
        "Plánování layoutu: %d fotek, %d znaků textu, cíl %d spreadů, profil %s",
        len(images), text.total_body_chars, target_spreads, style_profile_id,
    )

    # AI-assisted plánování (volitelné)
    if use_ai:
        ai_plan = _plan_ai(images, text, text_estimate, target_spreads,
                           style_profile_id, project_id, api_key)
        if ai_plan:
            return ai_plan
        logger.info("AI plánování selhalo, fallback na rule-based")

    # Rule-based plánování
    return _plan_rule_based(images, text, text_estimate, target_spreads,
                            style_profile_id, project_id)


def _auto_spread_count(
    images: list[ImageInfo],
    text_estimate: TextEstimate,
) -> int:
    """Automatický odhad počtu spreadů na základě obsahu."""
    # Z textu
    text_spreads = text_estimate.estimated_total_spreads

    # Z fotek — každá supporting/detail fotka potřebuje místo
    # Hero = 1 spread (opening), supporting ~ 0.5 spreadu, detail ~ 0.2
    image_needs = 1  # opening
    for img in images:
        if img.priority == ImagePriority.SUPPORTING:
            image_needs += 0.5
        elif img.priority == ImagePriority.DETAIL:
            image_needs += 0.2

    # Vzít maximum z textu a fotek
    total = max(text_spreads, ceil(image_needs))
    return max(MIN_SPREADS, min(total, MAX_SPREADS))


def _plan_rule_based(
    images: list[ImageInfo],
    text: ArticleText,
    text_estimate: TextEstimate,
    target_spreads: int,
    style_profile_id: str,
    project_id: str,
) -> LayoutPlan:
    """Rule-based plánování — deterministické přiřazení patterns, fotek a textu."""
    spreads: list[PlannedSpread] = []
    remaining_images = list(images)
    remaining_body = list(text.body_paragraphs)
    remaining_captions = list(text.captions)

    # --- 1. Opening spread ---
    hero_imgs = [i for i in remaining_images if i.priority == ImagePriority.HERO]
    hero = hero_imgs[0] if hero_imgs else (remaining_images[0] if remaining_images else None)

    opening = PlannedSpread(
        spread_index=0,
        pattern_id="opening_fullbleed",
        spread_type=SpreadType.OPENING,
        assigned_images=[hero.path] if hero else [],
        assigned_image_infos=[hero] if hero else [],
        assigned_text_sections=["headline", "deck", "byline"],
        notes=f"Opening: hero {hero.filename if hero else 'N/A'}, "
              f"{hero.width}×{hero.height}px" if hero else "Opening: bez hero fotky",
    )
    spreads.append(opening)
    if hero and hero in remaining_images:
        remaining_images.remove(hero)

    # --- 2. Body spreads ---
    body_spread_count = target_spreads - 2  # -opening -closing
    body_spread_count = max(1, body_spread_count)

    # Rozdělit body text na dávky pro jednotlivé spready
    body_text_chunks = _split_text_to_spreads(remaining_body, body_spread_count)

    # Rozdělit fotky na dávky
    image_chunks = _distribute_images(remaining_images, body_spread_count)

    for i in range(body_spread_count):
        chunk_images = image_chunks[i] if i < len(image_chunks) else []
        chunk_text = body_text_chunks[i] if i < len(body_text_chunks) else []
        chunk_caption = []
        if remaining_captions:
            # Přiřadit captions k fotkám v tomto spreadu
            for _ in chunk_images:
                if remaining_captions:
                    chunk_caption.append(remaining_captions.pop(0))

        # Vybrat pattern podle obsahu
        pattern_id = _select_body_pattern(chunk_images, chunk_text, chunk_caption)

        text_sections = []
        if chunk_text:
            text_sections.append(f"body_{i}")
        if chunk_caption:
            text_sections.extend(f"caption_{j}" for j in range(len(chunk_caption)))

        # Pull quote — max 1 na spread, jen pokud máme
        if text.pull_quotes and i < len(text.pull_quotes):
            text_sections.append(f"pull_quote_{i}")

        spread = PlannedSpread(
            spread_index=i + 1,
            pattern_id=pattern_id,
            spread_type=_pattern_to_spread_type(pattern_id),
            assigned_images=[img.path for img in chunk_images],
            assigned_image_infos=chunk_images,
            assigned_text_sections=text_sections,
            notes=f"Body {i+1}: {len(chunk_images)} fotek, "
                  f"~{sum(len(p) for p in chunk_text)} znaků textu",
        )
        spreads.append(spread)

    # --- 3. Closing spread ---
    closing_images = remaining_images[:2] if remaining_images else []
    closing = PlannedSpread(
        spread_index=len(spreads),
        pattern_id="closing",
        spread_type=SpreadType.CLOSING,
        assigned_images=[img.path for img in closing_images],
        assigned_image_infos=closing_images,
        assigned_text_sections=["closing_text", "bio", "credits"],
        notes=f"Closing: {len(closing_images)} fotek, bio/credits",
    )
    spreads.append(closing)

    total_pages = sum(2 for _ in spreads)  # Každý spread = 2 stránky

    plan = LayoutPlan(
        project_id=project_id,
        style_profile=style_profile_id,
        total_pages=total_pages,
        spreads=spreads,
    )

    logger.info(
        "Rule-based plán: %d spreadů, %d stránek, %d fotek přiřazeno",
        len(spreads), total_pages, sum(len(s.assigned_images) for s in spreads),
    )
    return plan


def _split_text_to_spreads(
    paragraphs: list[str],
    num_spreads: int,
) -> list[list[str]]:
    """Rozdělí paragrafy textu rovnoměrně do spreadů."""
    if not paragraphs or num_spreads <= 0:
        return [[] for _ in range(num_spreads)]

    # Rozdělit podle počtu znaků (ne počtu paragrafů)
    total_chars = sum(len(p) for p in paragraphs)
    chars_per_spread = total_chars / num_spreads if num_spreads > 0 else total_chars

    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_chars = 0

    for para in paragraphs:
        current_chunk.append(para)
        current_chars += len(para)

        if current_chars >= chars_per_spread and len(chunks) < num_spreads - 1:
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0

    # Poslední chunk
    if current_chunk:
        chunks.append(current_chunk)

    # Doplnit prázdné chunky pokud jich je méně než spreadů
    while len(chunks) < num_spreads:
        chunks.append([])

    return chunks


def _distribute_images(
    images: list[ImageInfo],
    num_spreads: int,
) -> list[list[ImageInfo]]:
    """Distribuuje fotky do spreadů. Velké fotky dostanou vlastní spread."""
    if not images or num_spreads <= 0:
        return [[] for _ in range(num_spreads)]

    chunks: list[list[ImageInfo]] = [[] for _ in range(num_spreads)]

    # Seřadit: supporting first (hero je už v opening), detail last
    priority_order = {ImagePriority.SUPPORTING: 0, ImagePriority.DETAIL: 1, ImagePriority.HERO: 2}
    sorted_imgs = sorted(images, key=lambda i: priority_order.get(i.priority, 9))

    # Round-robin distribuce s preferencí pro photo_dominant spreads
    spread_idx = 0
    for img in sorted_imgs:
        chunks[spread_idx % num_spreads].append(img)
        # Supporting fotky → posunout spread (každá dostane "prominence")
        if img.priority == ImagePriority.SUPPORTING:
            spread_idx += 1
        # Detail fotky → seskupit (2-3 na spread)
        elif img.priority == ImagePriority.DETAIL:
            if len(chunks[spread_idx % num_spreads]) >= 3:
                spread_idx += 1

    return chunks


def _select_body_pattern(
    images: list[ImageInfo],
    text_chunks: list[str],
    captions: list[str],
) -> str:
    """Vybere vhodný pattern pro body spread podle obsahu."""
    num_images = len(images)
    text_chars = sum(len(p) for p in text_chunks)

    # Hodně fotek → photo grid
    if num_images >= 3:
        return "photo_grid_3x2"

    # Jedna velká fotka, málo textu → photo dominant
    if (num_images == 1
        and images[0].priority == ImagePriority.SUPPORTING
        and images[0].orientation == ImageOrientation.LANDSCAPE
        and text_chars < 2000):
        return "photo_dominant"

    # Fotka + text → mixed
    if num_images >= 1 and text_chars >= 500:
        # Pokud fotka je landscape → top photo varianta
        if images[0].orientation == ImageOrientation.LANDSCAPE:
            return "body_mixed_top_photo"
        return "body_mixed_2col"

    # Hodně textu, málo fotek → text heavy
    if text_chars >= 1500:
        return "body_text_3col"

    # Default
    if num_images >= 1:
        return "body_mixed_2col"

    return "body_text_3col"


def _pattern_to_spread_type(pattern_id: str) -> SpreadType:
    """Mapuje pattern ID na SpreadType."""
    pattern = get_pattern(pattern_id)
    if pattern:
        return pattern.spread_type

    # Fallback mapping
    mapping = {
        "opening_fullbleed": SpreadType.OPENING,
        "big_picture": SpreadType.BIG_PICTURE,
        "body_mixed_2col": SpreadType.BODY_MIXED,
        "body_mixed_top_photo": SpreadType.BODY_MIXED,
        "body_text_3col": SpreadType.BODY_TEXT,
        "photo_grid_3x2": SpreadType.PHOTO_GRID,
        "photo_dominant": SpreadType.PHOTO_DOMINANT,
        "closing": SpreadType.CLOSING,
        "cover": SpreadType.COVER,
    }
    return mapping.get(pattern_id, SpreadType.BODY_MIXED)


# === AI-assisted plánování ===

_AI_SYSTEM_PROMPT = """Jsi expert na magazine layout design pro National Geographic.
Navrhni optimální sekvenci spreadů pro reportáž.

Dostupné spread patterns:
- opening_fullbleed: Opening spread — full-bleed foto + overlay titulek (1 hero fotka)
- big_picture: Celostránková fotka + caption (1 fotka, min text)
- body_mixed_2col: 2 sloupce textu + fotka vpravo (1-2 fotky, 500+ znaků)
- body_mixed_top_photo: Fotka nahoře + text dole (1-2 fotky, 300+ znaků)
- body_text_3col: 3 sloupce textu + malá fotka (0-1 fotka, 1500+ znaků)
- photo_grid_3x2: Mřížka 3-6 fotek + captions (3-6 fotek)
- photo_dominant: Dominantní fotka + text vpravo (1 fotka)
- closing: Závěrečný spread — text + bio/credits (0-2 fotky)

Pravidla:
- VŽDY začni opening_fullbleed s hero fotkou
- VŽDY konči closing
- Prostřídej vizuálně bohaté a text-heavy spready
- Velké landscape fotky → big_picture nebo photo_dominant
- Skupiny detailních fotek → photo_grid
- Respektuj minimální počty fotek a textu pro každý pattern"""

_AI_USER_TEMPLATE = """Navrhni layout pro reportáž:

Fotky ({num_images}):
{image_list}

Text:
- Headline: {headline_len} znaků
- Deck: {deck_len} znaků
- Body: {body_chars} znaků ({body_paragraphs} paragrafů)
- Captions: {num_captions}
- Pull quotes: {num_pullquotes}

Cílový počet spreadů: {target_spreads}
Styl: {style}

Vrať POUZE JSON pole (bez markdown):
[
  {{"spread_index": 0, "pattern_id": "opening_fullbleed", "image_indices": [0], "notes": "hero landscape"}},
  ...
]
Kde image_indices jsou indexy fotek z výše uvedeného seznamu (0-based)."""


def _plan_ai(
    images: list[ImageInfo],
    text: ArticleText,
    text_estimate: TextEstimate,
    target_spreads: int,
    style_profile_id: str,
    project_id: str,
    api_key: Optional[str] = None,
) -> Optional[LayoutPlan]:
    """AI-assisted plánování pomocí Engine abstrakce."""
    from core.engine import get_engine, MODEL_SONNET
    from core.traces import TraceCollector, get_trace_store

    engine = get_engine()
    if not engine.health():
        logger.warning("Engine nedostupný, přeskakuji AI plánování")
        return None

    collector = TraceCollector(engine, get_trace_store(), module="layout_planner")

    # Sestavit popis fotek
    image_lines = []
    for i, img in enumerate(images):
        image_lines.append(
            f"  [{i}] {img.filename}: {img.width}×{img.height}px, "
            f"{img.orientation.value}, priority={img.priority.value}"
        )
    image_list = "\n".join(image_lines) if image_lines else "  (žádné fotky)"

    user_msg = _AI_USER_TEMPLATE.format(
        num_images=len(images),
        image_list=image_list,
        headline_len=len(text.headline),
        deck_len=len(text.deck),
        body_chars=text.total_body_chars,
        body_paragraphs=len(text.body_paragraphs),
        num_captions=len(text.captions),
        num_pullquotes=len(text.pull_quotes),
        target_spreads=target_spreads,
        style=style_profile_id,
    )

    try:
        result = collector.generate(
            messages=[{"role": "user", "content": user_msg}],
            model=MODEL_SONNET,
            system=_AI_SYSTEM_PROMPT,
            max_tokens=2000,
        )
        raw = result.content.strip()
        logger.info("AI layout response (%.1fs, $%.4f): %s",
                     result.latency_seconds, result.cost_usd, raw[:200])

        # Parsovat JSON
        ai_spreads = json.loads(raw)
        return _convert_ai_plan(ai_spreads, images, text, style_profile_id, project_id)

    except json.JSONDecodeError as e:
        logger.warning("AI vrátilo nevalidní JSON: %s", e)
        return None
    except Exception as e:
        logger.warning("AI plánování selhalo: %s", e)
        return None


def _convert_ai_plan(
    ai_spreads: list[dict],
    images: list[ImageInfo],
    text: ArticleText,
    style_profile_id: str,
    project_id: str,
) -> Optional[LayoutPlan]:
    """Konvertuje AI JSON výstup na LayoutPlan s validací."""
    spreads: list[PlannedSpread] = []
    used_image_indices: set[int] = set()

    for item in ai_spreads:
        pattern_id = item.get("pattern_id", "body_mixed_2col")
        image_indices = item.get("image_indices", [])
        notes = item.get("notes", "")

        # Validace pattern_id
        pattern = get_pattern(pattern_id)
        if not pattern:
            logger.warning("AI navrhlo neznámý pattern: %s, fallback na body_mixed_2col", pattern_id)
            pattern_id = "body_mixed_2col"
            pattern = get_pattern(pattern_id)

        # Přiřadit fotky
        spread_images: list[ImageInfo] = []
        for idx in image_indices:
            if isinstance(idx, int) and 0 <= idx < len(images) and idx not in used_image_indices:
                spread_images.append(images[idx])
                used_image_indices.add(idx)

        # Validace: respektuj min/max images patternu
        if pattern and len(spread_images) > pattern.max_images:
            spread_images = spread_images[:pattern.max_images]

        spread = PlannedSpread(
            spread_index=len(spreads),
            pattern_id=pattern_id,
            spread_type=_pattern_to_spread_type(pattern_id),
            assigned_images=[img.path for img in spread_images],
            assigned_image_infos=spread_images,
            notes=f"[AI] {notes}",
        )
        spreads.append(spread)

    if not spreads:
        return None

    # Přiřadit text sekce
    _assign_text_sections(spreads, text)

    total_pages = sum(2 for _ in spreads)

    plan = LayoutPlan(
        project_id=project_id,
        style_profile=style_profile_id,
        total_pages=total_pages,
        spreads=spreads,
    )

    logger.info("AI plán: %d spreadů, %d stránek", len(spreads), total_pages)
    return plan


def _assign_text_sections(spreads: list[PlannedSpread], text: ArticleText) -> None:
    """Přiřadí textové sekce ke spreadům z AI plánu."""
    body_chunks = _split_text_to_spreads(
        text.body_paragraphs,
        max(1, len(spreads) - 2),  # Bez opening a closing
    )

    for i, spread in enumerate(spreads):
        if spread.spread_type == SpreadType.OPENING:
            spread.assigned_text_sections = ["headline", "deck", "byline"]
        elif spread.spread_type == SpreadType.CLOSING:
            spread.assigned_text_sections = ["closing_text", "bio", "credits"]
        else:
            body_idx = i - 1  # Offset za opening
            sections = []
            if 0 <= body_idx < len(body_chunks) and body_chunks[body_idx]:
                sections.append(f"body_{body_idx}")
            spread.assigned_text_sections = sections


# === Convenience function ===

def plan_layout_from_files(
    image_paths: list[str | Path],
    text_content: str,
    style_profile_id: str = "ng_feature",
    num_pages: int | str = "auto",
    project_id: Optional[str] = None,
    use_ai: bool = False,
) -> LayoutPlan:
    """Convenience wrapper: fotky z cest + raw text → LayoutPlan.

    Kombinuje image_analyzer.analyze_batch() + text_parser.parse_article_text() + plan_layout().
    """
    # Analyzovat fotky
    images = analyze_batch([str(p) for p in image_paths])

    # Parsovat text
    article = parse_article_text(text_content)

    # Naplánovat layout
    return plan_layout(
        images=images,
        text=article,
        style_profile_id=style_profile_id,
        num_pages=num_pages,
        project_id=project_id,
        use_ai=use_ai,
    )


def plan_layout_variants(
    images: list[ImageInfo],
    text: ArticleText,
    style_profile_id: str = "ng_feature",
    num_pages: int | str = "auto",
    project_id: Optional[str] = None,
    count: int = 3,
) -> list[LayoutPlan]:
    """Vygeneruje N variant layoutu se různým rozložením fotek.

    Varianta 1: Originální pořadí fotek
    Varianta 2: Shuffled fotky (hero zůstane, zbytek promíchán)
    Varianta 3: Inverzní pořadí (hero zůstane, zbytek obrácen)

    Returns:
        Seznam LayoutPlan variant.
    """
    import random

    variants = []

    # Varianta 1 — originální pořadí
    plan1 = plan_layout(
        images=list(images),
        text=text,
        style_profile_id=style_profile_id,
        num_pages=num_pages,
        project_id=f"{project_id}_v1" if project_id else None,
    )
    variants.append(plan1)

    if count < 2:
        return variants

    # Separovat hero od zbytku
    hero = [img for img in images if img.priority == ImagePriority.HERO]
    non_hero = [img for img in images if img.priority != ImagePriority.HERO]

    # Varianta 2 — shuffled (seed pro reproducibilitu)
    shuffled = list(non_hero)
    random.Random(42).shuffle(shuffled)
    images_v2 = hero + shuffled

    plan2 = plan_layout(
        images=images_v2,
        text=text,
        style_profile_id=style_profile_id,
        num_pages=num_pages,
        project_id=f"{project_id}_v2" if project_id else None,
    )
    variants.append(plan2)

    if count < 3:
        return variants

    # Varianta 3 — inverzní pořadí
    images_v3 = hero + list(reversed(non_hero))
    plan3 = plan_layout(
        images=images_v3,
        text=text,
        style_profile_id=style_profile_id,
        num_pages=num_pages,
        project_id=f"{project_id}_v3" if project_id else None,
    )
    variants.append(plan3)

    logger.info("Vygenerovány %d varianty layoutu", len(variants))
    return variants


# === Multi-article plánování ===

def plan_multi_article_layout(
    multi_text: MultiArticleText,
    image_allocation: dict[str, list[ImageInfo]],
    project_id: Optional[str] = None,
    use_ai: bool = False,
    api_key: Optional[str] = None,
) -> MultiArticlePlan:
    """Naplánuje layout pro více článků — jeden LayoutPlan per article.

    Args:
        multi_text: Kolekce článků (z parse_multi_article_text).
        image_allocation: {article_id: [ImageInfo]} — přiřazení fotek k článkům.
        project_id: ID projektu.
        use_ai: Použít AI pro jednotlivé plány.
        api_key: Anthropic API klíč.

    Returns:
        MultiArticlePlan s jedním LayoutPlan per article a boundary info.
    """
    project_id = project_id or str(uuid.uuid4())[:8]
    article_plans: list[LayoutPlan] = []
    boundaries: list[dict] = []
    cumulative_pages = 0

    for article in multi_text.articles:
        # Konvertovat ArticleItem na ArticleText
        article_text = ArticleText(
            headline=article.headline,
            deck=article.deck,
            byline=article.byline,
            body_paragraphs=article.body_paragraphs,
            captions=article.captions,
            pull_quotes=article.pull_quotes,
            total_body_chars=article.total_body_chars,
            total_chars=article.total_chars,
        )

        # Fotky pro tento článek
        images = image_allocation.get(article.article_id, [])

        # Naplánovat layout pro článek
        plan = plan_layout(
            images=images,
            text=article_text,
            style_profile_id=article.style_profile_id,
            project_id=f"{project_id}_{article.article_id}",
            use_ai=use_ai,
            api_key=api_key,
        )

        # Přečíslovat spread_index s offsetem
        for spread in plan.spreads:
            spread.spread_index += cumulative_pages // 2

        article_plans.append(plan)

        start_page = cumulative_pages + 1
        end_page = cumulative_pages + plan.total_pages
        boundaries.append({
            "article_id": article.article_id,
            "headline": article.headline,
            "style_profile_id": article.style_profile_id,
            "start_page": start_page,
            "end_page": end_page,
            "spread_count": len(plan.spreads),
        })
        cumulative_pages += plan.total_pages

    total_pages = cumulative_pages

    logger.info(
        "Multi-article plán: %d článků, %d stránek celkem, hranice: %s",
        len(article_plans), total_pages,
        [(b["article_id"], b["start_page"], b["end_page"]) for b in boundaries],
    )

    return MultiArticlePlan(
        project_id=project_id,
        total_pages=total_pages,
        article_plans=article_plans,
        article_boundaries=boundaries,
    )
