"""Endpointy pro extrakci textu (MAP i IDML) a upload IDML souboru."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from config import UPLOADS_DIR
from models import ProjectPhase, ProjectType
from services.project_store import get_project, save_project
from services.text_extractor import extract_from_illustrator, raw_to_elements
from services.category_engine import categorize_elements

logger = logging.getLogger(__name__)

router = APIRouter(tags=["extract"])


# === Extrakce ===

@router.post("/api/projects/{project_id}/extract")
async def api_extract(project_id: str):
    """Extrakce textu z Illustratoru (MAP) nebo IDML."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project.type == ProjectType.MAP:
        return await _extract_map(project)
    elif project.type == ProjectType.IDML:
        return await _extract_idml(project)
    else:
        raise HTTPException(400, f"Unknown project type: {project.type}")


async def _extract_map(project):
    """Extrakce textu z Illustratoru pres ExtendScript."""
    try:
        extraction = await asyncio.get_running_loop().run_in_executor(
            None, extract_from_illustrator
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Illustrator extraction failed: {e}")

    raw_layers = extraction["layers"]
    doc_info = extraction.get("document")

    # Ulozit info o zdrojovem dokumentu
    if doc_info:
        project.source_file = doc_info.get("name", "")
        ai_path = doc_info.get("path", "")
        if ai_path:
            project.idml_path = ai_path  # reuse field pro .ai cestu
        logger.info("MAP source: %s (%s)", project.source_file, ai_path)

    elements = raw_to_elements(raw_layers)
    if not elements:
        raise HTTPException(422, "No text elements found in the document")

    categorized = categorize_elements(elements)
    logger.info("Categorized %d/%d elements", categorized, len(elements))

    project.elements = elements
    project.phase = ProjectPhase.EXTRACTED
    save_project(project)

    return project


async def _extract_idml(project):
    """Extrakce textu z IDML souboru."""
    if not project.idml_path:
        raise HTTPException(422, "No IDML file uploaded. Upload first via /upload-idml")

    idml_path = Path(project.idml_path)
    if not idml_path.exists():
        raise HTTPException(404, f"IDML file not found: {idml_path}")

    from services.idml_processor import unpack_idml, cleanup_temp
    from services.idml_extractor import extract_stories

    # Rozbalit do temp adresare
    temp_dir = None
    try:
        temp_dir = unpack_idml(idml_path)
        elements = extract_stories(temp_dir)
    except Exception as e:
        raise HTTPException(500, f"IDML extraction failed: {e}")
    finally:
        if temp_dir:
            cleanup_temp(temp_dir)

    if not elements:
        raise HTTPException(422, "No text elements found in the IDML file")

    project.elements = elements
    project.phase = ProjectPhase.EXTRACTED
    save_project(project)

    return project


# === Upload IDML ===

@router.post("/api/projects/{project_id}/upload-idml")
async def api_upload_idml(project_id: str, file: UploadFile = File(...)):
    """Upload IDML souboru do projektu."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project.type != ProjectType.IDML:
        raise HTTPException(400, "Upload IDML is only for IDML projects")

    if not file.filename or not file.filename.lower().endswith(".idml"):
        raise HTTPException(400, "File must have .idml extension")

    # Ulozit do uploads/{project_id}/
    project_upload_dir = UPLOADS_DIR / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    dest = project_upload_dir / file.filename
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    # Zakladni validace — je to ZIP?
    from services.idml_validator import validate_packed_idml
    validation = validate_packed_idml(dest)
    if not validation["valid"]:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            422,
            f"Invalid IDML file: {'; '.join(validation['errors'][:3])}"
        )

    project.idml_path = str(dest)
    project.source_file = file.filename
    save_project(project)

    return project


@router.post("/api/projects/{project_id}/upload-translation")
async def api_upload_translation(project_id: str, file: UploadFile = File(...)):
    """Upload souboru s CZ prekladem (txt/docx). Automaticky parsuje a páruje s IDML."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project.type != ProjectType.IDML:
        raise HTTPException(400, "Translation upload is only for IDML projects")

    if not project.elements:
        raise HTTPException(422, "No IDML elements extracted yet. Extract first.")

    # Ulozit soubor
    project_upload_dir = UPLOADS_DIR / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    dest = project_upload_dir / (file.filename or "translation.docx")
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    project.translation_doc = str(dest)

    # Automaticky parsovat a párovat DOCX s IDML elementy
    match_result = None
    if str(dest).lower().endswith(".docx"):
        try:
            from services.docx_parser import parse_docx
            from services.docx_matcher import match_docx_to_idml

            docx_result = parse_docx(dest)
            match_result = match_docx_to_idml(project.elements, docx_result)
            logger.info("DOCX matching: %d/%d stories, %d/%d elements s CZ",
                        match_result.matched_stories, match_result.total_stories,
                        match_result.elements_with_czech, match_result.total_elements)
        except Exception as e:
            logger.error("DOCX matching failed: %s", e, exc_info=True)
            # Neupadne — soubor je uložen, matching se dá spustit znovu

    save_project(project)

    # Vrátit projekt + matching statistiky
    response = project.model_dump()
    if match_result:
        response["match_stats"] = {
            "matched_stories": match_result.matched_stories,
            "total_stories": match_result.total_stories,
            "elements_with_czech": match_result.elements_with_czech,
            "total_elements": match_result.total_elements,
            "matches": match_result.matches[:10],  # prvních 10 pro náhled
        }
    return response


# === Upload zdrojoveho PDF ===

@router.post("/api/projects/{project_id}/upload-source-pdf")
async def api_upload_source_pdf(project_id: str, file: UploadFile = File(...)):
    """Upload zdrojoveho anglickeho PDF (RTT). Aktualizuje texty + ulozi backgrounder."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project.type != ProjectType.IDML:
        raise HTTPException(400, "Source PDF upload is only for IDML projects")

    if not project.elements:
        raise HTTPException(422, "No IDML elements extracted yet. Extract IDML first.")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must have .pdf extension")

    # Ulozit soubor
    project_upload_dir = UPLOADS_DIR / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    dest = project_upload_dir / file.filename
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    project.source_pdf = str(dest)

    # Parsovat PDF a matchovat s IDML
    match_stats = None
    try:
        from services.pdf_source_parser import parse_source_pdf
        from services.pdf_source_matcher import match_pdf_to_idml

        pdf_result = parse_source_pdf(dest)

        # Ulozit backgrounder pro kontext prekladu
        if pdf_result.backgrounder_text:
            project.backgrounder = pdf_result.backgrounder_text
            logger.info("Backgrounder extracted: %d pages, %d chars",
                        pdf_result.backgrounder_pages, len(project.backgrounder))

        # Matchovat a aktualizovat texty
        match_stats = match_pdf_to_idml(project.elements, pdf_result)

        logger.info("PDF source matching: %d matched, %d updated, %d paragraphs",
                    match_stats["matched"], match_stats["updated"],
                    match_stats["total_paragraphs"])
    except Exception as e:
        logger.error("PDF source processing failed: %s", e, exc_info=True)

    save_project(project)

    response = project.model_dump()
    if match_stats:
        response["pdf_match_stats"] = match_stats
    return response


# === Kategorizace ===

@router.post("/api/projects/{project_id}/categorize")
async def api_categorize(project_id: str):
    """Spusti auto-kategorizaci na existujicich elementech."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if not project.elements:
        raise HTTPException(422, "No elements to categorize")

    categorized = categorize_elements(project.elements)
    if project.phase == ProjectPhase.CREATED:
        project.phase = ProjectPhase.CATEGORIZED
    save_project(project)

    return {"categorized": categorized, "total": len(project.elements)}
