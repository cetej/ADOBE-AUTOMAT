"""Template Analyzer — reverse-engineering IDML layoutů.

Parsuje existující NG IDML soubory a extrahuje layout pravidla:
- Rozměry stránek, marginy, grid systém
- Pozice a velikosti všech rámců (text/image)
- Typografické styly
- Klasifikaci rámců a spreadů
"""

import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Přidej parent pro importy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models_layout import (
    Bounds, FrameSpec, FrameType, PageSpec, SpreadAnalysis,
    SpreadType, StyleInfo, TemplateAnalysis
)

NS = {'idPkg': 'http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging'}

# Mapování paragraph stylů na typy rámců
STYLE_TO_FRAME_TYPE = {
    # Headlines
    'Headline': FrameType.HEADLINE,
    'FEA_Head': FrameType.HEADLINE,
    'Head': FrameType.HEADLINE,
    # Decks
    'Deck': FrameType.DECK,
    'FEA_Deck': FrameType.DECK,
    'Display': FrameType.DECK,
    # Bylines
    'Byline': FrameType.BYLINE,
    'FEA_Byline': FrameType.BYLINE,
    # Body text
    'Body': FrameType.BODY_TEXT,
    'ALL_Body': FrameType.BODY_TEXT,
    'FEA_Body': FrameType.BODY_TEXT,
    # Captions
    'Caption': FrameType.CAPTION,
    'ALL_Caption': FrameType.CAPTION,
    # Pull quotes / callouts
    'Callout': FrameType.PULL_QUOTE,
    'FEA_Callout': FrameType.PULL_QUOTE,
    # Credits
    'Credit': FrameType.CREDIT,
    'ALL_Credit': FrameType.CREDIT,
    # Footers
    'Footer': FrameType.FOLIO,
    'FEA_Footer': FrameType.FOLIO,
    # Bio
    'Bio': FrameType.SIDEBAR,
    'ALL_Bio': FrameType.SIDEBAR,
    # Map/Art labels
    'ART_': FrameType.MAP_LABEL,
    'Map': FrameType.MAP_LABEL,
    # Cover
    'COV_': FrameType.COVER_LINE,
    'COVER': FrameType.COVER_LINE,
    # NGS Grant note
    'NGS': FrameType.SIDEBAR,
}


def parse_transform(transform_str: str) -> dict:
    """Parsuje ItemTransform='a b c d tx ty' na dict."""
    parts = [float(x) for x in transform_str.split()]
    if len(parts) != 6:
        return {'a': 1, 'b': 0, 'c': 0, 'd': 1, 'tx': 0, 'ty': 0}
    return {
        'a': parts[0], 'b': parts[1],
        'c': parts[2], 'd': parts[3],
        'tx': parts[4], 'ty': parts[5]
    }


def apply_transform(x: float, y: float, t: dict) -> tuple[float, float]:
    """Aplikuje afinní transformaci na bod."""
    return (
        t['a'] * x + t['c'] * y + t['tx'],
        t['b'] * x + t['d'] * y + t['ty']
    )


def get_frame_bounds(elem, transform: dict) -> Optional[Bounds]:
    """Vypočítá absolutní bounds rámce z PathPointArray + ItemTransform."""
    points = []
    for pp in elem.iter('PathPointType'):
        anchor = pp.get('Anchor', '0 0').split()
        if len(anchor) >= 2:
            x, y = float(anchor[0]), float(anchor[1])
            abs_x, abs_y = apply_transform(x, y, transform)
            points.append((abs_x, abs_y))

    if not points:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Bounds(
        x=min(xs), y=min(ys),
        width=max(xs) - min(xs),
        height=max(ys) - min(ys)
    )


def classify_frame_by_style(story_id: str, stories_data: dict) -> FrameType:
    """Klasifikuje rámec podle paragraph stylu v příslušném story."""
    if story_id not in stories_data:
        return FrameType.UNKNOWN

    style_name = stories_data[story_id].get('primary_style', '')

    for pattern, frame_type in STYLE_TO_FRAME_TYPE.items():
        if pattern in style_name:
            return frame_type

    return FrameType.UNKNOWN


