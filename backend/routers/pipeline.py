"""Endpointy pro text processing pipeline (fáze 2-6) s polling progress."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import logging
import threading
import time
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from services.project_store import get_project, save_project
from services.translation_service import get_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pipeline"])

# In-memory progress store (per project)
_pipeline_progress = {}


class PipelineRequest(BaseModel):
    """Požadavek na spuštění text pipeline."""
    phases: list[int] = [3, 4, 5, 6]
    phase6_model: Optional[str] = None
    term_notes: Optional[str] = None


PHASE_LABELS = {
    2: "Kontrola úplnosti",
    3: "Ověření termínů",
    4: "Kontrola faktů",
    5: "Jazyk a kontext",
    6: "Stylistika",
}


@router.post("/api/projects/{project_id}/process-text")
def api_process_text(project_id: str, req: PipelineRequest = PipelineRequest()):
    """Spustí pipeline na pozadí a vrátí okamžitě. Průběh přes GET /progress."""
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY není nastaven.")

    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    valid_phases = {2, 3, 4, 5, 6}
    invalid = set(req.phases) - valid_phases
    if invalid:
        raise HTTPException(400, f"Neplatné fáze: {invalid}")

    has_czech = any(e.czech and e.czech.strip() for e in project.elements)
    if not has_czech:
        raise HTTPException(400, "Žádné přeložené elementy.")

    # Už běží?
    if project_id in _pipeline_progress and _pipeline_progress[project_id].get("status") == "running":
        raise HTTPException(409, "Pipeline již běží.")

    try:
        from services.text_pipeline import TextPipeline, PipelineConfig
    except ImportError as e:
        raise HTTPException(500, f"Text pipeline není dostupný: {e}")

    phases = sorted(req.phases)

    # Snapshot textů před pipeline
    texts_before = {
        e.id: e.czech for e in project.elements
        if e.czech and e.czech.strip()
    }

    # Inicializovat progress
    _pipeline_progress[project_id] = {
        "status": "running",
        "started_at": time.time(),
        "phases": {str(p): {"name": PHASE_LABELS.get(p, f"Fáze {p}"), "status": "waiting"} for p in phases},
        "current_phase": None,
        "result": None,
        "change_log": [],
    }

    def run_pipeline():
        """Běží v thread."""
        progress = _pipeline_progress[project_id]

        def progress_cb(phase, phase_name, status, extra=None):
            progress["current_phase"] = phase
            progress["phases"][str(phase)] = {
                "name": phase_name,
                "status": status,
                **(extra or {}),
            }

        config = PipelineConfig(
            phases=phases,
            api_key=api_key,
            phase6_model=req.phase6_model,
        )
        pipeline = TextPipeline(config=config)

        try:
            result = pipeline.run(project, progress_callback=progress_cb)

            # Uložit projekt
            if result.elements_updated > 0:
                save_project(project)

            # Change log
            change_log = []
            for elem in project.elements:
                old = texts_before.get(elem.id)
                new = elem.czech
                if old and new and old != new:
                    change_log.append({
                        "id": elem.id,
                        "layer": elem.layer_name,
                        "before": old,
                        "after": new,
                    })

            # Uložit change log do souboru
            if change_log:
                from config import PROJECTS_DIR
                log_path = PROJECTS_DIR / project_id / "pipeline_changes.json"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(
                    json.dumps(change_log, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

            # Phase details
            phase_details = []
            for pr in result.phases_completed + result.phases_failed:
                phase_details.append({
                    "phase": pr.phase,
                    "name": pr.phase_name,
                    "success": pr.success,
                    "duration_s": pr.duration_s,
                    "tokens": pr.tokens_used,
                    "web_searches": pr.web_searches,
                    "error": pr.error,
                })

            progress["status"] = "done"
            progress["result"] = {
                "success": result.success,
                "phases": phase_details,
                "elements_updated": result.elements_updated,
                "total_tokens": result.total_tokens,
                "total_duration_s": result.total_duration_s,
                "error": result.error,
                "change_log": change_log,
            }

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            progress["status"] = "error"
            progress["result"] = {"success": False, "error": str(e)}

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return {
        "status": "started",
        "phases": phases,
        "message": f"Pipeline spuštěna ({len(phases)} fází, {len(texts_before)} elementů)",
    }


@router.get("/api/projects/{project_id}/process-text/progress")
def api_pipeline_progress(project_id: str):
    """Vrátí aktuální stav pipeline (polling)."""
    progress = _pipeline_progress.get(project_id)
    if not progress:
        return {"status": "idle"}

    result = {
        "status": progress["status"],
        "current_phase": progress.get("current_phase"),
        "phases": progress.get("phases", {}),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }

    if progress["status"] in ("done", "error"):
        result["result"] = progress.get("result")
        # Přidat aktualizovaný projekt
        if progress["status"] == "done":
            project = get_project(project_id)
            if project:
                result["project"] = project.model_dump()

    return result


@router.get("/api/projects/{project_id}/pipeline-changes")
def api_get_pipeline_changes(project_id: str):
    """Vrátí protokol změn z posledního běhu pipeline."""
    from config import PROJECTS_DIR
    log_path = PROJECTS_DIR / project_id / "pipeline_changes.json"
    if not log_path.exists():
        return {"changes": [], "message": "Žádný protokol změn"}
    changes = json.loads(log_path.read_text(encoding="utf-8"))
    return {"changes": changes, "count": len(changes)}
