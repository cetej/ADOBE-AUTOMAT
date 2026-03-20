"""Extrakce textu z Illustratoru pres ExtendScript."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import logging
from pathlib import Path

from services.illustrator_bridge import execute_script
from models import TextElement

logger = logging.getLogger(__name__)

_EXTRACT_SCRIPT_PATH = Path(__file__).parent.parent / "extendscripts" / "extract_texts.jsx"
_extract_script_cache: str | None = None


def _load_extract_script() -> str:
    """Lazy load ExtendScript — nečte soubor při importu modulu."""
    global _extract_script_cache
    if _extract_script_cache is None:
        _extract_script_cache = _EXTRACT_SCRIPT_PATH.read_text(encoding="utf-8")
    return _extract_script_cache


def extract_from_illustrator(timeout: int = 120) -> dict:
    """Spusti ExtendScript pro extrakci textu a vrati raw data vcetne info o dokumentu.

    Returns:
        dict: {
            "layers": [{layerName, layerId, texts: [...]}],
            "document": {"name": str, "path": str} | None
        }

    Raises:
        RuntimeError: Pri chybe komunikace s Illustratorem.
    """
    logger.info("Starting text extraction from Illustrator...")
    raw_result = execute_script(_load_extract_script(), timeout=timeout)

    # Proxy vraci {"content": [{"type": "text", "text": "JSON"}]}
    result = raw_result
    if isinstance(result, dict) and "content" in result:
        for item in result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                result = item["text"]
                break

    # Vysledek muze byt string (JSON) nebo uz dict
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from Illustrator: {e}\nRaw: {result[:500]}")

    if isinstance(result, dict) and "error" in result:
        raise RuntimeError(f"ExtendScript error: {result['error']} (line {result.get('line', '?')})")

    # Novy format: dict s "layers" a "document"
    if isinstance(result, dict) and "layers" in result:
        layers = result["layers"]
        doc_info = result.get("document")
    elif isinstance(result, list):
        # Zpetna kompatibilita — stary format bez doc info
        layers = result
        doc_info = None
    else:
        raise RuntimeError(f"Unexpected result type: {type(result)}. Expected dict or list.")

    total_texts = sum(len(layer.get("texts", [])) for layer in layers)
    logger.info("Extracted %d layers, %d text frames total", len(layers), total_texts)
    return {"layers": layers, "document": doc_info}


def raw_to_elements(raw_layers: list[dict]) -> list[TextElement]:
    """Prevede raw extrakci na seznam TextElement objektu.

    Args:
        raw_layers: Vysledek z extract_from_illustrator()

    Returns:
        list[TextElement]: Plochy seznam vsech textovych elementu.
    """
    elements = []
    seen_ids = set()
    for layer in raw_layers:
        layer_name = layer.get("layerName", "Unknown")
        layer_id = layer.get("layerId", 0)
        for text in layer.get("texts", []):
            contents = text.get("contents", "").strip()
            if not contents:
                continue

            elem_id = f"{layer_name}/{text.get('index', 0)}"
            # Deduplikace — vrstvy se stejnym jmenem dostanou layerId suffix
            if elem_id in seen_ids:
                elem_id = f"{layer_name}#{layer_id}/{text.get('index', 0)}"
            seen_ids.add(elem_id)
            elements.append(TextElement(
                id=elem_id,
                contents=contents,
                layer_name=layer_name,
                position=text.get("position"),
                fontSize=text.get("fontSize"),
            ))

    logger.info("Converted to %d text elements", len(elements))
    return elements
