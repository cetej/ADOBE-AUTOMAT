"""Endpointy pro preklad a editaci textu."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
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

# CzechCorrector — typography auto-fix po překladu
try:
    from ngm_terminology.corrector import CzechCorrector
    _CORRECTOR_AVAILABLE = True
except ImportError:
    _CORRECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter(tags=["translate"])

# Progress tracking per project
_translate_progress: dict[str, dict] = {}


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
    """AI preklad textu pomoci Claude API — bezi na pozadi s progress tracking."""
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
        return {"translated": 0, "message": "Zadne texty k prekladu", "status": "done"}

    # Zjisti jestli ma backgrounder
    has_backgrounder = bool(project.backgrounder)

    # Inicializuj progress
    _translate_progress[project_id] = {
        "status": "running",
        "batch": 0,
        "total_batches": 0,
        "from_memory": 0,
        "total_elements": len(elements),
        "translated": 0,
        "has_backgrounder": has_backgrounder,
        "error": None,
    }

    # Spust preklad na pozadi
    asyncio.get_running_loop().run_in_executor(
        None,
        _run_translation,
        project_id, elements, project.type, req.model,
        project.backgrounder, req.overwrite,
    )

    return {
        "status": "started",
        "total_elements": len(elements),
        "has_backgrounder": has_backgrounder,
    }


def _run_translation(project_id, elements, project_type, model, backgrounder, overwrite):
    """Synchronni preklad bezici v thread poolu."""
    try:
        def on_progress(batch_num, total_batches, from_memory_count):
            _translate_progress[project_id].update({
                "batch": batch_num,
                "total_batches": total_batches,
                "from_memory": from_memory_count,
            })

        results = translate_batch(
            elements=elements,
            project_type=project_type,
            model=model,
            backgrounder=backgrounder,
            progress_callback=on_progress,
        )

        # Aplikovat preklady
        project = get_project(project_id)
        result_map = {r["id"]: r["czech"] for r in results}
        applied = 0
        for elem in project.elements:
            if elem.id in result_map:
                elem.czech = result_map[elem.id]
                elem.auto_translated = True
                if not elem.status:
                    elem.status = TextStatus.OVERIT
                applied += 1

        # CzechCorrector
        corrected_count = 0
        if _CORRECTOR_AVAILABLE and applied > 0:
            try:
                corrector = CzechCorrector()
                for elem in project.elements:
                    if elem.czech and elem.id in result_map:
                        result_c = corrector.correct(
                            elem.czech,
                            fix_typography=True,
                            check_spelling=False,
                            check_rules=False,
                        )
                        if result_c.auto_count > 0:
                            elem.czech = result_c.text
                            corrected_count += 1
                corrector.close()
            except Exception as e:
                logger.warning("CzechCorrector: %s", e)

        save_project(project)

        from_memory = _translate_progress[project_id].get("from_memory", 0)
        _translate_progress[project_id].update({
            "status": "done",
            "translated": applied,
            "from_memory": from_memory,
            "typo_corrected": corrected_count,
        })
        logger.info("Preklad dokoncen: %d prelozeno, %d z TM, %d typografie",
                    applied, from_memory, corrected_count)

    except Exception as e:
        logger.error("Chyba prekladu: %s", e, exc_info=True)
        _translate_progress[project_id].update({
            "status": "error",
            "error": str(e),
        })


@router.get("/api/projects/{project_id}/translate/progress")
async def api_translate_progress(project_id: str):
    """Polling progress prekladu."""
    progress = _translate_progress.get(project_id)
    if not progress:
        return {"status": "idle"}
    # Po dokonceni vrat projekt a smaz progress
    if progress["status"] in ("done", "error"):
        result = dict(progress)
        if progress["status"] == "done":
            project = get_project(project_id)
            result["project"] = project
        del _translate_progress[project_id]
        return result
    return progress


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
