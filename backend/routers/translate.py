"""Endpointy pro preklad a editaci textu."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from fastapi import APIRouter, HTTPException

from models import TextUpdate, BulkTextUpdate, TranslateRequest, TextStatus
from services.project_store import get_project, save_project
from services.translation_service import (
    translate_batch,
    update_translation_memory,
    load_translation_memory,
    get_api_key,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["translate"])


@router.put("/api/projects/{project_id}/texts/{text_id:path}")
async def api_update_text(project_id: str, text_id: str, update: TextUpdate):
    """Aktualizuje jeden textovy element."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    for elem in project.elements:
        if elem.id == text_id:
            if update.czech is not None:
                elem.czech = update.czech
            if update.status is not None:
                elem.status = update.status
            if update.category is not None:
                elem.category = update.category
            if update.notes is not None:
                elem.notes = update.notes
            save_project(project)
            return elem

    raise HTTPException(404, f"Text '{text_id}' not found")


@router.patch("/api/projects/{project_id}/texts/bulk")
async def api_bulk_update(project_id: str, update: BulkTextUpdate):
    """Hromadna aktualizace textu."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    updated = 0
    id_set = set(update.ids)
    for elem in project.elements:
        if elem.id in id_set:
            if update.status is not None:
                elem.status = update.status
            if update.category is not None:
                elem.category = update.category
            updated += 1

    save_project(project)
    return {"updated": updated}


@router.post("/api/projects/{project_id}/translate")
async def api_translate(project_id: str, req: TranslateRequest = TranslateRequest()):
    """AI preklad textu pomoci Claude API."""
    # Overit API klic
    if not get_api_key():
        raise HTTPException(
            400,
            "ANTHROPIC_API_KEY neni nastaven. "
            "Nastavte env promennou nebo vytvorte .env soubor v rootu projektu."
        )

    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Vybrat elementy k prekladu
    if req.ids:
        elements = [e for e in project.elements if e.id in set(req.ids)]
    elif req.overwrite:
        elements = [e for e in project.elements if e.contents.strip()]
    else:
        elements = [e for e in project.elements if e.contents.strip() and not e.czech]

    if not elements:
        return {"translated": 0, "message": "Zadne texty k prekladu"}

    # Prelozit
    try:
        results = translate_batch(
            elements=elements,
            project_type=project.type,
            model=req.model,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Chyba prekladu: %s", e)
        raise HTTPException(500, f"Chyba prekladu: {e}")

    # Aplikovat preklady do projektu
    result_map = {r["id"]: r["czech"] for r in results}
    applied = 0
    for elem in project.elements:
        if elem.id in result_map:
            elem.czech = result_map[elem.id]
            elem.auto_translated = True
            if not elem.status:
                elem.status = TextStatus.OVERIT
            applied += 1

    save_project(project)

    return {
        "translated": applied,
        "total_requested": len(elements),
        "from_memory": sum(1 for _ in results) - applied if len(results) > applied else 0,
        "project": project,
    }


@router.post("/api/projects/{project_id}/translate/save-tm")
async def api_save_translation_memory(project_id: str):
    """Ulozi potvrzene preklady (status=OK) do translation memory."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    added = update_translation_memory(project.elements)
    tm = load_translation_memory()

    return {
        "added": added,
        "total": len(tm),
    }
