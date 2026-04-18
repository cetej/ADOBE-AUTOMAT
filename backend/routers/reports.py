"""Reports router — přístup k výstupům jednotlivých pipeline fází.

Endpoints:
- GET /api/projects/{id}/reports                     — list dostupných reportů + metadata
- GET /api/projects/{id}/reports/pipeline            — markdown pipeline_report.md (JSON {markdown, ...})
- GET /api/projects/{id}/reports/pipeline/download   — ke stažení jako .md soubor
- GET /api/projects/{id}/reports/glossary-fixes      — glossary_fixes.json (všechny běhy)
- GET /api/projects/{id}/reports/glossary-fixes/download  — ke stažení jako .json soubor
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import PROJECTS_DIR

logger = logging.getLogger(__name__)
router = APIRouter()


def _project_dir(project_id: str):
    d = PROJECTS_DIR / project_id
    if not d.exists():
        raise HTTPException(404, f"Projekt {project_id} neexistuje")
    return d


def _mtime_iso(path) -> str:
    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).astimezone().isoformat(timespec="seconds")
    except OSError:
        return ""


@router.get("/api/projects/{project_id}/reports")
def list_reports(project_id: str):
    """Vrátí seznam dostupných reportů pro projekt."""
    d = _project_dir(project_id)
    reports = []

    pipeline_md = d / "pipeline_report.md"
    if pipeline_md.exists():
        reports.append({
            "id": "pipeline",
            "title": "Pipeline — tabulky oprav per fáze",
            "format": "markdown",
            "size_bytes": pipeline_md.stat().st_size,
            "updated_at": _mtime_iso(pipeline_md),
        })

    glossary_json = d / "glossary_fixes.json"
    if glossary_json.exists():
        runs = 0
        total_fixes = 0
        try:
            data = json.loads(glossary_json.read_text(encoding="utf-8"))
            if isinstance(data, list):
                runs = len(data)
                total_fixes = sum(len(r.get("fixes", [])) for r in data)
        except (json.JSONDecodeError, OSError):
            pass
        reports.append({
            "id": "glossary-fixes",
            "title": "Glossary enforcer — DB substituce překladu",
            "format": "json",
            "size_bytes": glossary_json.stat().st_size,
            "updated_at": _mtime_iso(glossary_json),
            "runs": runs,
            "total_fixes": total_fixes,
        })

    corrector_json = d / "corrector_suggestions.json"
    if corrector_json.exists():
        reports.append({
            "id": "corrector-suggestions",
            "title": "CzechCorrector — návrhy ke schválení",
            "format": "json",
            "size_bytes": corrector_json.stat().st_size,
            "updated_at": _mtime_iso(corrector_json),
        })

    changes_json = d / "pipeline_changes.json"
    if changes_json.exists():
        reports.append({
            "id": "pipeline-changes",
            "title": "Pipeline — change log (before/after per element)",
            "format": "json",
            "size_bytes": changes_json.stat().st_size,
            "updated_at": _mtime_iso(changes_json),
        })

    return {"project_id": project_id, "reports": reports}


@router.get("/api/projects/{project_id}/reports/pipeline")
def get_pipeline_report(project_id: str):
    """Vrátí obsah pipeline_report.md jako JSON."""
    d = _project_dir(project_id)
    path = d / "pipeline_report.md"
    if not path.exists():
        raise HTTPException(404, "Pipeline report zatím neexistuje — spusť pipeline v Editoru")
    return {
        "project_id": project_id,
        "markdown": path.read_text(encoding="utf-8"),
        "updated_at": _mtime_iso(path),
        "size_bytes": path.stat().st_size,
    }


@router.get("/api/projects/{project_id}/reports/pipeline/download")
def download_pipeline_report(project_id: str):
    """Vrátí pipeline_report.md jako stažitelný soubor."""
    d = _project_dir(project_id)
    path = d / "pipeline_report.md"
    if not path.exists():
        raise HTTPException(404, "Pipeline report neexistuje")
    return FileResponse(
        path=str(path),
        media_type="text/markdown; charset=utf-8",
        filename=f"{project_id}_pipeline_report.md",
    )


@router.get("/api/projects/{project_id}/reports/glossary-fixes")
def get_glossary_fixes(project_id: str):
    """Vrátí glossary enforcer fixes JSON."""
    d = _project_dir(project_id)
    path = d / "glossary_fixes.json"
    if not path.exists():
        return {"project_id": project_id, "runs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(500, f"Nelze načíst glossary_fixes.json: {e}")
    return {
        "project_id": project_id,
        "runs": data if isinstance(data, list) else [],
        "updated_at": _mtime_iso(path),
    }


@router.get("/api/projects/{project_id}/reports/glossary-fixes/download")
def download_glossary_fixes(project_id: str):
    """Vrátí glossary_fixes.json jako stažitelný soubor."""
    d = _project_dir(project_id)
    path = d / "glossary_fixes.json"
    if not path.exists():
        raise HTTPException(404, "Glossary fixes report neexistuje")
    return FileResponse(
        path=str(path),
        media_type="application/json; charset=utf-8",
        filename=f"{project_id}_glossary_fixes.json",
    )


@router.get("/api/projects/{project_id}/reports/corrector-suggestions/download")
def download_corrector_suggestions(project_id: str):
    """Vrátí corrector_suggestions.json jako stažitelný soubor."""
    d = _project_dir(project_id)
    path = d / "corrector_suggestions.json"
    if not path.exists():
        raise HTTPException(404, "Corrector suggestions neexistuje")
    return FileResponse(
        path=str(path),
        media_type="application/json; charset=utf-8",
        filename=f"{project_id}_corrector_suggestions.json",
    )


@router.get("/api/projects/{project_id}/reports/pipeline-changes/download")
def download_pipeline_changes(project_id: str):
    """Vrátí pipeline_changes.json jako stažitelný soubor."""
    d = _project_dir(project_id)
    path = d / "pipeline_changes.json"
    if not path.exists():
        raise HTTPException(404, "Pipeline changes neexistuje")
    return FileResponse(
        path=str(path),
        media_type="application/json; charset=utf-8",
        filename=f"{project_id}_pipeline_changes.json",
    )