def classify_image_frame(bounds: Bounds, page_width: float, page_height: float,
                         spread_width: float) -> FrameType:
    """Klasifikuje image rámec podle velikosti — hero vs body."""
    spread_area = spread_width * page_height
    frame_area = bounds.area

    # Full-bleed = pokrývá 60%+ spreadu
    if frame_area > spread_area * 0.6:
        return FrameType.HERO_IMAGE
    return FrameType.BODY_IMAGE


def classify_spread(text_frames: list[FrameSpec], image_frames: list[FrameSpec],
                    page_width: float, page_height: float,
                    num_pages: int) -> SpreadType:
    """Klasifikuje spread podle obsahu rámců."""
    spread_area = page_width * num_pages * page_height

    # Plochy
    total_text_area = sum(f.bounds.area for f in text_frames
                          if f.frame_type not in (FrameType.FOLIO, FrameType.CREDIT))
    total_image_area = sum(f.bounds.area for f in image_frames)

    text_ratio = total_text_area / spread_area if spread_area > 0 else 0
    image_ratio = total_image_area / spread_area if spread_area > 0 else 0

    has_hero = any(f.frame_type == FrameType.HERO_IMAGE for f in image_frames)
    has_headline = any(f.frame_type == FrameType.HEADLINE for f in text_frames)
    has_deck = any(f.frame_type == FrameType.DECK for f in text_frames)
    has_map = any(f.frame_type == FrameType.MAP_LABEL for f in text_frames)
    has_cover_line = any(f.frame_type == FrameType.COVER_LINE for f in text_frames)

    body_text_count = sum(1 for f in text_frames if f.frame_type == FrameType.BODY_TEXT)

    # Cover
    if has_cover_line:
        return SpreadType.COVER

    # Map/infographic — hodně malých text frames (labels)
    if has_map or len(text_frames) > 12:
        return SpreadType.MAP_INFOGRAPHIC

    # Opening — hero image + headline/deck, málo body textu
    if has_hero and (has_headline or has_deck) and body_text_count <= 1:
        return SpreadType.OPENING

    # Big Picture — hero image, skoro žádný text
    if has_hero and text_ratio < 0.05:
        return SpreadType.BIG_PICTURE

    # Photo dominant — velká fotka + trochu textu (captions)
    if has_hero and text_ratio < 0.15:
        return SpreadType.PHOTO_DOMINANT

    # Photo grid — hodně obrázků
    if len(image_frames) >= 3:
        return SpreadType.PHOTO_GRID

    # Body text heavy
    if text_ratio > 0.3 and image_ratio < 0.15:
        return SpreadType.BODY_TEXT

    # Closing — bio, credits, menší fotky
    if any(f.frame_type == FrameType.SIDEBAR for f in text_frames):
        return SpreadType.CLOSING

    # Default — mixed
    return SpreadType.BODY_MIXED


def parse_stories(idml_dir: str) -> dict:
    """Parsuje Stories/*.xml a vrací dict {story_id: {primary_style, text_preview}}."""
    stories = {}
    stories_dir = os.path.join(idml_dir, 'Stories')
    if not os.path.exists(stories_dir):
        return stories

    for fname in os.listdir(stories_dir):
        if not fname.endswith('.xml'):
            continue
        try:
            tree = ET.parse(os.path.join(stories_dir, fname))
            root = tree.getroot()

            for story in root.iter('Story'):
                story_id = story.get('Self', '')
                if not story_id:
                    continue

                # Najdi primární paragraph styl
                styles = []
                text_parts = []
                for psr in story.iter('ParagraphStyleRange'):
                    style = psr.get('AppliedParagraphStyle', '')
                    # Dekóduj style name
                    style = style.replace('ParagraphStyle/', '')
                    style = unquote(style.replace('%3a', ':'))
                    styles.append(style)

                    for content in psr.iter('Content'):
                        if content.text:
                            text_parts.append(content.text)

                # Primární styl = první ne-prázdný
                primary = ''
                for s in styles:
                    if s and not s.startswith('$ID'):
                        primary = s
                        break

                text_preview = ' '.join(text_parts)[:200]
                stories[story_id] = {
                    'primary_style': primary,
                    'all_styles': styles,
                    'text_preview': text_preview,
                    'char_count': sum(len(t) for t in text_parts)
                }
        except ET.ParseError:
            continue

    return stories


