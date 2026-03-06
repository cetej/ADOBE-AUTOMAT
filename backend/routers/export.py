"""Endpointy pro export prekladu — DOCX tabulka, CSV."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import csv
import io
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.project_store import get_project

logger = logging.getLogger(__name__)
router = APIRouter(tags=["export"])


@router.post("/api/projects/{project_id}/export/{format}")
async def api_export(project_id: str, format: str):
    """Export prekladu do CSV nebo JSON."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if format == "csv":
        return _export_csv(project)
    elif format == "json":
        return _export_json(project)
    else:
        raise HTTPException(400, f"Nepodporovany format: {format}. Podporovane: csv, json")


def _export_csv(project):
    """Export do CSV souboru."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "original", "czech", "status", "category", "story_id"])

    for el in project.elements:
        writer.writerow([
            el.id,
            el.contents,
            el.czech or "",
            el.status.value if el.status else "",
            el.category.value if el.category else "",
            el.story_id or "",
        ])

    output.seek(0)
    filename = f"{project.id}_translations.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _export_json(project):
    """Export jako JSON pole prekladu."""
    data = []
    for el in project.elements:
        if el.czech:
            data.append({
                "id": el.id,
                "original": el.contents,
                "czech": el.czech,
                "status": el.status.value if el.status else None,
                "category": el.category.value if el.category else None,
            })
    return {"project_id": project.id, "total": len(data), "translations": data}
