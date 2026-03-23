"""IDML Builder — programatická tvorba validních IDML souborů z layout specifikace.

Strategie: "skeleton IDML" — vezme reálný NG IDML jako základ (obsahuje správné
Resources, Preferences, Fonts, MasterSpreads), odstraní existující Spready a Stories,
vygeneruje nové z layout plánu.

KRITICKÉ PRAVIDLO: NIKDY ElementTree.write() — pouze string construction + ET.fromstring() validace.
"""

import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from html import escape as html_escape
from pathlib import Path
from typing import Optional

from models_layout import (
    Bounds, FrameType, LayoutPlan, MultiArticlePlan, PlannedSpread,
    SlotSpec, SpreadPattern, StyleInfo, StyleProfile,
)
from services.layout.spread_patterns import (
    get_pattern, instantiate_pattern,
)
from services.layout.style_profiles import (
    get_profile, get_style_for_frame_type,
)

logger = logging.getLogger(__name__)

# NG stránka: 495×720 pt, spread = 2 stránky = 990×720 pt
PAGE_WIDTH = 495.0
PAGE_HEIGHT = 720.0
SPREAD_WIDTH = 990.0
SPREAD_HEIGHT = 720.0

# Offset: spread souřadnice mají (0,0) uprostřed spreadu
# Levá stránka: ItemTransform "1 0 0 1 -495 -360"
# Pravá stránka: ItemTransform "1 0 0 1 0 -360"
SPREAD_OFFSET_X = PAGE_WIDTH   # 495 — posun od středu doleva
SPREAD_OFFSET_Y = PAGE_HEIGHT / 2  # 360 — posun od středu nahoru

# Soubory ze skeleton IDML, které se kopírují beze změn
SKELETON_KEEP_PREFIXES = (
    "mimetype",
    "META-INF/",
    "Resources/",
    "MasterSpreads/",
    "XML/",
)


def xml_escape(text: str) -> str:
    """Escapuje text pro vložení do XML <Content>."""
    result = html_escape(text, quote=True)
    result = result.replace("'", "&apos;")
    return result


class UIDGenerator:
    """Generátor unikátních Self ID pro IDML elementy.

    Formát: u{hex} — začíná od vysokého čísla aby se vyhnul kolizím
    s existujícími UID ve skeleton IDML.
    """

    def __init__(self, start: int = 0xA0000):
        self._counter = start

    def next(self) -> str:
        uid = f"u{self._counter:x}"
        self._counter += 1
        return uid

    def next_n(self, n: int) -> list[str]:
        return [self.next() for _ in range(n)]


