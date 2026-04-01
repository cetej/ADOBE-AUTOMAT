"""Endpointy pro korektury — import oprav, preview, aplikace, verzovaný writeback."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from pathlib import Path
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from config import EXPORTS_DIR, UPLOADS_DIR
from models import ProjectType
from services.project_store import get_project, save_project
from services.correction_store import (
    CorrectionEntry, CorrectionRound,
    next_round_id, save_round, get_round, get_rounds,
)
from services.correction_applier import match_corrections, apply_corrections
from services.correction_parsers import parse_corrections_file
from services.idml_writeback import writeback_idml

logger = logging.getLogger(__name__)
router = APIRouter(tags=["corrections"])


# ─── Ruční zadání korektur ───────────────────────────────────

@router.post("/api/projects/{project_id}/corrections/manual")
async def api_corrections_manual(project_id: str, body: dict):
    """Ruční zadání korektur z UI.

    Body: {"entries": [{"element_id": "...", "after": "...", "notes": "..."}]}
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    raw_entries = body.get("entries", [])
    if not raw_entries:
        raise HTTPException(400, "Žádné opravy k zadání")

    entries = []
    for e in raw_entries:
        entries.append(CorrectionEntry(
            element_id=e.get("element_id", ""),
            before="",  # doplní se při matchingu
            after=e.get("after", ""),
            source="manual",
            confidence=1.0,
            notes=e.get("notes"),
        ))

    # Match a vytvoř kolo
    matched = match_corrections(entries, project.elements)
    rid = next_round_id(project_id)
    round_data = CorrectionRound(
        round_id=rid,
        source_type="manual",
        entries=matched,
    )
    save_round(project_id, round_data)

    # Zaregistruj v projektu
    project.corrections.append(rid)
    project.current_correction_round = len(project.corrections)
    save_project(project)

    return {
        "round_id": rid,
        "entries": [asdict(e) for e in matched],
        "stats": {
            "total": len(matched),
            "matched": sum(1 for e in matched if e.element_id),
            "unmatched": sum(1 for e in matched if not e.element_id),
        }
    }


# ─── Upload souboru s korekturami ────────────────────────────

@router.post("/api/projects/{project_id}/corrections/upload")
async def api_corrections_upload(project_id: str, file: UploadFile = File(...)):
    """Upload Excel/DOCX/PDF s korekturami → parse → preview (bez aplikace).

    Vrací parsed entries pro preview v UI. Uživatel potvrdí → /apply.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    # Validace typu souboru
    suffix = Path(file.filename or "").suffix.lower()
    type_map = {".xlsx": "excel", ".xls": "excel", ".docx": "docx", ".pdf": "pdf"}
    source_type = type_map.get(suffix)
    if not source_type:
        raise HTTPException(400, f"Nepodporovaný typ souboru: {suffix}. Povolené: .xlsx, .docx, .pdf")

    # Uložit soubor
    rid = next_round_id(project_id)
    upload_dir = UPLOADS_DIR / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"corrections_{rid}_{file.filename}"
    content = await file.read()
    upload_path.write_bytes(content)

    # Parse
    try:
        entries = parse_corrections_file(upload_path, source_type)
    except Exception as e:
        logger.error("Parse korektur selhal: %s", e)
        raise HTTPException(400, f"Nepodařilo se zpracovat soubor: {e}")

    if not entries:
        raise HTTPException(400, "V souboru nebyly nalezeny žádné korektury")

    # Match s elementy
    matched = match_corrections(entries, project.elements)

    # Uložit kolo (zatím applied=False)
    round_data = CorrectionRound(
        round_id=rid,
        source_file=file.filename,
        source_type=source_type,
        entries=matched,
        applied=False,
    )
    save_round(project_id, round_data)

    project.corrections.append(rid)
    project.current_correction_round = len(project.corrections)
    save_project(project)

    return {
        "round_id": rid,
        "source_file": file.filename,
        "entries": [asdict(e) for e in matched],
        "stats": {
            "total": len(matched),
            "matched": sum(1 for e in matched if e.element_id),
            "unmatched": sum(1 for e in matched if not e.element_id),
            "low_confidence": sum(1 for e in matched if 0 < e.confidence < 0.9),
        }
    }


# ─── Aplikace kola korektur ─────────────────────────────────

@router.post("/api/projects/{project_id}/corrections/{round_id}/apply")
async def api_corrections_apply(project_id: str, round_id: str):
    """Aplikuje korektury na elementy a vytvoří verzovaný IDML výstup."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    round_data = get_round(project_id, round_id)
    if not round_data:
        raise HTTPException(404, f"Kolo korektur {round_id} nenalezeno")

    if round_data.applied:
        raise HTTPException(400, f"Kolo {round_id} už bylo aplikováno")

    # Aplikuj korektury na elementy
    stats = apply_corrections(round_data.entries, project.elements)

    # Verzovaný IDML writeback (pokud má IDML)
    output_key = None
    writeback_result = None
    if project.type == ProjectType.IDML and project.idml_path:
        idml_path = Path(project.idml_path)
        if idml_path.exists():
            try:
                suffix = f"_CZ_{round_id}"
                writeback_result = writeback_idml(
                    idml_path=idml_path,
                    elements=project.elements,
                    project_id=project_id,
                    output_suffix=suffix,
                )
                output_key = f"idml_cz_{round_id}"
                if writeback_result.get("output_path"):
                    project.exports[output_key] = writeback_result["output_path"]
            except Exception as e:
                logger.error("Verzovaný writeback selhal: %s", e)
                # Korektury jsou aplikovány, writeback selhal — reportujeme obojí

    # Aktualizuj kolo
    round_data.applied = True
    round_data.output_key = output_key
    round_data.stats = stats
    save_round(project_id, round_data)

    # Uložit projekt s aktualizovanými elementy
    save_project(project)

    result = {
        "round_id": round_id,
        "stats": stats,
        "output_key": output_key,
    }
    if writeback_result:
        result["writeback"] = {
            "output_path": writeback_result.get("output_path"),
            "replaced": writeback_result.get("replaced", 0),
            "errors": writeback_result.get("errors", []),
        }

    # Pro MAP projekty: flag že je potřeba manuální writeback do Illustratoru
    if project.type == ProjectType.MAP:
        result["needs_map_writeback"] = True

    return result


# ─── Listing a detail ────────────────────────────────────────

@router.get("/api/projects/{project_id}/corrections")
async def api_corrections_list(project_id: str):
    """Vrátí seznam kol korektur (bez plných entries)."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    rounds = get_rounds(project_id)
    return {
        "rounds": [asdict(r) for r in rounds],
        "total": len(rounds),
    }


@router.get("/api/projects/{project_id}/corrections/{round_id}")
async def api_corrections_detail(project_id: str, round_id: str):
    """Vrátí detail jednoho kola včetně všech entries."""
    round_data = get_round(project_id, round_id)
    if not round_data:
        raise HTTPException(404, f"Kolo korektur {round_id} nenalezeno")
    return asdict(round_data)


@router.get("/api/projects/{project_id}/corrections/{round_id}/download")
async def api_corrections_download(project_id: str, round_id: str):
    """Stáhne verzovaný IDML soubor pro dané kolo korektur."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    output_key = f"idml_cz_{round_id}"
    output_path = project.exports.get(output_key)
    if not output_path:
        raise HTTPException(404, f"Výstup pro kolo {round_id} nenalezen")

    path = Path(output_path)
    if not path.exists():
        raise HTTPException(404, f"Soubor nenalezen: {path}")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