def parse_styles(idml_dir: str) -> tuple[list[StyleInfo], list[StyleInfo]]:
    """Parsuje Resources/Styles.xml a vrací paragraph + character styly."""
    styles_path = os.path.join(idml_dir, 'Resources', 'Styles.xml')
    if not os.path.exists(styles_path):
        return [], []

    tree = ET.parse(styles_path)
    root = tree.getroot()

    para_styles = []
    char_styles = []

    for ps in root.iter('ParagraphStyle'):
        name = ps.get('Name', '')
        if not name or name.startswith('$ID'):
            continue

        font = ''
        for af in ps.iter('AppliedFont'):
            font = af.text or ''

        leading = None
        for l in ps.iter('Leading'):
            try:
                leading = float(l.text) if l.text else None
            except (ValueError, TypeError):
                pass

        para_styles.append(StyleInfo(
            style_name=unquote(name.replace('%3a', ':')),
            font_family=font or None,
            font_style=ps.get('FontStyle') or None,
            point_size=float(ps.get('PointSize')) if ps.get('PointSize') else None,
            tracking=int(float(ps.get('Tracking'))) if ps.get('Tracking') else None,
            leading=leading,
            capitalization=ps.get('Capitalization') or None,
            fill_color=ps.get('FillColor') or None,
        ))

    for cs in root.iter('CharacterStyle'):
        name = cs.get('Name', '')
        if not name or name.startswith('$ID'):
            continue

        font = ''
        for af in cs.iter('AppliedFont'):
            font = af.text or ''

        char_styles.append(StyleInfo(
            style_name=unquote(name.replace('%3a', ':')),
            font_family=font or None,
            font_style=cs.get('FontStyle') or None,
            point_size=float(cs.get('PointSize')) if cs.get('PointSize') else None,
            tracking=int(float(cs.get('Tracking'))) if cs.get('Tracking') else None,
            capitalization=cs.get('Capitalization') or None,
        ))

    return para_styles, char_styles