class IDMLBuilder:
    """Engine pro generování validních IDML souborů z layout specifikace.

    Použití:
        builder = IDMLBuilder(skeleton_idml="input/samples/MF...idml")
        builder.add_spread(pattern, content_map, style_profile)
        builder.add_spread(...)
        output_path = builder.build("output/my_layout.idml")
    """

    def __init__(self, skeleton_idml: str | Path):
        self.skeleton_path = Path(skeleton_idml)
        if not self.skeleton_path.exists():
            raise FileNotFoundError(f"Skeleton IDML not found: {self.skeleton_path}")

        self.uid = UIDGenerator()
        # Generované spready a stories
        self._spreads: list[dict] = []  # {"uid": str, "xml": str, "filename": str}
        self._stories: list[dict] = []  # {"uid": str, "xml": str, "filename": str}
        # Mapování story_uid → story data (pro designmap StoryList)
        self._story_uids: list[str] = []
        # Threaded text frames: story_uid → [frame_uid, ...]
        self._threaded_frames: dict[str, list[str]] = {}

        # Metadata ze skeleton
        self._skeleton_data: dict[str, bytes] = {}
        self._skeleton_designmap: str = ""
        self._skeleton_master_spreads: list[str] = []
        self._load_skeleton()

    def _load_skeleton(self):
        """Načte skeleton IDML a extrahuje infrastrukturní soubory."""
        with zipfile.ZipFile(self.skeleton_path, "r") as z:
            for info in z.infolist():
                name = info.filename
                # Kopírovat infrastrukturní soubory
                if any(name.startswith(p) for p in SKELETON_KEEP_PREFIXES):
                    self._skeleton_data[name] = z.read(name)

                # Designmap — potřebujeme pro extrakci hlavičky a master spreadů
                if name == "designmap.xml":
                    self._skeleton_designmap = z.read(name).decode("utf-8")

                # Preferences — kopírovat
                if name == "Resources/Preferences.xml":
                    self._skeleton_data[name] = z.read(name)

        # Najít master spread reference v designmap
        for match in re.finditer(
            r'<idPkg:MasterSpread\s+src="([^"]+)"',
            self._skeleton_designmap,
        ):
            self._skeleton_master_spreads.append(match.group(1))

        logger.info(
            "Skeleton loaded: %d files, %d master spreads",
            len(self._skeleton_data),
            len(self._skeleton_master_spreads),
        )

    # ----- Spread tvorba -----

    def add_spread(
        self,
        pattern: SpreadPattern,
        content_map: dict[str, str],
        style_profile: StyleProfile,
        image_map: Optional[dict[str, str]] = None,
        page_start: int = 1,
    ) -> str:
        """Přidá spread s obsahem podle patternu.

        Args:
            pattern: Spread pattern definující rozložení slotů.
            content_map: slot_id → text obsah (pro textové sloty).
            style_profile: Typografický profil pro styly.
            image_map: slot_id → cesta k obrázku (pro image sloty).
            page_start: Číslo první stránky (pro folio).

        Returns:
            UID vytvořeného spreadu.
        """
        image_map = image_map or {}
        spread_uid = self.uid.next()

        # Instantiate pattern → absolutní bounds
        slots = instantiate_pattern(pattern, SPREAD_WIDTH, SPREAD_HEIGHT)

        # Generovat stránky
        page_left_uid = self.uid.next()
        page_right_uid = self.uid.next()

        # Generovat frame XML pro každý slot
        frame_xmls = []
        for slot_data in slots:
            slot_id = slot_data["slot_id"]
            slot_type = slot_data["slot_type"]
            bounds: Bounds = slot_data["bounds"]
            default_style = slot_data["default_style"]

            # Textový slot
            if slot_type in (
                FrameType.BODY_TEXT.value, FrameType.HEADLINE.value,
                FrameType.DECK.value, FrameType.BYLINE.value,
                FrameType.CAPTION.value, FrameType.PULL_QUOTE.value,
                FrameType.FOLIO.value, FrameType.CREDIT.value,
                FrameType.SIDEBAR.value, FrameType.COVER_LINE.value,
            ):
                text = content_map.get(slot_id, "")

                # Threaded story: content_map má '_thread:{uid}' hodnotu
                if text.startswith("_thread:"):
                    threaded_uid = text[8:]
                    style_name = default_style or "ALL_Body_Justified"
                    frame_uid = self.uid.next()
                    self._threaded_frames.setdefault(threaded_uid, [])
                    self._threaded_frames[threaded_uid].append(
                        (frame_uid, bounds, style_name, False)
                    )
                    # Placeholder — bude nahrazeno ve _finalize_threading
                    frame_xmls.append(f"__THREAD_{frame_uid}__")
                    continue

                if not text and not slot_data["required"]:
                    continue
                if not text:
                    text = " "  # Placeholder pro required sloty

                # Style resolution
                style_name = default_style or "ALL_Body_Justified"

                # Vytvořit story
                story_uid = self.uid.next()
                story_xml = self._build_story_xml(story_uid, text, style_name)
                story_filename = f"Stories/Story_{story_uid}.xml"
                self._stories.append({
                    "uid": story_uid,
                    "xml": story_xml,
                    "filename": story_filename,
                })
                self._story_uids.append(story_uid)

                # Vytvořit TextFrame
                frame_xml = self._build_text_frame_xml(
                    bounds, story_uid, style_name,
                )
                frame_xmls.append(frame_xml)

            # Image slot
            elif slot_type in (
                FrameType.HERO_IMAGE.value, FrameType.BODY_IMAGE.value,
            ):
                image_path = image_map.get(slot_id, "")
                frame_xml = self._build_image_frame_xml(
                    bounds, image_path, slot_data.get("allow_bleed", False),
                )
                frame_xmls.append(frame_xml)

            # Logo — placeholder rectangle
            elif slot_type == FrameType.LOGO.value:
                frame_xml = self._build_image_frame_xml(bounds, "", False)
                frame_xmls.append(frame_xml)

        # Sestavit spread XML
        spread_xml = self._build_spread_xml(
            spread_uid, page_left_uid, page_right_uid,
            frame_xmls, page_start,
            style_profile,
        )
        spread_filename = f"Spreads/Spread_{spread_uid}.xml"
        self._spreads.append({
            "uid": spread_uid,
            "xml": spread_xml,
            "filename": spread_filename,
        })

        return spread_uid

    def create_threaded_story(
        self,
        text: str,
        paragraph_style: str = "ALL_Body_Justified",
    ) -> str:
        """Vytvoří story pro threaded body text.

        Vrátí story_uid, který pak předáte do content_map
        jako speciální klíč '_thread:{story_uid}' pro body_text sloty.
        Builder propojí TextFrame elementy přes PreviousTextFrame/NextTextFrame.

        Args:
            text: Celý body text článku.
            paragraph_style: Paragraph style pro body text.

        Returns:
            story_uid pro referencování ve spreadech.
        """
        story_uid = self.uid.next()
        story_xml = self._build_story_xml(story_uid, text, paragraph_style)
        self._stories.append({
            "uid": story_uid,
            "xml": story_xml,
            "filename": f"Stories/Story_{story_uid}.xml",
        })
        self._story_uids.append(story_uid)
        self._threaded_frames[story_uid] = []
        return story_uid

    def _add_threaded_text_frame(
        self,
        bounds: Bounds,
        story_uid: str,
        style_name: str,
        single_page: bool = False,
    ) -> str:
        """Přidá text frame napojený na existující threaded story.

        Returns:
            frame_uid nového framu.
        """
        frame_uid = self.uid.next()
        self._threaded_frames[story_uid].append(frame_uid)
        # XML se vygeneruje dodatečně v _finalize_threaded_frames
        return frame_uid

    def _build_threaded_text_frame_xml(
        self,
        frame_uid: str,
        bounds: Bounds,
        story_uid: str,
        style_name: str,
        prev_frame: str = "n",
        next_frame: str = "n",
        single_page: bool = False,
    ) -> str:
        """Generuje XML pro TextFrame s threading support."""
        tx, ty = self._bounds_to_spread_coords(bounds, single_page)
        w = round(bounds.width, 2)
        h = round(bounds.height, 2)

        col_count = 1
        if "Body" in style_name and w > 200:
            col_count = 2 if w < 500 else 3

        return (
            f'\t\t<TextFrame Self="{frame_uid}" '
            f'ParentStory="{story_uid}" '
            f'PreviousTextFrame="{prev_frame}" '
            f'NextTextFrame="{next_frame}" '
            f'ContentType="TextType" '
            f'StoryTitle="$ID/" '
            f'FillColor="Swatch/None" '
            f'StrokeWeight="0" StrokeColor="Swatch/None" '
            f'ItemLayer="u1a5" Locked="false" '
            f'AppliedObjectStyle='
            f'"ObjectStyle/$ID/[Normal Text Frame]" '
            f'Visible="true" '
            f'ItemTransform="1 0 0 1 {tx} {ty}">\n'
            f'\t\t\t<Properties>\n'
            f'\t\t\t\t<PathGeometry>\n'
            f'\t\t\t\t\t<GeometryPathType PathOpen="false">\n'
            f'\t\t\t\t\t\t<PathPointArray>\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="0 0" '
            f'LeftDirection="0 0" RightDirection="0 0" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="0 {h}" '
            f'LeftDirection="0 {h}" RightDirection="0 {h}" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="{w} {h}" '
            f'LeftDirection="{w} {h}" RightDirection="{w} {h}" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="{w} 0" '
            f'LeftDirection="{w} 0" RightDirection="{w} 0" />\n'
            f'\t\t\t\t\t\t</PathPointArray>\n'
            f'\t\t\t\t\t</GeometryPathType>\n'
            f'\t\t\t\t</PathGeometry>\n'
            f'\t\t\t</Properties>\n'
            f'\t\t\t<TextFramePreference TextColumnCount="{col_count}" '
            f'TextColumnGutter="24" '
            f'FirstBaselineOffset="AscentOffset" '
            f'VerticalJustification="TopAlign" '
            f'IgnoreWrap="false">\n'
            f'\t\t\t\t<Properties>\n'
            f'\t\t\t\t\t<InsetSpacing type="list">\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t</InsetSpacing>\n'
            f'\t\t\t\t</Properties>\n'
            f'\t\t\t</TextFramePreference>\n'
            f'\t\t\t<TextWrapPreference TextWrapMode="None">\n'
            f'\t\t\t\t<Properties>\n'
            f'\t\t\t\t\t<TextWrapOffset Top="0" Left="0" '
            f'Bottom="0" Right="0" />\n'
            f'\t\t\t\t</Properties>\n'
            f'\t\t\t</TextWrapPreference>\n'
            f'\t\t</TextFrame>'
        )

    def add_single_page_spread(
        self,
        pattern: SpreadPattern,
        content_map: dict[str, str],
        style_profile: StyleProfile,
        image_map: Optional[dict[str, str]] = None,
        page_start: int = 1,
    ) -> str:
        """Přidá single-page spread (např. cover)."""
        image_map = image_map or {}
        spread_uid = self.uid.next()
        page_uid = self.uid.next()

        # Pro single page: spread = 1 stránka (495×720)
        slots = instantiate_pattern(pattern, PAGE_WIDTH, PAGE_HEIGHT)

        frame_xmls = []
        for slot_data in slots:
            slot_id = slot_data["slot_id"]
            slot_type = slot_data["slot_type"]
            bounds: Bounds = slot_data["bounds"]
            default_style = slot_data["default_style"]

            if slot_type in (
                FrameType.BODY_TEXT.value, FrameType.HEADLINE.value,
                FrameType.DECK.value, FrameType.BYLINE.value,
                FrameType.CAPTION.value, FrameType.PULL_QUOTE.value,
                FrameType.FOLIO.value, FrameType.CREDIT.value,
                FrameType.SIDEBAR.value, FrameType.COVER_LINE.value,
            ):
                text = content_map.get(slot_id, "")
                if not text and not slot_data["required"]:
                    continue
                if not text:
                    text = " "
                style_name = default_style or "ALL_Body_Justified"
                story_uid = self.uid.next()
                story_xml = self._build_story_xml(story_uid, text, style_name)
                self._stories.append({
                    "uid": story_uid,
                    "xml": story_xml,
                    "filename": f"Stories/Story_{story_uid}.xml",
                })
                self._story_uids.append(story_uid)
                frame_xml = self._build_text_frame_xml(
                    bounds, story_uid, style_name, single_page=True,
                )
                frame_xmls.append(frame_xml)

            elif slot_type in (
                FrameType.HERO_IMAGE.value, FrameType.BODY_IMAGE.value,
                FrameType.LOGO.value,
            ):
                image_path = image_map.get(slot_id, "")
                frame_xml = self._build_image_frame_xml(
                    bounds, image_path,
                    slot_data.get("allow_bleed", False),
                    single_page=True,
                )
                frame_xmls.append(frame_xml)

        spread_xml = self._build_single_page_spread_xml(
            spread_uid, page_uid, frame_xmls, page_start, style_profile,
        )
        self._spreads.append({
            "uid": spread_uid,
            "xml": spread_xml,
            "filename": f"Spreads/Spread_{spread_uid}.xml",
        })
        return spread_uid

    # ----- XML Builders -----

    def _build_story_xml(
        self,
        story_uid: str,
        text: str,
        paragraph_style: str,
    ) -> str:
        """Generuje Story XML pro text frame."""
        escaped_text = xml_escape(text)
        # Rozdělit text na odstavce
        paragraphs = escaped_text.split("\n")

        para_xmls = []
        for para_text in paragraphs:
            if not para_text.strip():
                continue
            para_xmls.append(
                f'\t\t<ParagraphStyleRange AppliedParagraphStyle='
                f'"ParagraphStyle/{xml_escape(paragraph_style)}">\n'
                f'\t\t\t<CharacterStyleRange AppliedCharacterStyle='
                f'"CharacterStyle/$ID/[No character style]">\n'
                f'\t\t\t\t<Content>{para_text}</Content>\n'
                f'\t\t\t</CharacterStyleRange>\n'
                f'\t\t</ParagraphStyleRange>'
            )

        # Pokud žádný odstavec, vložit prázdný
        if not para_xmls:
            para_xmls.append(
                f'\t\t<ParagraphStyleRange AppliedParagraphStyle='
                f'"ParagraphStyle/{xml_escape(paragraph_style)}">\n'
                f'\t\t\t<CharacterStyleRange AppliedCharacterStyle='
                f'"CharacterStyle/$ID/[No character style]">\n'
                f'\t\t\t\t<Content> </Content>\n'
                f'\t\t\t</CharacterStyleRange>\n'
                f'\t\t</ParagraphStyleRange>'
            )

        story_title = text[:50].replace('"', "'") if text else ""

        return (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<idPkg:Story xmlns:idPkg='
            f'"http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" '
            f'DOMVersion="21.0">\n'
            f'\t<Story Self="{story_uid}" AppliedTOCStyle="n" '
            f'UserText="true" IsEndnoteStory="false" '
            f'TrackChanges="false" '
            f'StoryTitle="$ID/{xml_escape(story_title)}" '
            f'AppliedNamedGrid="n">\n'
            f'\t\t<StoryPreference OpticalMarginAlignment="false" '
            f'OpticalMarginSize="12" FrameType="TextFrameType" '
            f'StoryOrientation="Horizontal" '
            f'StoryDirection="LeftToRightDirection" />\n'
            f'\t\t<InCopyExportOption IncludeGraphicProxies="true" '
            f'IncludeAllResources="false" />\n'
            + "\n".join(para_xmls) + "\n"
            f'\t</Story>\n'
            f'</idPkg:Story>'
        )

    def _bounds_to_spread_coords(
        self,
        bounds: Bounds,
        single_page: bool = False,
    ) -> tuple[float, float]:
        """Převede absolutní bounds na spread souřadnice (tx, ty).

        Pro double-page spread: bounds.x je vůči celému spreadu (0-990pt).
        Pro single-page spread: bounds.x je vůči jedné stránce (0-495pt).
        """
        if single_page:
            # Single page: origin v centru stránky
            tx = bounds.x - PAGE_WIDTH / 2
            ty = bounds.y - PAGE_HEIGHT / 2
        else:
            # Double page: origin v centru spreadu
            tx = bounds.x - SPREAD_OFFSET_X
            ty = bounds.y - SPREAD_OFFSET_Y
        return round(tx, 2), round(ty, 2)

    def _build_text_frame_xml(
        self,
        bounds: Bounds,
        story_uid: str,
        style_name: str,
        single_page: bool = False,
    ) -> str:
        """Generuje XML pro TextFrame element."""
        frame_uid = self.uid.next()
        tx, ty = self._bounds_to_spread_coords(bounds, single_page)
        w = round(bounds.width, 2)
        h = round(bounds.height, 2)

        # Počet sloupců pro body text
        col_count = 1
        if "Body" in style_name and w > 200:
            col_count = 2 if w < 500 else 3

        return (
            f'\t\t<TextFrame Self="{frame_uid}" '
            f'ParentStory="{story_uid}" '
            f'PreviousTextFrame="n" NextTextFrame="n" '
            f'ContentType="TextType" '
            f'StoryTitle="$ID/" '
            f'FillColor="Swatch/None" '
            f'StrokeWeight="0" StrokeColor="Swatch/None" '
            f'ItemLayer="u1a5" Locked="false" '
            f'AppliedObjectStyle='
            f'"ObjectStyle/$ID/[Normal Text Frame]" '
            f'Visible="true" '
            f'ItemTransform="1 0 0 1 {tx} {ty}">\n'
            f'\t\t\t<Properties>\n'
            f'\t\t\t\t<PathGeometry>\n'
            f'\t\t\t\t\t<GeometryPathType PathOpen="false">\n'
            f'\t\t\t\t\t\t<PathPointArray>\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="0 0" '
            f'LeftDirection="0 0" RightDirection="0 0" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="0 {h}" '
            f'LeftDirection="0 {h}" RightDirection="0 {h}" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="{w} {h}" '
            f'LeftDirection="{w} {h}" RightDirection="{w} {h}" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="{w} 0" '
            f'LeftDirection="{w} 0" RightDirection="{w} 0" />\n'
            f'\t\t\t\t\t\t</PathPointArray>\n'
            f'\t\t\t\t\t</GeometryPathType>\n'
            f'\t\t\t\t</PathGeometry>\n'
            f'\t\t\t</Properties>\n'
            f'\t\t\t<TextFramePreference TextColumnCount="{col_count}" '
            f'TextColumnGutter="24" '
            f'FirstBaselineOffset="AscentOffset" '
            f'VerticalJustification="TopAlign" '
            f'IgnoreWrap="false">\n'
            f'\t\t\t\t<Properties>\n'
            f'\t\t\t\t\t<InsetSpacing type="list">\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t\t<ListItem type="unit">0</ListItem>\n'
            f'\t\t\t\t\t</InsetSpacing>\n'
            f'\t\t\t\t</Properties>\n'
            f'\t\t\t</TextFramePreference>\n'
            f'\t\t\t<TextWrapPreference TextWrapMode="None">\n'
            f'\t\t\t\t<Properties>\n'
            f'\t\t\t\t\t<TextWrapOffset Top="0" Left="0" '
            f'Bottom="0" Right="0" />\n'
            f'\t\t\t\t</Properties>\n'
            f'\t\t\t</TextWrapPreference>\n'
            f'\t\t</TextFrame>'
        )

    def _build_image_frame_xml(
        self,
        bounds: Bounds,
        image_path: str = "",
        allow_bleed: bool = False,
        single_page: bool = False,
    ) -> str:
        """Generuje XML pro Rectangle (image frame) element."""
        rect_uid = self.uid.next()
        tx, ty = self._bounds_to_spread_coords(bounds, single_page)
        w = round(bounds.width, 2)
        h = round(bounds.height, 2)

        # Content type: GraphicType pokud bude obrázek, jinak Unassigned
        content_type = "GraphicType" if image_path else "Unassigned"

        # Image child element (pokud je zadána cesta)
        image_xml = ""
        if image_path:
            image_uid = self.uid.next()
            link_uid = self.uid.next()
            # Normalizovat cestu na URI
            uri = image_path.replace("\\", "/")
            if not uri.startswith("file:"):
                uri = f"file:///{uri}" if ":" in uri else f"file://{uri}"

            image_xml = (
                f'\t\t\t<FrameFittingOption LeftCrop="0" TopCrop="0" '
                f'RightCrop="0" BottomCrop="0" '
                f'FittingOnEmptyFrame="Proportionally" />\n'
                f'\t\t\t<Image Self="{image_uid}" '
                f'Space="$ID/#Links_CMYK" '
                f'ActualPpi="300 300" EffectivePpi="300 300" '
                f'ImageTypeName="$ID/Importable" '
                f'ItemTransform="1 0 0 1 0 0">\n'
                f'\t\t\t\t<Properties>\n'
                f'\t\t\t\t\t<GraphicBounds Left="0" Top="0" '
                f'Right="{w}" Bottom="{h}" />\n'
                f'\t\t\t\t</Properties>\n'
                f'\t\t\t\t<Link Self="{link_uid}" '
                f'LinkResourceURI="{xml_escape(uri)}" '
                f'StoredState="Normal" />\n'
                f'\t\t\t</Image>\n'
            )
        else:
            image_xml = (
                f'\t\t\t<FrameFittingOption LeftCrop="0" TopCrop="0" '
                f'RightCrop="0" BottomCrop="0" '
                f'FittingOnEmptyFrame="Proportionally" />\n'
            )

        return (
            f'\t\t<Rectangle Self="{rect_uid}" '
            f'ContentType="{content_type}" '
            f'StoryTitle="$ID/" '
            f'FillColor="Color/Paper" '
            f'StrokeWeight="0" StrokeColor="Swatch/None" '
            f'ItemLayer="u1a5" Locked="false" '
            f'AppliedObjectStyle="ObjectStyle/$ID/[None]" '
            f'Visible="true" '
            f'ItemTransform="1 0 0 1 {tx} {ty}">\n'
            f'\t\t\t<Properties>\n'
            f'\t\t\t\t<PathGeometry>\n'
            f'\t\t\t\t\t<GeometryPathType PathOpen="false">\n'
            f'\t\t\t\t\t\t<PathPointArray>\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="0 0" '
            f'LeftDirection="0 0" RightDirection="0 0" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="0 {h}" '
            f'LeftDirection="0 {h}" RightDirection="0 {h}" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="{w} {h}" '
            f'LeftDirection="{w} {h}" RightDirection="{w} {h}" />\n'
            f'\t\t\t\t\t\t\t<PathPointType Anchor="{w} 0" '
            f'LeftDirection="{w} 0" RightDirection="{w} 0" />\n'
            f'\t\t\t\t\t\t</PathPointArray>\n'
            f'\t\t\t\t\t</GeometryPathType>\n'
            f'\t\t\t\t</PathGeometry>\n'
            f'\t\t\t</Properties>\n'
            + image_xml
            + f'\t\t</Rectangle>'
        )

    def _build_spread_xml(
        self,
        spread_uid: str,
        page_left_uid: str,
        page_right_uid: str,
        frame_xmls: list[str],
        page_start: int,
        style_profile: StyleProfile,
    ) -> str:
        """Generuje kompletní Spread XML pro double-page spread."""
        # NG standard marginy a grid
        mt = style_profile.margin_top
        mb = style_profile.margin_bottom
        ml = style_profile.margin_left
        mr = style_profile.margin_right
        cc = style_profile.column_count // 2  # Per page (12 total / 2 pages = 6)
        cg = style_profile.column_gutter

        frames_str = "\n".join(frame_xmls)

        # Najít master spread UID — použít první dostupný 2-page master
        master_uid = "n"
        for ms_path in self._skeleton_master_spreads:
            ms_data = self._skeleton_data.get(ms_path, b"")
            if b'PageCount="2"' in ms_data:
                match = re.search(rb'Self="([^"]+)"', ms_data)
                if match:
                    master_uid = match.group(1).decode("utf-8")
                    break

        return (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<idPkg:Spread xmlns:idPkg='
            f'"http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" '
            f'DOMVersion="21.0">\n'
            f'\t<Spread Self="{spread_uid}" '
            f'FlattenerOverride="Default" '
            f'SpreadHidden="false" '
            f'AllowPageShuffle="true" '
            f'ItemTransform="1 0 0 1 0 0" '
            f'ShowMasterItems="true" '
            f'PageCount="2" '
            f'BindingLocation="1" '
            f'PageTransitionType="None" '
            f'PageTransitionDirection="NotApplicable" '
            f'PageTransitionDuration="Medium">\n'
            f'\t\t<FlattenerPreference '
            f'LineArtAndTextResolution="300" '
            f'GradientAndMeshResolution="150" '
            f'ClipComplexRegions="false" '
            f'ConvertAllStrokesToOutlines="false" '
            f'ConvertAllTextToOutlines="false">\n'
            f'\t\t\t<Properties>\n'
            f'\t\t\t\t<RasterVectorBalance type="double">'
            f'50</RasterVectorBalance>\n'
            f'\t\t\t</Properties>\n'
            f'\t\t</FlattenerPreference>\n'
            # Levá stránka
            f'\t\t<Page Self="{page_left_uid}" '
            f'GeometricBounds="0 0 {PAGE_HEIGHT} {PAGE_WIDTH}" '
            f'ItemTransform="1 0 0 1 -{PAGE_WIDTH} -{PAGE_HEIGHT / 2}" '
            f'Name="{page_start}" '
            f'AppliedTrapPreset='
            f'"TrapPreset/$ID/kDefaultTrapStyleName" '
            f'AppliedMaster="{master_uid}" '
            f'MasterPageTransform="1 0 0 1 0 0">\n'
            f'\t\t\t<MarginPreference ColumnCount="{cc}" '
            f'ColumnGutter="{cg}" '
            f'Top="{mt}" Bottom="{mb}" '
            f'Left="{ml}" Right="{mr}" '
            f'ColumnDirection="Horizontal" />\n'
            f'\t\t</Page>\n'
            # Pravá stránka
            f'\t\t<Page Self="{page_right_uid}" '
            f'GeometricBounds="0 0 {PAGE_HEIGHT} {PAGE_WIDTH}" '
            f'ItemTransform="1 0 0 1 0 -{PAGE_HEIGHT / 2}" '
            f'Name="{page_start + 1}" '
            f'AppliedTrapPreset='
            f'"TrapPreset/$ID/kDefaultTrapStyleName" '
            f'AppliedMaster="{master_uid}" '
            f'MasterPageTransform="1 0 0 1 0 0">\n'
            f'\t\t\t<MarginPreference ColumnCount="{cc}" '
            f'ColumnGutter="{cg}" '
            f'Top="{mt}" Bottom="{mb}" '
            f'Left="{mr}" Right="{ml}" '
            f'ColumnDirection="Horizontal" />\n'
            f'\t\t</Page>\n'
            # Frames
            + frames_str + "\n"
            f'\t</Spread>\n'
            f'</idPkg:Spread>'
        )

    def _build_single_page_spread_xml(
        self,
        spread_uid: str,
        page_uid: str,
        frame_xmls: list[str],
        page_start: int,
        style_profile: StyleProfile,
    ) -> str:
        """Generuje Spread XML pro single-page spread (cover)."""
        mt = style_profile.margin_top
        mb = style_profile.margin_bottom
        ml = style_profile.margin_left
        mr = style_profile.margin_right
        cc = style_profile.column_count // 2
        cg = style_profile.column_gutter

        frames_str = "\n".join(frame_xmls)

        return (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<idPkg:Spread xmlns:idPkg='
            f'"http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" '
            f'DOMVersion="21.0">\n'
            f'\t<Spread Self="{spread_uid}" '
            f'FlattenerOverride="Default" '
            f'SpreadHidden="false" '
            f'AllowPageShuffle="true" '
            f'ItemTransform="1 0 0 1 0 0" '
            f'ShowMasterItems="true" '
            f'PageCount="1" '
            f'BindingLocation="1">\n'
            f'\t\t<FlattenerPreference '
            f'LineArtAndTextResolution="300" '
            f'GradientAndMeshResolution="150" '
            f'ClipComplexRegions="false" '
            f'ConvertAllStrokesToOutlines="false" '
            f'ConvertAllTextToOutlines="false">\n'
            f'\t\t\t<Properties>\n'
            f'\t\t\t\t<RasterVectorBalance type="double">'
            f'50</RasterVectorBalance>\n'
            f'\t\t\t</Properties>\n'
            f'\t\t</FlattenerPreference>\n'
            f'\t\t<Page Self="{page_uid}" '
            f'GeometricBounds="0 0 {PAGE_HEIGHT} {PAGE_WIDTH}" '
            f'ItemTransform="1 0 0 1 -{PAGE_WIDTH / 2} -{PAGE_HEIGHT / 2}" '
            f'Name="{page_start}" '
            f'AppliedTrapPreset='
            f'"TrapPreset/$ID/kDefaultTrapStyleName" '
            f'AppliedMaster="n" '
            f'MasterPageTransform="1 0 0 1 0 0">\n'
            f'\t\t\t<MarginPreference ColumnCount="{cc}" '
            f'ColumnGutter="{cg}" '
            f'Top="{mt}" Bottom="{mb}" '
            f'Left="{ml}" Right="{mr}" '
            f'ColumnDirection="Horizontal" />\n'
            f'\t\t</Page>\n'
            + frames_str + "\n"
            f'\t</Spread>\n'
            f'</idPkg:Spread>'
        )

    # ----- designmap.xml -----

    def _build_designmap_xml(self) -> str:
        """Generuje nový designmap.xml s odkazem na skeleton resources
        a nové spready/stories.
        """
        # Extrahovat hlavičku z skeleton designmap (vše až po <Document ...>)
        # Potřebujeme <?xml?>, <?aid?>, <Document> a Resources/Preferences/Tags
        # ale NOVÉ spready a stories

        # Najít Document tag a jeho atributy
        doc_match = re.search(
            r'<Document\s+([^>]+)>',
            self._skeleton_designmap,
            re.DOTALL,
        )
        if not doc_match:
            raise RuntimeError("Cannot parse designmap.xml from skeleton")

        doc_attrs = doc_match.group(1)

        # Aktualizovat StoryList
        all_story_uids = " ".join(self._story_uids)
        doc_attrs = re.sub(
            r'StoryList="[^"]*"',
            f'StoryList="{all_story_uids}"',
            doc_attrs,
        )

        # Najít obsah mezi <Document> a prvním <idPkg: — to jsou Language, Kinsoku atd.
        # Extrahujeme vše od <Document> po </Document>, ale vyměníme Spready a Stories
        inner_start = self._skeleton_designmap.find(">", doc_match.start()) + 1
        inner_end = self._skeleton_designmap.rfind("</Document>")
        inner_content = self._skeleton_designmap[inner_start:inner_end]

        # Z inner_content ponechat vše KROMĚ Spread a Story referencí
        lines_to_keep = []
        for line in inner_content.split("\n"):
            stripped = line.strip()
            # Přeskočit staré spread a story reference
            if stripped.startswith("<idPkg:Spread "):
                continue
            if stripped.startswith("<idPkg:Story "):
                continue
            if stripped.startswith("<idPkg:BackingStory "):
                continue
            if stripped.startswith("<idPkg:Mapping "):
                continue
            lines_to_keep.append(line)

        # Přidat nové spread reference
        spread_refs = []
        for spread in self._spreads:
            spread_refs.append(
                f'\t<idPkg:Spread src="{spread["filename"]}" />'
            )

        # Přidat BackingStory (ze skeleton) a nové story reference
        backing_story = '\t<idPkg:BackingStory src="XML/BackingStory.xml" />'
        story_refs = []
        for story in self._stories:
            story_refs.append(
                f'\t<idPkg:Story src="{story["filename"]}" />'
            )

        # Mapping
        mapping_ref = '\t<idPkg:Mapping src="XML/Mapping.xml" />'

        # Složit
        cleaned_inner = "\n".join(lines_to_keep).rstrip()
        new_refs = "\n".join(spread_refs + [backing_story] + story_refs + [mapping_ref])

        return (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<?aid style="50" type="document" readerVersion="6.0" '
            f'featureSet="257" product="21.0(6)" ?>\n'
            f'<Document {doc_attrs}>\n'
            + cleaned_inner + "\n"
            + new_refs + "\n"
            + "</Document>"
        )

    # ----- Threading finalization -----

    def _finalize_threading(self):
        """Nahradí __THREAD_xxx__ placeholdery ve spread XML reálnými frame XML.

        Pro každou threaded story propojí framy přes PreviousTextFrame/NextTextFrame.
        """
        for story_uid, frame_entries in self._threaded_frames.items():
            if not frame_entries:
                continue

            # frame_entries: list of (frame_uid, bounds, style_name, single_page)
            # Pokud jsou to tuples (nový formát)
            if not frame_entries or not isinstance(frame_entries[0], tuple):
                continue

            frame_uids = [e[0] for e in frame_entries]

            # Generovat XML pro každý frame s prev/next
            for i, (frame_uid, bounds, style_name, single_page) in enumerate(frame_entries):
                prev_uid = frame_uids[i - 1] if i > 0 else "n"
                next_uid = frame_uids[i + 1] if i < len(frame_entries) - 1 else "n"

                frame_xml = self._build_threaded_text_frame_xml(
                    frame_uid, bounds, story_uid, style_name,
                    prev_frame=prev_uid, next_frame=next_uid,
                    single_page=single_page,
                )

                # Nahradit placeholder ve všech spreadech
                placeholder = f"__THREAD_{frame_uid}__"
                for spread in self._spreads:
                    if placeholder in spread["xml"]:
                        spread["xml"] = spread["xml"].replace(
                            placeholder, frame_xml
                        )
                        break

    # ----- Build -----

    def build(self, output_path: str | Path) -> Path:
        """Sestaví a zabalí finální IDML soubor.

        Returns:
            Path k vytvořenému IDML souboru.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Validace: musí být aspoň 1 spread
        if not self._spreads:
            raise RuntimeError("No spreads added — call add_spread() first")

        # Finalizovat threading — nahradit placeholdery reálnými frame XML
        self._finalize_threading()

        # Generovat designmap
        designmap_xml = self._build_designmap_xml()

        # Validovat všechny XML
        self._validate_xml(designmap_xml, "designmap.xml")
        for spread in self._spreads:
            self._validate_xml(spread["xml"], spread["filename"])
        for story in self._stories:
            self._validate_xml(story["xml"], story["filename"])

        # Zabalit do IDML (ZIP)
        with zipfile.ZipFile(output_path, "w") as zf:
            # 1. mimetype — MUSÍ být první, ZIP_STORED (ne DEFLATED)
            zf.writestr(
                "mimetype",
                "application/vnd.adobe.indesign-idml-package",
                compress_type=zipfile.ZIP_STORED,
            )

            # 2. META-INF/container.xml
            if "META-INF/container.xml" in self._skeleton_data:
                zf.writestr(
                    "META-INF/container.xml",
                    self._skeleton_data["META-INF/container.xml"],
                    compress_type=zipfile.ZIP_DEFLATED,
                )

            # 3. designmap.xml
            zf.writestr(
                "designmap.xml",
                designmap_xml.encode("utf-8"),
                compress_type=zipfile.ZIP_DEFLATED,
            )

            # 4. Resources
            for name, data in self._skeleton_data.items():
                if name.startswith("Resources/"):
                    zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

            # 5. MasterSpreads
            for name, data in self._skeleton_data.items():
                if name.startswith("MasterSpreads/"):
                    zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

            # 6. Spreads (nové)
            for spread in self._spreads:
                zf.writestr(
                    spread["filename"],
                    spread["xml"].encode("utf-8"),
                    compress_type=zipfile.ZIP_DEFLATED,
                )

            # 7. Stories (nové)
            for story in self._stories:
                zf.writestr(
                    story["filename"],
                    story["xml"].encode("utf-8"),
                    compress_type=zipfile.ZIP_DEFLATED,
                )

            # 8. XML (BackingStory, Mapping, Tags)
            for name, data in self._skeleton_data.items():
                if name.startswith("XML/"):
                    zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

        logger.info(
            "IDML built: %s (%d spreads, %d stories)",
            output_path,
            len(self._spreads),
            len(self._stories),
        )
        return output_path

    def _validate_xml(self, xml_str: str, label: str):
        """Validuje XML string přes ET.fromstring()."""
        try:
            ET.fromstring(xml_str.encode("utf-8"))
        except ET.ParseError as e:
            logger.error("XML validation failed for %s: %s", label, e)
            # Debug: uložit problematický XML
            debug_path = Path(f"data/debug_{label.replace('/', '_')}")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(xml_str, encoding="utf-8")
            raise RuntimeError(
                f"Invalid XML generated for {label}: {e}. "
                f"Debug XML saved to {debug_path}"
            ) from e


# ----- Convenience funkce -----

def build_from_plan(
    layout_plan: LayoutPlan,
    skeleton_idml: str | Path,
    output_path: str | Path,
    text_sections: Optional[dict[str, str]] = None,
    image_paths: Optional[dict[str, list[str]]] = None,
) -> Path:
    """Vytvoří IDML z kompletního layout plánu.

    Args:
        layout_plan: Plán layoutu se sekvencí spreadů.
        skeleton_idml: Cesta ke skeleton IDML.
        output_path: Kam uložit výstupní IDML.
        text_sections: Mapování section_id → text.
        image_paths: Mapování spread_index → [cesty k obrázkům].

    Returns:
        Path k vytvořenému IDML.
    """
    text_sections = text_sections or {}
    image_paths = image_paths or {}

    profile = get_profile(layout_plan.style_profile)
    if not profile:
        raise ValueError(f"Style profile not found: {layout_plan.style_profile}")

    builder = IDMLBuilder(skeleton_idml)

    for planned_spread in layout_plan.spreads:
        pattern = get_pattern(planned_spread.pattern_id)
        if not pattern:
            raise ValueError(f"Pattern not found: {planned_spread.pattern_id}")

        # Sestavit content_map z přiřazených text sekcí
        content_map = {}
        for section_id in planned_spread.assigned_text_sections:
            if section_id in text_sections:
                # Namapovat na příslušný slot
                content_map[section_id] = text_sections[section_id]

        # Sestavit image_map
        imgs = image_paths.get(str(planned_spread.spread_index), [])
        image_map = {}
        img_idx = 0
        for slot in pattern.slots:
            if slot.slot_type in (FrameType.HERO_IMAGE, FrameType.BODY_IMAGE):
                if img_idx < len(imgs):
                    image_map[slot.slot_id] = imgs[img_idx]
                    img_idx += 1

        page_num = planned_spread.spread_index * 2 + 1

        if planned_spread.spread_type.value == "cover":
            builder.add_single_page_spread(
                pattern, content_map, profile,
                image_map, page_start=page_num,
            )
        else:
            builder.add_spread(
                pattern, content_map, profile,
                image_map, page_start=page_num,
            )

    return builder.build(output_path)


def build_from_multi_article_plans(
    multi_plan: MultiArticlePlan,
    skeleton_idml: str | Path,
    output_path: str | Path,
    article_text_sections: dict[str, dict[str, str]] | None = None,
    article_image_paths: dict[str, dict[str, list[str]]] | None = None,
) -> Path:
    """Vytvoří jeden IDML z multi-article plánu.

    Každý článek má vlastní threaded body story (žádné cross-article threading).
    Stránky jsou číslovány kontinuálně (článek 1: 1-10, článek 2: 11-18...).

    Args:
        multi_plan: MultiArticlePlan s jedním LayoutPlan per article.
        skeleton_idml: Cesta ke skeleton IDML.
        output_path: Kam uložit výstupní IDML.
        article_text_sections: {article_id: {section_id: text}} — texty per article.
        article_image_paths: {article_id: {spread_index: [paths]}} — fotky per article.

    Returns:
        Path k vytvořenému IDML.
    """
    article_text_sections = article_text_sections or {}
    article_image_paths = article_image_paths or {}

    builder = IDMLBuilder(skeleton_idml)
    global_page_num = 1

    for article_plan in multi_plan.article_plans:
        profile = get_profile(article_plan.style_profile)
        if not profile:
            raise ValueError(f"Style profile not found: {article_plan.style_profile}")

        text_sections = article_text_sections.get(article_plan.project_id, {})
        image_paths = article_image_paths.get(article_plan.project_id, {})

        for planned_spread in article_plan.spreads:
            pattern = get_pattern(planned_spread.pattern_id)
            if not pattern:
                raise ValueError(f"Pattern not found: {planned_spread.pattern_id}")

            # Sestavit content_map
            content_map = {}
            for section_id in planned_spread.assigned_text_sections:
                if section_id in text_sections:
                    content_map[section_id] = text_sections[section_id]

            # Sestavit image_map
            imgs = image_paths.get(str(planned_spread.spread_index), [])
            image_map = {}
            img_idx = 0
            for slot in pattern.slots:
                if slot.slot_type in (FrameType.HERO_IMAGE, FrameType.BODY_IMAGE):
                    if img_idx < len(imgs):
                        image_map[slot.slot_id] = imgs[img_idx]
                        img_idx += 1

            if planned_spread.spread_type.value == "cover":
                builder.add_single_page_spread(
                    pattern, content_map, profile,
                    image_map, page_start=global_page_num,
                )
                global_page_num += 1
            else:
                builder.add_spread(
                    pattern, content_map, profile,
                    image_map, page_start=global_page_num,
                )
                global_page_num += 2

    logger.info(
        "Multi-article IDML: %d článků, %d stránek, výstup: %s",
        len(multi_plan.article_plans), global_page_num - 1, output_path,
    )
    return builder.build(output_path)
