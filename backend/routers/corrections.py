"""Endpointy pro korektury — import oprav, preview, aplikace, verzovaný writeback."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import json
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


# ─── AI korekce z volného textu ────────────────────────────

AI_CORRECTION_PROMPT = """Jsi jazykový korektor pro National Geographic Česko.
Dostaneš seznam přeložených textových elementů (id + český text) a instrukci od editora.

Instrukce editora:
{instruction}

## Elementy k revizi:
{elements_json}

## Úkol:
Projdi elementy a aplikuj instrukci editora. Vrať POUZE elementy, které se mění.
Pro každý změněný element vrať JSON objekt s těmito poli:
- "element_id": ID elementu
- "before": původní český text (přesná kopie)
- "after": opravený český text
- "notes": stručné vysvětlení změny (max 10 slov)

Vrať JSON pole: [{"element_id": "...", "before": "...", "after": "...", "notes": "..."}]
Pokud žádný element nevyžaduje změnu, vrať prázdné pole: []
Pouze JSON, žádný další text."""


@router.post("/api/projects/{project_id}/corrections/ai")
async def api_corrections_ai(project_id: str, body: dict):
    """AI korekce z volného textu — editor napíše instrukci, Claude ji aplikuje.

    Body: {"instruction": "všude kde je 'realizovat' změň na 'uskutečnit'"}
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    instruction = (body.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(400, "Chybí instrukce pro korektora")

    # Připrav elementy s českým textem
    elements_for_ai = []
    for el in project.elements:
        if el.czech:
            elements_for_ai.append({"id": el.id, "czech": el.czech})

    if not elements_for_ai:
        raise HTTPException(400, "Žádné přeložené elementy k revizi")

    # Omez na max 200 elementů aby prompt nebyl příliš velký
    if len(elements_for_ai) > 200:
        elements_for_ai = elements_for_ai[:200]
        logger.warning("AI korekce: omezeno na 200 elementů (projekt má %d)",
                        len([e for e in project.elements if e.czech]))

    # Claude API call
    from services.translation_service import get_api_key
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY není nastaven")

    from core.engine import get_engine
    from core.traces import TraceCollector, get_trace_store

    elements_json = json.dumps(elements_for_ai, ensure_ascii=False, indent=2)
    system = AI_CORRECTION_PROMPT.replace("{instruction}", instruction).replace("{elements_json}", elements_json)

    engine = get_engine()
    collector = TraceCollector(engine, get_trace_store(), module="corrections_ai")

    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: collector.generate(
                messages=[{"role": "user", "content": f"Aplikuj instrukci: {instruction}"}],
                model="claude-sonnet-4-6",
                system=system,
                max_tokens=4096,
            )
        )
    except Exception as e:
        logger.error("AI korekce selhaly: %s", e)
        raise HTTPException(500, f"Chyba při volání Claude API: {e}")

    # Parse odpovědi
    raw = result.content.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise HTTPException(500, "Claude nevrátil platný JSON")

    try:
        ai_entries = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as e:
        logger.error("AI korekce: neplatný JSON — %s", e)
        raise HTTPException(500, "Claude vrátil neplatný JSON")

    if not ai_entries:
        return {"round_id": None, "entries": [], "stats": {"total": 0, "matched": 0}}

    # Převeď na CorrectionEntry
    entries = []
    for ae in ai_entries:
        entries.append(CorrectionEntry(
            element_id=ae.get("element_id", ""),
            before=ae.get("before", ""),
            after=ae.get("after", ""),
            source="ai",
            confidence=1.0,
            notes=ae.get("notes"),
        ))

    # Match a validace (pro případ že Claude vrátil špatné element_id)
    matched = match_corrections(entries, project.elements)

    # Ulož kolo
    rid = next_round_id(project_id)
    round_data = CorrectionRound(
        round_id=rid,
        source_file=f"AI: {instruction[:80]}",
        source_type="ai",
        entries=matched,
        applied=False,
    )
    save_round(project_id, round_data)

    project.corrections.append(rid)
    project.current_correction_round = len(project.corrections)
    save_project(project)

    return {
        "round_id": rid,
        "source_file": f"AI: {instruction[:80]}",
        "entries": [asdict(e) for e in matched],
        "stats": {
            "total": len(matched),
            "matched": sum(1 for e in matched if e.element_id),
            "unmatched": sum(1 for e in matched if not e.element_id),
        }
    }