def analyze_spread(spread_path: str, spread_index: int,
                   stories_data: dict, page_width: float,
                   page_height: float) -> Optional[SpreadAnalysis]:
    """Analyzuje jeden spread XML soubor."""
    try:
        tree = ET.parse(spread_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    spread_el = root.find('Spread')
    if spread_el is None:
        return None

    spread_id = spread_el.get('Self', '')

    # Parsuj stránky
    pages = []
    for page in spread_el.findall('Page'):
        gb = page.get('GeometricBounds', '0 0 720 495').split()
        margin = page.find('MarginPreference')

        pages.append(PageSpec(
            page_name=page.get('Name', '?'),
            width=float(gb[3]) if len(gb) > 3 else page_width,
            height=float(gb[2]) if len(gb) > 2 else page_height,
            margin_top=float(margin.get('Top', 0)) if margin is not None else 0,
            margin_bottom=float(margin.get('Bottom', 0)) if margin is not None else 0,
            margin_left=float(margin.get('Left', 0)) if margin is not None else 0,
            margin_right=float(margin.get('Right', 0)) if margin is not None else 0,
            column_count=int(float(margin.get('ColumnCount', 1))) if margin is not None else 1,
            column_gutter=float(margin.get('ColumnGutter', 0)) if margin is not None else 0,
        ))

    if not pages:
        return None

    num_pages = len(pages)
    spread_width = sum(p.width for p in pages)

    # Parsuj rámce — přímí potomci spreadu + rámce v Groups
    text_frames = []
    image_frames = []
    all_frames = []

    def process_frame(elem, parent_transform=None):
        """Zpracuje TextFrame nebo Rectangle."""
        t = parse_transform(elem.get('ItemTransform', '1 0 0 1 0 0'))

        # Pokud je v groupě, kombinuj transformace
        if parent_transform:
            # Zjednodušená kompozice — stačí pro většinu NG layoutů
            t['tx'] = parent_transform['a'] * t['tx'] + parent_transform['c'] * t['ty'] + parent_transform['tx']
            t['ty'] = parent_transform['b'] * t['tx'] + parent_transform['d'] * t['ty'] + parent_transform['ty']
            t['a'] *= parent_transform['a']
            t['d'] *= parent_transform['d']

        bounds = get_frame_bounds(elem, t)
        if bounds is None or bounds.width < 5 or bounds.height < 5:
            return

        if elem.tag == 'TextFrame':
            story_id = elem.get('ParentStory', '')
            frame_type = classify_frame_by_style(story_id, stories_data)

            # Relativní pozice vůči spreadu
            rel_x = (bounds.x + spread_width / 2) / spread_width
            rel_y = (bounds.y + page_height / 2) / page_height

            frame = FrameSpec(
                frame_id=elem.get('Self', ''),
                frame_type=frame_type,
                bounds=bounds,
                story_id=story_id,
                paragraph_style=stories_data.get(story_id, {}).get('primary_style', ''),
                text_content=stories_data.get(story_id, {}).get('text_preview', ''),
                rel_x=max(0, min(1, rel_x)),
                rel_y=max(0, min(1, rel_y)),
                rel_width=min(1, bounds.width / spread_width),
                rel_height=min(1, bounds.height / page_height),
            )
            text_frames.append(frame)
            all_frames.append(frame)

        elif elem.tag == 'Rectangle' and elem.get('ContentType') == 'GraphicType':
            frame_type = classify_image_frame(bounds, page_width, page_height, spread_width)

            # Linked file
            linked = None
            for link in elem.iter('Link'):
                uri = link.get('LinkResourceURI', '')
                if uri:
                    linked = unquote(uri.split('/')[-1])

            rel_x = (bounds.x + spread_width / 2) / spread_width
            rel_y = (bounds.y + page_height / 2) / page_height

            frame = FrameSpec(
                frame_id=elem.get('Self', ''),
                frame_type=frame_type,
                bounds=bounds,
                linked_file=linked,
                rel_x=max(0, min(1, rel_x)),
                rel_y=max(0, min(1, rel_y)),
                rel_width=min(1, bounds.width / spread_width),
                rel_height=min(1, bounds.height / page_height),
            )
            image_frames.append(frame)
            all_frames.append(frame)

    # Přímí potomci spreadu
    for tf in spread_el.findall('TextFrame'):
        process_frame(tf)
    for rect in spread_el.findall('Rectangle'):
        if rect.get('ContentType') == 'GraphicType':
            process_frame(rect)

    # Rámce v Groups
    for group in spread_el.findall('Group'):
        gt = parse_transform(group.get('ItemTransform', '1 0 0 1 0 0'))
        for tf in group.iter('TextFrame'):
            process_frame(tf, gt)
        for rect in group.iter('Rectangle'):
            if rect.get('ContentType') == 'GraphicType':
                process_frame(rect, gt)

    # Klasifikace spreadu
    spread_type = classify_spread(text_frames, image_frames,
                                  page_width, page_height, num_pages)

    # Statistiky
    spread_area = spread_width * page_height
    text_area = sum(f.bounds.area for f in text_frames
                    if f.frame_type not in (FrameType.FOLIO, FrameType.CREDIT))
    image_area = sum(f.bounds.area for f in image_frames)

    has_bleed = any(
        f.bounds.width > spread_width * 0.95 or
        f.bounds.height > page_height * 0.95
        for f in image_frames
    )

    return SpreadAnalysis(
        spread_index=spread_index,
        spread_id=spread_id,
        spread_type=spread_type,
        pages=pages,
        frames=all_frames,
        text_frame_count=len(text_frames),
        image_frame_count=len(image_frames),
        text_area_ratio=text_area / spread_area if spread_area > 0 else 0,
        image_area_ratio=image_area / spread_area if spread_area > 0 else 0,
        has_bleed_image=has_bleed,
    )


def analyze_idml(idml_path: str, output_dir: Optional[str] = None) -> TemplateAnalysis:
    """Hlavní funkce — analyzuje IDML soubor a vrátí TemplateAnalysis.

    Args:
        idml_path: Cesta k IDML souboru
        output_dir: Volitelně — kam uložit JSON výstup

    Returns:
        TemplateAnalysis s kompletním popisem layoutu
    """
    idml_path = Path(idml_path)
    if not idml_path.exists():
        raise FileNotFoundError(f"IDML soubor nenalezen: {idml_path}")

    # Rozbal IDML do temp adresáře
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(idml_path, 'r') as z:
            z.extractall(tmp_dir)

        # Parsuj designmap — pořadí spreadů
        dm_path = os.path.join(tmp_dir, 'designmap.xml')
        dm_tree = ET.parse(dm_path)
        dm_root = dm_tree.getroot()

        spread_srcs = [
            s.get('src') for s in dm_root.findall('idPkg:Spread', NS)
        ]

        # Parsuj stories
        stories_data = parse_stories(tmp_dir)

        # Parsuj styly
        para_styles, char_styles = parse_styles(tmp_dir)

        # Analyzuj první spread pro rozměry stránky
        first_spread_path = os.path.join(tmp_dir, spread_srcs[0])
        first_tree = ET.parse(first_spread_path)
        first_page = first_tree.find('.//Page')
        if first_page is not None:
            gb = first_page.get('GeometricBounds', '0 0 720 495').split()
            page_height = float(gb[2])
            page_width = float(gb[3])
        else:
            page_height = 720.0
            page_width = 495.0

        # Analyzuj všechny spready
        spreads = []
        for i, src in enumerate(spread_srcs):
            spread_path = os.path.join(tmp_dir, src)
            analysis = analyze_spread(spread_path, i, stories_data,
                                      page_width, page_height)
            if analysis:
                spreads.append(analysis)

        # Celkový počet stránek
        total_pages = sum(len(s.pages) for s in spreads)

        # Distribuce typů spreadů
        type_dist = {}
        for s in spreads:
            key = s.spread_type.value
            type_dist[key] = type_dist.get(key, 0) + 1

        # Průměrné poměry
        avg_text = sum(s.text_area_ratio for s in spreads) / len(spreads) if spreads else 0
        avg_image = sum(s.image_area_ratio for s in spreads) / len(spreads) if spreads else 0

        # Detekce typu dokumentu
        doc_type = detect_document_type(idml_path.name, spreads)

        result = TemplateAnalysis(
            source_file=idml_path.name,
            document_type=doc_type,
            page_width=page_width,
            page_height=page_height,
            page_count=total_pages,
            spread_count=len(spreads),
            spreads=spreads,
            paragraph_styles=para_styles,
            character_styles=char_styles,
            avg_text_ratio=avg_text,
            avg_image_ratio=avg_image,
            spread_type_distribution=type_dist,
        )

        # Ulož JSON pokud je output_dir
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            out_file = out_path / f"{idml_path.stem}_analysis.json"
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
            print(f"Analýza uložena: {out_file}")

        return result


def detect_document_type(filename: str, spreads: list[SpreadAnalysis]) -> str:
    """Detekuje typ dokumentu z názvu a obsahu."""
    fn = filename.upper()

    if 'CV ' in fn or 'COVER' in fn:
        return 'cover'
    if 'TC ' in fn or 'TOC' in fn:
        return 'toc'
    if 'PG ' in fn or 'PAGE GUIDE' in fn:
        return 'frontmatter'
    if 'EP ' in fn or 'EDITOR' in fn:
        return 'frontmatter'
    if 'BP ' in fn or 'BIG PICTURE' in fn:
        return 'frontmatter'
    if 'OUR WORLD' in fn or 'OW ' in fn:
        return 'frontmatter'
    if 'MF ' in fn or 'MF_' in fn:
        return 'medium_feature'

    # Feature = má opening spread + body
    has_opening = any(s.spread_type == SpreadType.OPENING for s in spreads)
    if has_opening and len(spreads) >= 4:
        return 'feature'

    return 'unknown'


def print_analysis_summary(analysis: TemplateAnalysis):
    """Vytiskne čitelný souhrn analýzy."""
    print(f"\n{'=' * 70}")
    print(f"📄 {analysis.source_file}")
    print(f"   Typ: {analysis.document_type} | Stránky: {analysis.page_count} | "
          f"Spready: {analysis.spread_count}")
    print(f"   Stránka: {analysis.page_width}×{analysis.page_height} pt")
    print(f"   Ø text: {analysis.avg_text_ratio:.1%} | Ø obrázky: {analysis.avg_image_ratio:.1%}")
    print(f"   Distribuce: {analysis.spread_type_distribution}")
    print()

    for s in analysis.spreads:
        pages = ', '.join(p.page_name for p in s.pages)
        bleed = " 🖼️BLEED" if s.has_bleed_image else ""
        print(f"   Spread {s.spread_index} (pg {pages}): {s.spread_type.value}{bleed}")
        print(f"     TF: {s.text_frame_count} | IMG: {s.image_frame_count} | "
              f"text {s.text_area_ratio:.1%} | img {s.image_area_ratio:.1%}")

        # Hlavní rámce (ne folio/credit)
        main_frames = [f for f in s.frames
                       if f.frame_type not in (FrameType.FOLIO, FrameType.CREDIT, FrameType.UNKNOWN)
                       and f.bounds.area > 1000]
        for f in main_frames[:6]:
            extra = f" → {f.linked_file}" if f.linked_file else ""
            extra += f" [{f.paragraph_style}]" if f.paragraph_style else ""
            extra += f" «{f.text_content[:50]}»" if f.text_content else ""
            print(f"       {f.frame_type.value}: {f.bounds.width:.0f}×{f.bounds.height:.0f}pt{extra}")


# CLI — spuštění přímo pro testování
if __name__ == '__main__':
    import glob

    # Kořen projektu = 3 úrovně nad tímto souborem (backend/services/layout/)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    samples_dir = project_root / 'input' / 'samples'
    output_dir = project_root / 'data' / 'templates'

    if len(sys.argv) > 1:
        # Analyzuj konkrétní soubor
        path = sys.argv[1]
        analysis = analyze_idml(path, str(output_dir))
        print_analysis_summary(analysis)
    else:
        # Analyzuj všechny IDML v samples
        idml_files = sorted(samples_dir.glob('*.idml'))
        print(f"Nalezeno {len(idml_files)} IDML souborů v {samples_dir}\n")

        all_analyses = []
        for idml_file in idml_files:
            try:
                analysis = analyze_idml(str(idml_file), str(output_dir))
                print_analysis_summary(analysis)
                all_analyses.append(analysis)
            except Exception as e:
                print(f"❌ Chyba při analýze {idml_file.name}: {e}")

        # Souhrnná statistika
        if all_analyses:
            print(f"\n{'=' * 70}")
            print(f"📊 SOUHRN — {len(all_analyses)} dokumentů analyzováno")
            all_types = {}
            for a in all_analyses:
                for k, v in a.spread_type_distribution.items():
                    all_types[k] = all_types.get(k, 0) + v
            print(f"   Celkem spreadů: {sum(a.spread_count for a in all_analyses)}")
            print(f"   Distribuce typů: {json.dumps(all_types, indent=4)}")
