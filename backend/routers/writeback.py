"""Endpointy pro zapis prekladu zpet do IDML a MAP (Illustrator)."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.project_store import get_project, save_project
from services.idml_writeback import writeback_idml
from services.map_writeback import writeback_map, preview_map

logger = logging.getLogger(__name__)
router = APIRouter(tags=["writeback"])


@router.post("/api/projects/{project_id}/writeback")
async def api_writeback(project_id: str):
    """Zapise preklady zpet do IDML a vrati vysledek."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if not project.idml_path:
        raise HTTPException(400, "Projekt nema IDML soubor")

    idml_path = Path(project.idml_path)
    if not idml_path.exists():
        raise HTTPException(404, f"IDML soubor nenalezen: {idml_path}")

    # Spocitej kolik elementu ma preklad
    with_czech = [e for e in project.elements if e.czech]
    if not with_czech:
        raise HTTPException(400, "Zadne preklady k zapisu")

    try:
        result = writeback_idml(
            idml_path=idml_path,
            elements=project.elements,
            project_id=project_id,
        )
    except Exception as e:
        logger.error("Writeback selhal: %s", e)
        raise HTTPException(500, f"Writeback selhal: {e}")

    # Ulozit cestu k exportu do projektu
    if result.get("output_path"):
        project.exports["idml_cz"] = result["output_path"]
        project.phase = "exported"
        save_project(project)

    return result


@router.post("/api/projects/{project_id}/writeback/preview")
async def api_writeback_preview(project_id: str):
    """Nahled: kolik textu bude zapsano, kolik chybi."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    total = len(project.elements)
    with_czech = sum(1 for e in project.elements if e.czech)
    with_story = sum(1 for e in project.elements if e.czech and e.story_id)
    no_translation = sum(1 for e in project.elements if not e.czech and e.contents.strip())

    return {
        "total_elements": total,
        "with_translation": with_czech,
        "writable": with_story,
        "missing_translation": no_translation,
        "coverage_pct": round(with_czech / total * 100, 1) if total else 0,
    }


@router.post("/api/projects/{project_id}/writeback-map")
async def api_writeback_map(project_id: str):
    """Zapise preklady zpet do Illustratoru (MAP projekt)."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project.type != "map":
        raise HTTPException(400, "Projekt neni typu MAP")

    with_czech = [e for e in project.elements if e.czech]
    if not with_czech:
        raise HTTPException(400, "Zadne preklady k zapisu")

    try:
        result = writeback_map(elements=project.elements)
    except Exception as e:
        logger.error("MAP writeback selhal: %s", e)
        raise HTTPException(500, f"MAP writeback selhal: {e}")

    if result.get("changed", 0) > 0:
        project.phase = "written_back"
        save_project(project)

    return result


@router.post("/api/projects/{project_id}/writeback-map/preview")
async def api_writeback_map_preview(project_id: str):
    """Nahled pro MAP writeback — kolik textu bude zapsano."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    return preview_map(project.elements)


@router.get("/api/projects/{project_id}/download/{export_key}")
async def api_download_export(project_id: str, export_key: str):
    """Stahne exportovany soubor."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    file_path = project.exports.get(export_key)
    if not file_path:
        raise HTTPException(404, f"Export '{export_key}' nenalezen")

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(404, f"Soubor nenalezen: {path}")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