# ─── CzechCorrector auto-suggestions ──────────────────────

@router.post("/api/projects/{project_id}/corrections/auto-suggestions")
async def api_corrections_auto_suggestions(project_id: str):
    """Spustí CzechCorrector na přeložených elementech a vytvoří kolo návrhů.

    Detekuje anglicismy, false friends, typografické chyby.
    Vrací preview — editor potvrdí aplikaci přes /apply.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projekt nenalezen")

    # Import CzechCorrector
    try:
        from ngm_terminology.corrector import CzechCorrector
    except ImportError:
        raise HTTPException(501, "CzechCorrector není nainstalován (ngm_terminology)")

    from services.translation_service import get_protected_terms_cached
    protected = get_protected_terms_cached()

    elements_with_czech = [el for el in project.elements if el.czech]
    if not elements_with_czech:
        raise HTTPException(400, "Žádné přeložené elementy k analýze")

    # Spusť korektor na každém elementu
    entries = []
    try:
        with CzechCorrector(protected_terms=protected) as corrector:
            for el in elements_with_czech:
                result_c = corrector.correct(
                    el.czech,
                    fix_typography=True,
                    check_spelling=False,
                    check_rules=True,
                )
                # Typografické auto-opravy
                if result_c.auto_count > 0 and result_c.text != el.czech:
                    entries.append(CorrectionEntry(
                        element_id=el.id,
                        before=el.czech,
                        after=result_c.text,
                        source="corrector",
                        confidence=1.0,
                        notes=f"Typografie: {result_c.auto_count} oprav",
                    ))
                # Návrhy (anglicismy, false friends)
                if hasattr(result_c, 'suggestions'):
                    for s in result_c.suggestions:
                        if hasattr(s, 'corrected') and s.corrected:
                            # Aplikuj návrh do textu
                            fixed = el.czech.replace(s.original, s.corrected) if s.original else el.czech
                            if fixed != el.czech:
                                entries.append(CorrectionEntry(
                                    element_id=el.id,
                                    before=el.czech,
                                    after=fixed,
                                    source="corrector",
                                    confidence=0.9,
                                    notes=f"{s.type}: {s.rule}" if hasattr(s, 'rule') else s.type,
                                ))
    except Exception as e:
        logger.error("CzechCorrector selhal: %s", e)
        raise HTTPException(500, f"CzechCorrector selhal: {e}")

    if not entries:
        return {"round_id": None, "entries": [], "stats": {"total": 0}}

    # Deduplikuj — pokud stejný element má typografii i návrh, ponech jen ten s větší změnou
    seen = {}
    for entry in entries:
        existing = seen.get(entry.element_id)
        if not existing or len(entry.after) != len(existing.after):
            seen[entry.element_id] = entry
    deduped = list(seen.values())

    # Ulož kolo
    rid = next_round_id(project_id)
    round_data = CorrectionRound(
        round_id=rid,
        source_file="CzechCorrector (auto)",
        source_type="corrector",
        entries=deduped,
        applied=False,
    )
    save_round(project_id, round_data)

    project.corrections.append(rid)
    project.current_correction_round = len(project.corrections)
    save_project(project)

    return {
        "round_id": rid,
        "source_file": "CzechCorrector (auto)",
        "entries": [asdict(e) for e in deduped],
        "stats": {
            "total": len(deduped),
            "typography": sum(1 for e in deduped if e.confidence == 1.0),
            "suggestions": sum(1 for e in deduped if e.confidence < 1.0),
        }
    }
