"""REST API endpointy pro Layout Generator.

Session 1-7 endpointy:
- POST /api/layout/create-project — nový layout projekt
- POST /api/layout/upload-images/{project_id} — upload fotek (multipart)
- POST /api/layout/upload-text/{project_id} — upload textu
- POST /api/layout/plan/{project_id} — spustí layout planner
- GET  /api/layout/plan/{project_id}/progress — polling progress
- POST /api/layout/generate/{project_id} — z LayoutPlan vygeneruje IDML
- GET  /api/layout/generate/{project_id}/progress — polling progress
- GET  /api/layout/download/{project_id} — stáhne hotový IDML
- POST /api/layout/analyze-template — upload IDML vzoru → analýza
- GET  /api/layout/templates — seznam style profiles
- GET  /api/layout/patterns — seznam spread patterns
- GET  /api/layout/projects — seznam layout projektů
- GET  /api/layout/projects/{project_id} — detail projektu
- DELETE /api/layout/projects/{project_id} — smazání projektu
- GET  /api/layout/thumbnail/{project_id}/{filename} — thumbnail fotky
- POST /api/layout/update-plan/{project_id} — update layout plánu (reorder, swap)
- GET  /api/layout/validate/{project_id} — validace projektu
- GET  /api/layout/plan-detail/{project_id} — detail plánu se sloty a fotkama

Session 8 endpointy:
- POST /api/layout/create-style-from-template — upload IDML → nový style profile
- DELETE /api/layout/templates/{profile_id} — smazání custom profilu
- POST /api/layout/batch-plan/{project_id} — batch varianty plánu
- POST /api/layout/batch-generate/{project_id} — batch generování IDML
- GET  /api/layout/batch-generate/{project_id}/progress — polling batch progress
- GET  /api/layout/batch-download/{project_id}/{variant} — stáhne variantu
- POST /api/layout/preview-pdf/{project_id} — generování PDF náhledu
- GET  /api/layout/preview-pdf/{project_id}/download — stáhne PDF
- POST /api/layout/match-captions/{project_id} — AI caption matching
- GET  /api/layout/match-captions/{project_id}/progress — polling caption matching

Session 9 endpointy:
- GET  /api/layout/patterns?detail=true — seznam patterns (s detaily slotů)
- GET  /api/layout/patterns/{pattern_id} — detail jednoho patternu
- POST /api/layout/patterns — vytvoří nový custom pattern
- PUT  /api/layout/patterns/{pattern_id} — update custom patternu
- DELETE /api/layout/patterns/{pattern_id} — smazání custom patternu
- POST /api/layout/patterns/validate — validace patternu bez uložení
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import logging
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import DATA_DIR, EXPORTS_DIR
from services.translation_service import get_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["layout"])

# Adresář pro layout projekty
LAYOUT_DIR = DATA_DIR / "layout_projects"
LAYOUT_DIR.mkdir(parents=True, exist_ok=True)

# Výchozí skeleton IDML — první dostupný IDML z datasetu
SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "input" / "samples"

# In-memory progress store
_layout_progress = {}


# --- Request/Response modely ---

class LayoutProjectCreate(BaseModel):
    name: str
    style_profile: str = "ng_feature"


class PlanRequest(BaseModel):
    num_pages: int | str = "auto"
    use_ai: bool = False
    style_profile: Optional[str] = None


class GenerateRequest(BaseModel):
    skeleton_idml: Optional[str] = None  # cesta ke skeleton; None = auto


# --- Helpers ---

def _project_dir(project_id: str) -> Path:
    """Vrátí adresář layout projektu."""
    safe_id = "".join(c for c in project_id if c.isalnum() or c in "-_")
    if not safe_id:
        raise ValueError(f"Neplatné project_id: {project_id!r}")
    d = LAYOUT_DIR / safe_id
    if not d.resolve().is_relative_to(LAYOUT_DIR.resolve()):
        raise ValueError(f"Path traversal: {project_id!r}")
    return d


def _load_project_meta(project_id: str) -> dict:
    """Načte metadata layout projektu."""
    meta_path = _project_dir(project_id) / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, f"Layout projekt neexistuje: {project_id}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _save_project_meta(project_id: str, meta: dict) -> None:
    """Uloží metadata layout projektu."""
    meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta_path = _project_dir(project_id) / "meta.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _find_skeleton_idml() -> Optional[Path]:
    """Najde vhodný skeleton IDML z datasetu. Preferuje menší (MF) soubory."""
    if not SAMPLES_DIR.exists():
        return None
    idmls = sorted(SAMPLES_DIR.glob("*.idml"), key=lambda p: p.stat().st_size)
    for idml in idmls:
        # Preferuj MF (menší, čistější) nebo EP
        if "MF" in idml.name or "EP" in idml.name:
            return idml
    return idmls[0] if idmls else None


# --- Endpointy ---

@router.post("/api/layout/create-project")
def api_create_layout_project(req: LayoutProjectCreate):
    """Vytvoří nový layout projekt."""
    project_id = req.name.lower().strip()
    project_id = "".join(c if c.isalnum() or c in " -_" else "" for c in project_id)
    project_id = "-".join(project_id.split())[:64]
    if not project_id:
        project_id = f"layout-{uuid.uuid4().hex[:8]}"

    # Unikátnost
    base_id = project_id
    counter = 1
    while _project_dir(project_id).exists():
        project_id = f"{base_id}-{counter}"
        counter += 1

    d = _project_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "images").mkdir(exist_ok=True)

    meta = {
        "id": project_id,
        "name": req.name,
        "style_profile": req.style_profile,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "phase": "created",
        "images": [],
        "text_file": None,
        "plan": None,
        "generated_idml": None,
    }
    _save_project_meta(project_id, meta)

    return {"project_id": project_id, "meta": meta}


@router.get("/api/layout/projects")
def api_list_layout_projects():
    """Seznam layout projektů."""
    projects = []
    for d in sorted(LAYOUT_DIR.iterdir()):
        meta_path = d / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                projects.append(meta)
            except Exception:
                continue
    return {"projects": projects}


@router.get("/api/layout/projects/{project_id}")
def api_get_layout_project(project_id: str):
    """Detail layout projektu."""
    meta = _load_project_meta(project_id)
    return {"project": meta}


@router.delete("/api/layout/projects/{project_id}")
def api_delete_layout_project(project_id: str):
    """Smaže layout projekt."""
    d = _project_dir(project_id)
    if not d.exists():
        raise HTTPException(404, "Projekt neexistuje")
    shutil.rmtree(d)
    return {"deleted": project_id}


@router.post("/api/layout/upload-images/{project_id}")
async def api_upload_images(project_id: str, files: list[UploadFile] = File(...)):
    """Upload fotek do layout projektu."""
    meta = _load_project_meta(project_id)
    images_dir = _project_dir(project_id) / "images"
    images_dir.mkdir(exist_ok=True)

    uploaded = []
    for f in files:
        if not f.filename:
            continue
        # Bezpečný filename
        safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in f.filename)
        dest = images_dir / safe_name
        # Deduplikace
        counter = 1
        while dest.exists():
            stem = dest.stem
            dest = images_dir / f"{stem}_{counter}{dest.suffix}"
            counter += 1

        content = await f.read()
        dest.write_bytes(content)
        uploaded.append(str(dest))

    # Analyzovat nahrané fotky
    from services.layout.image_analyzer import analyze_batch
    all_images_paths = list(images_dir.glob("*"))
    all_images_paths = [p for p in all_images_paths if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".gif")]
    image_infos = analyze_batch([str(p) for p in all_images_paths])

    meta["images"] = [img.model_dump() for img in image_infos]
    meta["phase"] = "images_uploaded"
    _save_project_meta(project_id, meta)

    return {
        "uploaded": len(uploaded),
        "total_images": len(image_infos),
        "images": [{"filename": img.filename, "priority": img.priority, "orientation": img.orientation, "megapixels": img.megapixels} for img in image_infos],
    }


@router.post("/api/layout/upload-text/{project_id}")
async def api_upload_text(
    project_id: str,
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Upload textu — buď jako form field `text` nebo soubor."""
    meta = _load_project_meta(project_id)
    d = _project_dir(project_id)

    raw_text = ""
    if file and file.filename:
        content = await file.read()
        raw_text = content.decode("utf-8", errors="replace")
        text_path = d / file.filename
        text_path.write_text(raw_text, encoding="utf-8")
        meta["text_file"] = file.filename
    elif text:
        raw_text = text
        text_path = d / "article.txt"
        text_path.write_text(raw_text, encoding="utf-8")
        meta["text_file"] = "article.txt"
    else:
        raise HTTPException(400, "Zadej text nebo nahraj soubor")

    # Parsovat text
    from services.layout.text_parser import parse_article_text, estimate_text_space
    article = parse_article_text(raw_text)
    estimate = estimate_text_space(article)

    meta["article"] = article.model_dump()
    meta["text_estimate"] = estimate.model_dump()
    meta["phase"] = "text_uploaded"
    _save_project_meta(project_id, meta)

    return {
        "headline": article.headline[:100] if article.headline else "",
        "body_paragraphs": len(article.body_paragraphs),
        "total_chars": article.total_chars,
        "estimated_spreads": estimate.estimated_total_spreads,
        "pull_quotes": len(article.pull_quotes),
        "captions": len(article.captions),
    }


@router.post("/api/layout/plan/{project_id}")
def api_plan_layout(project_id: str, req: PlanRequest = PlanRequest()):
    """Spustí layout planner na pozadí."""
    meta = _load_project_meta(project_id)

    if not meta.get("images"):
        raise HTTPException(400, "Nejdřív nahraj fotky")
    if not meta.get("article"):
        raise HTTPException(400, "Nejdřív nahraj text")

    # Už běží?
    if project_id in _layout_progress and _layout_progress[project_id].get("status") == "running":
        raise HTTPException(409, "Plánování již běží")

    style_profile = req.style_profile or meta.get("style_profile", "ng_feature")
    api_key = get_api_key() if req.use_ai else None

    _layout_progress[project_id] = {
        "status": "running",
        "stage": "planning",
        "started_at": time.time(),
        "message": "Plánuji layout...",
        "result": None,
    }

    def run_plan():
        progress = _layout_progress[project_id]
        try:
            from models_layout import ImageInfo, ArticleText
            from services.layout.layout_planner import plan_layout

            # Rekonstruovat objekty z uloženého JSON
            images = [ImageInfo(**img) for img in meta["images"]]
            article = ArticleText(**meta["article"])

            progress["message"] = f"Plánuji layout pro {len(images)} fotek, {article.total_chars} znaků..."

            plan = plan_layout(
                images=images,
                text=article,
                style_profile_id=style_profile,
                num_pages=req.num_pages,
                project_id=project_id,
                use_ai=req.use_ai,
                api_key=api_key,
            )

            # Uložit plán
            plan_data = plan.model_dump()
            plan_path = _project_dir(project_id) / "layout_plan.json"
            plan_path.write_text(
                json.dumps(plan_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            meta["plan"] = plan_data
            meta["phase"] = "planned"
            _save_project_meta(project_id, meta)

            progress["status"] = "done"
            progress["message"] = f"Layout naplánován: {plan.total_pages} stran, {len(plan.spreads)} spreadů"
            progress["result"] = {
                "total_pages": plan.total_pages,
                "spreads": len(plan.spreads),
                "spread_types": [s.spread_type for s in plan.spreads],
                "plan": plan_data,
            }

        except Exception as e:
            logger.error(f"Layout planning error: {e}", exc_info=True)
            progress["status"] = "error"
            progress["message"] = str(e)
            progress["result"] = {"error": str(e)}

    thread = threading.Thread(target=run_plan, daemon=True)
    thread.start()

    return {"status": "started", "message": "Plánování layoutu spuštěno"}


@router.get("/api/layout/plan/{project_id}/progress")
def api_plan_progress(project_id: str):
    """Polling progress plánování."""
    progress = _layout_progress.get(project_id)
    if not progress or progress.get("stage") != "planning":
        return {"status": "idle"}

    result = {
        "status": progress["status"],
        "message": progress.get("message", ""),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }
    if progress["status"] in ("done", "error"):
        result["result"] = progress.get("result")
    return result


@router.post("/api/layout/generate/{project_id}")
def api_generate_idml(project_id: str, req: GenerateRequest = GenerateRequest()):
    """Vygeneruje IDML z layout plánu."""
    meta = _load_project_meta(project_id)

    if not meta.get("plan"):
        raise HTTPException(400, "Nejdřív spusť plánování")

    # Skeleton IDML
    skeleton = None
    if req.skeleton_idml:
        skeleton = Path(req.skeleton_idml)
        if not skeleton.exists():
            raise HTTPException(400, f"Skeleton IDML neexistuje: {req.skeleton_idml}")
    else:
        skeleton = _find_skeleton_idml()
        if not skeleton:
            raise HTTPException(400, "Žádný skeleton IDML k dispozici. Nahraj IDML vzor nebo zkontroluj input/samples/")

    # Už běží?
    gen_key = f"{project_id}_gen"
    if gen_key in _layout_progress and _layout_progress[gen_key].get("status") == "running":
        raise HTTPException(409, "Generování již běží")

    _layout_progress[gen_key] = {
        "status": "running",
        "stage": "generating",
        "started_at": time.time(),
        "message": "Generuji IDML...",
        "result": None,
    }

    skeleton_str = str(skeleton)

    def run_generate():
        progress = _layout_progress[gen_key]
        try:
            from models_layout import LayoutPlan, ArticleText
            from services.layout.idml_builder import build_from_plan

            plan = LayoutPlan(**meta["plan"])
            article = ArticleText(**meta["article"])

            progress["message"] = "Sestavuji text sekce..."

            # Sestavit text_sections mapování
            text_sections = {}
            # Headline, deck, byline
            if article.headline:
                text_sections["headline"] = article.headline
            if article.deck:
                text_sections["deck"] = article.deck
            if article.byline:
                text_sections["byline"] = article.byline
            # Body paragraphs
            for i, para in enumerate(article.body_paragraphs):
                text_sections[f"body_{i}"] = para
            # Captions
            for i, cap in enumerate(article.captions):
                text_sections[f"caption_{i}"] = cap
            # Pull quotes
            for i, pq in enumerate(article.pull_quotes):
                text_sections[f"pullquote_{i}"] = pq

            # Image paths per spread
            image_paths = {}
            images_dir = _project_dir(project_id) / "images"
            for spread in plan.spreads:
                if spread.assigned_images:
                    spread_imgs = []
                    for img_filename in spread.assigned_images:
                        img_path = images_dir / img_filename
                        if img_path.exists():
                            spread_imgs.append(str(img_path))
                        else:
                            # Zkusit najít podle filename v info
                            for info in spread.assigned_image_infos or []:
                                p = Path(info.get("path", "")) if isinstance(info, dict) else Path(info.path)
                                if p.exists():
                                    spread_imgs.append(str(p))
                                    break
                    if spread_imgs:
                        image_paths[str(spread.spread_index)] = spread_imgs

            progress["message"] = f"Generuji IDML ({len(plan.spreads)} spreadů)..."

            output_path = _project_dir(project_id) / f"{project_id}.idml"
            result_path = build_from_plan(
                layout_plan=plan,
                skeleton_idml=skeleton_str,
                output_path=str(output_path),
                text_sections=text_sections,
                image_paths=image_paths,
            )

            # Kopie do exports
            export_path = EXPORTS_DIR / f"{project_id}.idml"
            shutil.copy2(result_path, export_path)

            meta["generated_idml"] = str(result_path)
            meta["phase"] = "generated"
            _save_project_meta(project_id, meta)

            progress["status"] = "done"
            progress["message"] = f"IDML vygenerován: {result_path.name}"
            progress["result"] = {
                "idml_path": str(result_path),
                "export_path": str(export_path),
                "size_kb": round(result_path.stat().st_size / 1024, 1),
            }

        except Exception as e:
            logger.error(f"IDML generation error: {e}", exc_info=True)
            progress["status"] = "error"
            progress["message"] = str(e)
            progress["result"] = {"error": str(e)}

    thread = threading.Thread(target=run_generate, daemon=True)
    thread.start()

    return {"status": "started", "message": "Generování IDML spuštěno"}


@router.get("/api/layout/generate/{project_id}/progress")
def api_generate_progress(project_id: str):
    """Polling progress generování IDML."""
    gen_key = f"{project_id}_gen"
    progress = _layout_progress.get(gen_key)
    if not progress or progress.get("stage") != "generating":
        return {"status": "idle"}

    result = {
        "status": progress["status"],
        "message": progress.get("message", ""),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }
    if progress["status"] in ("done", "error"):
        result["result"] = progress.get("result")
    return result


@router.get("/api/layout/download/{project_id}")
def api_download_idml(project_id: str):
    """Stáhne vygenerovaný IDML."""
    meta = _load_project_meta(project_id)
    idml_path = meta.get("generated_idml")
    if not idml_path or not Path(idml_path).exists():
        # Zkusit export
        export_path = EXPORTS_DIR / f"{project_id}.idml"
        if export_path.exists():
            idml_path = str(export_path)
        else:
            raise HTTPException(404, "IDML ještě nebyl vygenerován")

    return FileResponse(
        idml_path,
        media_type="application/octet-stream",
        filename=f"{project_id}.idml",
    )


@router.post("/api/layout/analyze-template")
async def api_analyze_template(file: UploadFile = File(...)):
    """Upload IDML vzoru → analýza template."""
    if not file.filename or not file.filename.lower().endswith(".idml"):
        raise HTTPException(400, "Nahraj IDML soubor")

    # Uložit do temp
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".idml", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from services.layout.template_analyzer import analyze_idml
        analysis = analyze_idml(tmp_path)
        return {
            "source_file": file.filename,
            "analysis": analysis.model_dump(),
        }
    except Exception as e:
        raise HTTPException(500, f"Analýza selhala: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/api/layout/templates")
def api_list_templates():
    """Seznam dostupných style profiles."""
    from services.layout.style_profiles import get_all_profiles
    profiles = get_all_profiles()
    return {
        "profiles": [
            {
                "id": p.profile_id,
                "name": p.profile_name,
                "page_width": p.page_width,
                "page_height": p.page_height,
                "columns": p.column_count,
            }
            for p in profiles
        ]
    }


@router.get("/api/layout/patterns")
def api_list_patterns(detail: bool = False):
    """Seznam spread patterns. detail=true vrátí i sloty."""
    from services.layout.spread_patterns import get_all_patterns, is_builtin_pattern
    patterns = get_all_patterns()
    result = []
    for p in patterns:
        item = {
            "id": p.pattern_id,
            "name": p.pattern_name,
            "type": p.spread_type,
            "min_images": p.min_images,
            "max_images": p.max_images,
            "slots_count": len(p.slots),
            "description": p.description,
            "is_builtin": is_builtin_pattern(p.pattern_id),
        }
        if detail:
            item["slots"] = [s.model_dump() for s in p.slots]
            item["preferred_for"] = p.preferred_for
            item["min_text_chars"] = p.min_text_chars
        result.append(item)
    return {"patterns": result}


@router.get("/api/layout/patterns/{pattern_id}")
def api_get_pattern(pattern_id: str):
    """Detail jednoho patternu se všemi sloty."""
    from services.layout.spread_patterns import get_pattern, is_builtin_pattern
    p = get_pattern(pattern_id)
    if not p:
        raise HTTPException(404, f"Pattern neexistuje: {pattern_id}")
    return {
        "id": p.pattern_id,
        "name": p.pattern_name,
        "type": p.spread_type,
        "description": p.description,
        "min_images": p.min_images,
        "max_images": p.max_images,
        "min_text_chars": p.min_text_chars,
        "preferred_for": p.preferred_for,
        "is_builtin": is_builtin_pattern(p.pattern_id),
        "slots": [s.model_dump() for s in p.slots],
    }


@router.post("/api/layout/patterns")
def api_create_pattern(pattern: dict):
    """Vytvoří nový custom pattern."""
    from services.layout.spread_patterns import register_custom_pattern
    from models_layout import SpreadPattern
    try:
        sp = SpreadPattern(**pattern)
    except Exception as e:
        raise HTTPException(400, f"Neplatná data patternu: {e}")
    result = register_custom_pattern(sp)
    if not result["valid"]:
        raise HTTPException(400, {"detail": "Validace selhala", "errors": result["errors"]})
    return {"ok": True, "pattern_id": sp.pattern_id, **result}


@router.put("/api/layout/patterns/{pattern_id}")
def api_update_pattern(pattern_id: str, pattern: dict):
    """Aktualizuje existující custom pattern."""
    from services.layout.spread_patterns import update_custom_pattern
    from models_layout import SpreadPattern
    pattern["pattern_id"] = pattern_id
    try:
        sp = SpreadPattern(**pattern)
    except Exception as e:
        raise HTTPException(400, f"Neplatná data patternu: {e}")
    result = update_custom_pattern(sp)
    if not result["valid"]:
        raise HTTPException(400, {"detail": "Validace selhala", "errors": result["errors"]})
    return {"ok": True, "pattern_id": pattern_id, **result}


@router.delete("/api/layout/patterns/{pattern_id}")
def api_delete_pattern(pattern_id: str):
    """Smaže custom pattern (builtin nelze smazat)."""
    from services.layout.spread_patterns import delete_custom_pattern, is_builtin_pattern
    if is_builtin_pattern(pattern_id):
        raise HTTPException(400, "Nelze smazat builtin pattern")
    deleted = delete_custom_pattern(pattern_id)
    if not deleted:
        raise HTTPException(404, f"Custom pattern neexistuje: {pattern_id}")
    return {"ok": True, "deleted": pattern_id}


@router.post("/api/layout/patterns/validate")
def api_validate_pattern(pattern: dict):
    """Validace patternu bez uložení."""
    from services.layout.spread_patterns import validate_pattern
    from models_layout import SpreadPattern
    try:
        sp = SpreadPattern(**pattern)
    except Exception as e:
        raise HTTPException(400, f"Neplatná data patternu: {e}")
    return validate_pattern(sp)


# --- Session 7: Preview & Polish ---

# Thumbnail cache dir
_THUMB_DIR = LAYOUT_DIR / "_thumbnails"


@router.get("/api/layout/thumbnail/{project_id}/{filename}")
def api_thumbnail(project_id: str, filename: str, size: int = 200):
    """Vrátí thumbnail fotky (Pillow, EXIF-aware, cached)."""
    from PIL import Image, ExifTags

    images_dir = _project_dir(project_id) / "images"
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    src = images_dir / safe_name
    if not src.exists():
        raise HTTPException(404, f"Fotka neexistuje: {filename}")

    # Cache
    thumb_dir = _THUMB_DIR / project_id
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{safe_name}_{size}.jpg"

    if not thumb_path.exists() or thumb_path.stat().st_mtime < src.stat().st_mtime:
        with Image.open(src) as img:
            # EXIF orientace
            try:
                img = _apply_exif_orientation(img)
            except Exception:
                pass
            # Thumbnail — zachovává aspect ratio
            img.thumbnail((size, size), Image.LANCZOS)
            img = img.convert("RGB")
            img.save(str(thumb_path), "JPEG", quality=80)

    return FileResponse(thumb_path, media_type="image/jpeg")


def _apply_exif_orientation(img):
    """Aplikuje EXIF orientaci na Pillow Image."""
    from PIL import ExifTags
    try:
        exif = img.getexif()
        if not exif:
            return img
        orient_tag = None
        for tag_id, tag_name in ExifTags.TAGS.items():
            if tag_name == "Orientation":
                orient_tag = tag_id
                break
        if orient_tag and orient_tag in exif:
            orient = exif[orient_tag]
            rotate_map = {3: 180, 6: 270, 8: 90}
            if orient in rotate_map:
                img = img.rotate(rotate_map[orient], expand=True)
            elif orient in (2,):
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orient in (4,):
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
    except Exception:
        pass
    return img


class PlanUpdateRequest(BaseModel):
    """Update layout plánu — přesuny spreadů, přiřazení fotek."""
    spread_order: Optional[list[int]] = None        # Nové pořadí indexů
    swap_images: Optional[list[dict]] = None         # [{"from_spread": 0, "from_idx": 0, "to_spread": 1, "to_idx": 0}]
    move_image_to_spread: Optional[dict] = None      # {"image": "file.jpg", "from_spread": 0, "to_spread": 1}


@router.post("/api/layout/update-plan/{project_id}")
def api_update_plan(project_id: str, req: PlanUpdateRequest):
    """Update layout plánu — přeřadit spready, přehodit fotky."""
    meta = _load_project_meta(project_id)
    if not meta.get("plan"):
        raise HTTPException(400, "Nejdřív spusť plánování")

    from models_layout import LayoutPlan
    plan = LayoutPlan(**meta["plan"])

    # 1. Přeřazení spreadů
    if req.spread_order:
        if sorted(req.spread_order) != list(range(len(plan.spreads))):
            raise HTTPException(400, "Neplatné pořadí spreadů")
        new_spreads = [plan.spreads[i] for i in req.spread_order]
        # Přečíslovat spread_index
        for i, s in enumerate(new_spreads):
            s.spread_index = i
        plan.spreads = new_spreads

    # 2. Swap fotek mezi spready
    if req.swap_images:
        for swap in req.swap_images:
            si_from = swap.get("from_spread", 0)
            idx_from = swap.get("from_idx", 0)
            si_to = swap.get("to_spread", 0)
            idx_to = swap.get("to_idx", 0)
            s_from = plan.spreads[si_from]
            s_to = plan.spreads[si_to]
            if idx_from < len(s_from.assigned_images) and idx_to < len(s_to.assigned_images):
                s_from.assigned_images[idx_from], s_to.assigned_images[idx_to] = (
                    s_to.assigned_images[idx_to], s_from.assigned_images[idx_from]
                )

    # 3. Přesunutí fotky do jiného spreadu
    if req.move_image_to_spread:
        m = req.move_image_to_spread
        img = m.get("image", "")
        si_from = m.get("from_spread", 0)
        si_to = m.get("to_spread", 0)
        s_from = plan.spreads[si_from]
        s_to = plan.spreads[si_to]
        if img in s_from.assigned_images:
            s_from.assigned_images.remove(img)
            s_to.assigned_images.append(img)

    # Uložit
    plan_data = plan.model_dump()
    plan_path = _project_dir(project_id) / "layout_plan.json"
    plan_path.write_text(json.dumps(plan_data, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["plan"] = plan_data
    _save_project_meta(project_id, meta)

    return {"status": "updated", "plan": plan_data}


@router.get("/api/layout/validate/{project_id}")
def api_validate_project(project_id: str):
    """Validace projektu — kontrola fotek, textu, headline."""
    meta = _load_project_meta(project_id)
    warnings = []
    errors = []

    images = meta.get("images", [])
    article = meta.get("article")
    plan = meta.get("plan")

    # Fotky
    if not images:
        errors.append({"code": "no_images", "message": "Žádné fotky nebyly nahrány"})
    elif len(images) < 3:
        warnings.append({"code": "few_images", "message": f"Pouze {len(images)} fotky — doporučujeme alespoň 3"})
    elif len(images) > 30:
        warnings.append({"code": "many_images", "message": f"{len(images)} fotek — některé nebudou použity"})

    # Hero fotka
    hero_count = sum(1 for img in images if img.get("priority") == "hero")
    if hero_count == 0 and images:
        warnings.append({"code": "no_hero", "message": "Žádná fotka nemá prioritu hero — bude vybrána automaticky"})

    # Neplatné formáty (kontrola existujících souborů)
    images_dir = _project_dir(project_id) / "images"
    valid_exts = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".gif"}
    if images_dir.exists():
        for f in images_dir.iterdir():
            if f.is_file() and f.suffix.lower() not in valid_exts:
                warnings.append({"code": "invalid_format", "message": f"Neplatný formát: {f.name}"})

    # Text
    if not article:
        if meta.get("phase") in ("text_uploaded", "planned", "generated"):
            errors.append({"code": "no_text", "message": "Text článku chybí"})
    else:
        if not article.get("headline"):
            warnings.append({"code": "no_headline", "message": "Článek nemá titulek (headline)"})
        total_chars = article.get("total_chars", 0)
        if total_chars < 200:
            warnings.append({"code": "short_text", "message": f"Text je velmi krátký ({total_chars} znaků)"})
        elif total_chars > 30000:
            warnings.append({"code": "long_text", "message": f"Text je velmi dlouhý ({total_chars} znaků) — bude potřeba více stran"})

    # Poměr fotek k plánovaným stránkám
    if plan:
        plan_images_needed = 0
        for spread in plan.get("spreads", []):
            plan_images_needed += len(spread.get("assigned_images", []))
        if plan_images_needed > len(images):
            warnings.append({
                "code": "images_shortage",
                "message": f"Plán potřebuje {plan_images_needed} fotek, ale máte jen {len(images)}"
            })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


@router.get("/api/layout/plan-detail/{project_id}")
def api_plan_detail(project_id: str):
    """Detail plánu se sloty z pattern library a thumbnail URLs."""
    meta = _load_project_meta(project_id)
    if not meta.get("plan"):
        raise HTTPException(400, "Plán ještě neexistuje")

    from models_layout import LayoutPlan
    from services.layout.spread_patterns import get_pattern

    plan = LayoutPlan(**meta["plan"])
    images = meta.get("images", [])
    # Mapa: filename → image info (i s full path jako klíč)
    img_map = {}
    for img in images:
        fn = img.get("filename", "")
        if fn:
            img_map[fn] = img
        p = img.get("path", "")
        if p:
            img_map[p] = img
            img_map[Path(p).name] = img

    spreads_detail = []
    for spread in plan.spreads:
        pattern = get_pattern(spread.pattern_id)
        slots = []
        if pattern:
            for slot in pattern.slots:
                slots.append({
                    "slot_id": slot.slot_id,
                    "slot_type": slot.slot_type.value if hasattr(slot.slot_type, 'value') else str(slot.slot_type),
                    "rel_x": slot.rel_x,
                    "rel_y": slot.rel_y,
                    "rel_width": slot.rel_width,
                    "rel_height": slot.rel_height,
                    "required": slot.required,
                    "allow_bleed": slot.allow_bleed,
                })

        # Image info s thumbnail URL — normalizuj na filename
        assigned_images_detail = []
        for img_ref in spread.assigned_images:
            # assigned_images může obsahovat full path nebo jen filename
            basename = Path(img_ref).name if img_ref else img_ref
            info = img_map.get(img_ref, img_map.get(basename, {}))
            assigned_images_detail.append({
                "filename": basename,
                "thumbnail_url": f"/api/layout/thumbnail/{project_id}/{basename}",
                "orientation": info.get("orientation", "landscape"),
                "priority": info.get("priority", "supporting"),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
            })

        spreads_detail.append({
            "spread_index": spread.spread_index,
            "pattern_id": spread.pattern_id,
            "spread_type": spread.spread_type.value if hasattr(spread.spread_type, 'value') else str(spread.spread_type),
            "slots": slots,
            "assigned_images": assigned_images_detail,
            "assigned_text_sections": spread.assigned_text_sections,
            "notes": spread.notes,
        })

    return {
        "project_id": plan.project_id,
        "style_profile": plan.style_profile,
        "total_pages": plan.total_pages,
        "spreads": spreads_detail,
    }


# ===========================================================================
# Session 8: Pokročilé funkce
# ===========================================================================


# --- Feature 1: Style Transfer ---

@router.post("/api/layout/create-style-from-template")
async def api_create_style_from_template(file: UploadFile = File(...)):
    """Upload IDML → analýza → nový StyleProfile."""
    if not file.filename or not file.filename.lower().endswith(".idml"):
        raise HTTPException(400, "Nahraj IDML soubor")

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".idml", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from services.layout.template_analyzer import analyze_idml
        from services.layout.style_profiles import profile_from_analysis, register_profile

        analysis = analyze_idml(tmp_path)
        source_name = Path(file.filename).stem
        profile = profile_from_analysis(analysis, source_name=source_name)
        register_profile(profile)

        return {
            "profile_id": profile.profile_id,
            "profile_name": profile.profile_name,
            "description": profile.description,
            "page_width": profile.page_width,
            "page_height": profile.page_height,
            "headline_styles": len(profile.headline_styles),
            "body_styles": len(profile.body_styles),
            "caption_styles": len(profile.caption_styles),
        }
    except Exception as e:
        raise HTTPException(500, f"Style transfer selhal: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.delete("/api/layout/templates/{profile_id}")
def api_delete_template(profile_id: str):
    """Smaže custom style profile."""
    from services.layout.style_profiles import delete_profile
    if delete_profile(profile_id):
        return {"deleted": profile_id}
    raise HTTPException(400, f"Profil '{profile_id}' nelze smazat (hardcoded nebo neexistuje)")


# --- Feature 2: Batch generování ---

class BatchPlanRequest(BaseModel):
    num_pages: int | str = "auto"
    style_profile: Optional[str] = None
    variant_count: int = 3


class BatchGenerateRequest(BaseModel):
    skeleton_idml: Optional[str] = None
    variant_count: int = 3


@router.post("/api/layout/batch-plan/{project_id}")
def api_batch_plan(project_id: str, req: BatchPlanRequest = BatchPlanRequest()):
    """Vygeneruje N variant layout plánů."""
    meta = _load_project_meta(project_id)

    if not meta.get("images"):
        raise HTTPException(400, "Nejdřív nahraj fotky")
    if not meta.get("article"):
        raise HTTPException(400, "Nejdřív nahraj text")

    from models_layout import ImageInfo, ArticleText
    from services.layout.layout_planner import plan_layout_variants

    images = [ImageInfo(**img) for img in meta["images"]]
    article = ArticleText(**meta["article"])
    style_profile = req.style_profile or meta.get("style_profile", "ng_feature")

    variants = plan_layout_variants(
        images=images,
        text=article,
        style_profile_id=style_profile,
        num_pages=req.num_pages,
        project_id=project_id,
        count=min(req.variant_count, 5),
    )

    # Uložit varianty
    variants_data = [v.model_dump() for v in variants]
    d = _project_dir(project_id)
    (d / "variants").mkdir(exist_ok=True)

    for i, vd in enumerate(variants_data):
        vpath = d / "variants" / f"plan_v{i + 1}.json"
        vpath.write_text(json.dumps(vd, ensure_ascii=False, indent=2), encoding="utf-8")

    meta["batch_plans"] = len(variants_data)
    meta["phase"] = "batch_planned"
    _save_project_meta(project_id, meta)

    return {
        "variants": len(variants_data),
        "plans": [
            {
                "variant": i + 1,
                "total_pages": v.get("total_pages", 0),
                "spreads": len(v.get("spreads", [])),
            }
            for i, v in enumerate(variants_data)
        ],
    }


@router.post("/api/layout/batch-generate/{project_id}")
def api_batch_generate(project_id: str, req: BatchGenerateRequest = BatchGenerateRequest()):
    """Vygeneruje IDML pro všechny varianty."""
    meta = _load_project_meta(project_id)
    d = _project_dir(project_id)
    variants_dir = d / "variants"

    # Najít varianty plánů
    plan_files = sorted(variants_dir.glob("plan_v*.json")) if variants_dir.exists() else []
    if not plan_files:
        raise HTTPException(400, "Nejdřív spusť batch plánování")

    skeleton = None
    if req.skeleton_idml:
        skeleton = Path(req.skeleton_idml)
        if not skeleton.exists():
            raise HTTPException(400, f"Skeleton neexistuje: {req.skeleton_idml}")
    else:
        skeleton = _find_skeleton_idml()
        if not skeleton:
            raise HTTPException(400, "Žádný skeleton IDML k dispozici")

    batch_key = f"{project_id}_batch_gen"
    if batch_key in _layout_progress and _layout_progress[batch_key].get("status") == "running":
        raise HTTPException(409, "Batch generování již běží")

    _layout_progress[batch_key] = {
        "status": "running",
        "stage": "batch_generating",
        "started_at": time.time(),
        "message": f"Generuji {len(plan_files)} variant...",
        "completed": 0,
        "total": len(plan_files),
        "result": None,
    }

    skeleton_str = str(skeleton)

    def run_batch():
        progress = _layout_progress[batch_key]
        results = []
        try:
            from models_layout import LayoutPlan, ArticleText
            from services.layout.idml_builder import build_from_plan

            article = ArticleText(**meta["article"])

            text_sections = {}
            if article.headline:
                text_sections["headline"] = article.headline
            if article.deck:
                text_sections["deck"] = article.deck
            if article.byline:
                text_sections["byline"] = article.byline
            for i, para in enumerate(article.body_paragraphs):
                text_sections[f"body_{i}"] = para
            for i, cap in enumerate(article.captions):
                text_sections[f"caption_{i}"] = cap
            for i, pq in enumerate(article.pull_quotes):
                text_sections[f"pullquote_{i}"] = pq

            images_dir = d / "images"

            for vi, pf in enumerate(plan_files, 1):
                progress["message"] = f"Generuji variantu {vi}/{len(plan_files)}..."
                progress["completed"] = vi - 1

                plan_data = json.loads(pf.read_text(encoding="utf-8"))
                plan = LayoutPlan(**plan_data)

                image_paths = {}
                for spread in plan.spreads:
                    if spread.assigned_images:
                        spread_imgs = []
                        for img_fn in spread.assigned_images:
                            img_path = images_dir / img_fn
                            if img_path.exists():
                                spread_imgs.append(str(img_path))
                        if spread_imgs:
                            image_paths[str(spread.spread_index)] = spread_imgs

                output_path = variants_dir / f"variant_{vi}.idml"
                result_path = build_from_plan(
                    layout_plan=plan,
                    skeleton_idml=skeleton_str,
                    output_path=str(output_path),
                    text_sections=text_sections,
                    image_paths=image_paths,
                )

                results.append({
                    "variant": vi,
                    "path": str(result_path),
                    "size_kb": round(result_path.stat().st_size / 1024, 1),
                })

            progress["status"] = "done"
            progress["completed"] = len(plan_files)
            progress["message"] = f"Vygenerováno {len(results)} variant"
            progress["result"] = {"variants": results}

        except Exception as e:
            logger.error("Batch generation error: %s", e, exc_info=True)
            progress["status"] = "error"
            progress["message"] = str(e)
            progress["result"] = {"error": str(e), "completed_variants": results}

    thread = threading.Thread(target=run_batch, daemon=True)
    thread.start()
    return {"status": "started", "message": f"Batch generování spuštěno ({len(plan_files)} variant)"}


@router.get("/api/layout/batch-generate/{project_id}/progress")
def api_batch_generate_progress(project_id: str):
    """Polling progress batch generování."""
    batch_key = f"{project_id}_batch_gen"
    progress = _layout_progress.get(batch_key)
    if not progress or progress.get("stage") != "batch_generating":
        return {"status": "idle"}

    result = {
        "status": progress["status"],
        "message": progress.get("message", ""),
        "completed": progress.get("completed", 0),
        "total": progress.get("total", 0),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }
    if progress["status"] in ("done", "error"):
        result["result"] = progress.get("result")
    return result


@router.get("/api/layout/batch-download/{project_id}/{variant}")
def api_batch_download(project_id: str, variant: int):
    """Stáhne konkrétní variantu IDML."""
    d = _project_dir(project_id)
    idml_path = d / "variants" / f"variant_{variant}.idml"
    if not idml_path.exists():
        raise HTTPException(404, f"Varianta {variant} neexistuje")
    return FileResponse(
        str(idml_path),
        media_type="application/octet-stream",
        filename=f"{project_id}_v{variant}.idml",
    )


# --- Feature 3: PDF Preview ---

@router.post("/api/layout/preview-pdf/{project_id}")
def api_generate_preview_pdf(project_id: str):
    """Vygeneruje PDF náhled layoutu."""
    meta = _load_project_meta(project_id)
    if not meta.get("plan"):
        raise HTTPException(400, "Nejdřív spusť plánování")

    try:
        from services.layout.pdf_preview import generate_preview_pdf

        # Načíst plan detail
        plan_detail_data = api_plan_detail(project_id)
        d = _project_dir(project_id)

        pdf_path = generate_preview_pdf(
            plan_detail=plan_detail_data,
            project_dir=str(d),
            style_profile_id=meta.get("style_profile", "ng_feature"),
        )

        return {
            "status": "done",
            "pdf_path": str(pdf_path),
            "size_kb": round(pdf_path.stat().st_size / 1024, 1),
        }
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.error("PDF preview error: %s", e, exc_info=True)
        raise HTTPException(500, f"PDF generování selhalo: {e}")


@router.get("/api/layout/preview-pdf/{project_id}/download")
def api_download_preview_pdf(project_id: str):
    """Stáhne PDF náhled."""
    d = _project_dir(project_id)
    pdf_path = d / "preview.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "PDF preview ještě nebyl vygenerován")
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"{project_id}_preview.pdf",
    )


# --- Feature 4: Caption Matching ---

@router.post("/api/layout/match-captions/{project_id}")
def api_match_captions(project_id: str):
    """AI přiřazení popisků k fotkám."""
    meta = _load_project_meta(project_id)
    if not meta.get("images"):
        raise HTTPException(400, "Nejdřív nahraj fotky")
    if not meta.get("article"):
        raise HTTPException(400, "Nejdřív nahraj text")

    captions = meta["article"].get("captions", [])
    if not captions:
        raise HTTPException(400, "Článek neobsahuje žádné popisky (captions)")

    # Spustit na pozadí
    match_key = f"{project_id}_caption_match"
    if match_key in _layout_progress and _layout_progress[match_key].get("status") == "running":
        raise HTTPException(409, "Caption matching již běží")

    _layout_progress[match_key] = {
        "status": "running",
        "stage": "caption_matching",
        "started_at": time.time(),
        "message": "Přiřazuji popisky k fotkám...",
        "result": None,
    }

    def run_matching():
        progress = _layout_progress[match_key]
        try:
            from services.layout.caption_matcher import match_captions_to_images

            images_dir = _project_dir(project_id) / "images"
            image_paths = sorted(
                [p for p in images_dir.glob("*")
                 if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif")],
                key=lambda p: p.stat().st_size,
                reverse=True,
            )

            api_key = get_api_key()
            progress["message"] = f"Analyzuji {len(image_paths)} fotek vs {len(captions)} popisků..."

            matches = match_captions_to_images(
                image_paths=image_paths,
                captions=captions,
                api_key=api_key,
            )

            # Uložit do meta
            meta["caption_matches"] = matches
            _save_project_meta(project_id, meta)

            progress["status"] = "done"
            progress["message"] = f"Přiřazeno {sum(1 for m in matches if m['caption'])} popisků"
            progress["result"] = {"matches": matches}

        except Exception as e:
            logger.error("Caption matching error: %s", e, exc_info=True)
            progress["status"] = "error"
            progress["message"] = str(e)
            progress["result"] = {"error": str(e)}

    thread = threading.Thread(target=run_matching, daemon=True)
    thread.start()
    return {"status": "started", "message": "Caption matching spuštěn"}


@router.get("/api/layout/match-captions/{project_id}/progress")
def api_match_captions_progress(project_id: str):
    """Polling progress caption matchingu."""
    match_key = f"{project_id}_caption_match"
    progress = _layout_progress.get(match_key)
    if not progress or progress.get("stage") != "caption_matching":
        # Zkusit načíst uložené výsledky
        try:
            meta = _load_project_meta(project_id)
            if meta.get("caption_matches"):
                return {
                    "status": "done",
                    "message": "Popisky přiřazeny",
                    "result": {"matches": meta["caption_matches"]},
                }
        except Exception:
            pass
        return {"status": "idle"}

    result = {
        "status": progress["status"],
        "message": progress.get("message", ""),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }
    if progress["status"] in ("done", "error"):
        result["result"] = progress.get("result")
    return result


# === Session 10: Multi-Article endpointy ===

class ImageAllocationRequest(BaseModel):
    """Přiřazení fotek k článkům."""
    allocation: dict[str, list[str]]  # {article_id: [filename, ...]}


class MultiPlanRequest(BaseModel):
    num_pages: int | str = "auto"
    use_ai: bool = False


@router.post("/api/layout/multi/upload-articles/{project_id}")
async def api_multi_upload_articles(
    project_id: str,
    text: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
):
    """Upload N článků — buď jako jeden text s delimitery, nebo N souborů."""
    meta = _load_project_meta(project_id)
    d = _project_dir(project_id)

    from services.layout.text_parser import (
        parse_multi_article_text, parse_multi_article_files,
    )

    if files and any(f.filename for f in files):
        file_texts = []
        articles_dir = d / "articles"
        articles_dir.mkdir(exist_ok=True)
        for f in files:
            if not f.filename:
                continue
            content = await f.read()
            raw = content.decode("utf-8", errors="replace")
            (articles_dir / f.filename).write_text(raw, encoding="utf-8")
            file_texts.append((f.filename, raw))
        multi = parse_multi_article_files(file_texts)
    elif text:
        text_path = d / "multi_articles.txt"
        text_path.write_text(text, encoding="utf-8")
        multi = parse_multi_article_text(text)
    else:
        raise HTTPException(400, "Zadej text nebo nahraj soubory")

    if not multi.articles:
        raise HTTPException(400, "Žádný článek nebyl rozpoznán")

    meta["multi_article"] = True
    meta["articles"] = [a.model_dump() for a in multi.articles]
    meta["image_allocation"] = {}
    meta["phase"] = "articles_uploaded"
    _save_project_meta(project_id, meta)

    return {
        "article_count": len(multi.articles),
        "articles": [
            {
                "article_id": a.article_id,
                "headline": a.headline[:100] if a.headline else "",
                "body_paragraphs": len(a.body_paragraphs),
                "total_chars": a.total_chars,
                "style_profile_id": a.style_profile_id,
            }
            for a in multi.articles
        ],
    }


@router.post("/api/layout/multi/allocate-images/{project_id}")
def api_multi_allocate_images(project_id: str, req: ImageAllocationRequest):
    """Přiřadí fotky k článkům. Nepřiřazené se auto-distribuují."""
    meta = _load_project_meta(project_id)

    if not meta.get("multi_article"):
        raise HTTPException(400, "Projekt není multi-article")
    if not meta.get("images"):
        raise HTTPException(400, "Nejdřív nahraj fotky")

    all_filenames = {img["filename"] for img in meta["images"]}
    article_ids = {a["article_id"] for a in meta.get("articles", [])}

    assigned = set()
    for article_id, filenames in req.allocation.items():
        if article_id not in article_ids:
            raise HTTPException(400, f"Neznámý article_id: {article_id}")
        for fn in filenames:
            if fn not in all_filenames:
                raise HTTPException(400, f"Neznámá fotka: {fn}")
            if fn in assigned:
                raise HTTPException(400, f"Fotka {fn} je přiřazena vícekrát")
            assigned.add(fn)

    unassigned = [fn for fn in all_filenames if fn not in assigned]
    if unassigned:
        articles_list = list(article_ids)
        for i, fn in enumerate(sorted(unassigned)):
            target = articles_list[i % len(articles_list)]
            if target not in req.allocation:
                req.allocation[target] = []
            req.allocation[target].append(fn)

    meta["image_allocation"] = req.allocation
    meta["phase"] = "images_allocated"
    _save_project_meta(project_id, meta)

    return {
        "allocation": req.allocation,
        "auto_assigned": len(unassigned),
        "total_images": len(all_filenames),
    }


@router.post("/api/layout/multi/plan/{project_id}")
def api_multi_plan(project_id: str, req: MultiPlanRequest = MultiPlanRequest()):
    """Spustí multi-article plánování na pozadí."""
    meta = _load_project_meta(project_id)

    if not meta.get("multi_article"):
        raise HTTPException(400, "Projekt není multi-article")
    if not meta.get("articles"):
        raise HTTPException(400, "Nejdřív nahraj články")
    if not meta.get("images"):
        raise HTTPException(400, "Nejdřív nahraj fotky")

    plan_key = f"{project_id}_multi_plan"
    if plan_key in _layout_progress and _layout_progress[plan_key].get("status") == "running":
        raise HTTPException(409, "Plánování již běží")

    api_key = get_api_key() if req.use_ai else None

    _layout_progress[plan_key] = {
        "status": "running",
        "stage": "multi_planning",
        "started_at": time.time(),
        "message": "Plánuji multi-article layout...",
        "result": None,
    }

    def run_multi_plan():
        progress = _layout_progress[plan_key]
        try:
            from models_layout import ArticleItem, ImageInfo, MultiArticleText
            from services.layout.layout_planner import plan_multi_article_layout

            articles = [ArticleItem(**a) for a in meta["articles"]]
            multi_text = MultiArticleText(articles=articles)

            all_images = {img["filename"]: ImageInfo(**img) for img in meta["images"]}
            allocation = meta.get("image_allocation", {})

            image_alloc: dict[str, list] = {}
            for article_id, filenames in allocation.items():
                image_alloc[article_id] = [
                    all_images[fn] for fn in filenames if fn in all_images
                ]

            if not allocation:
                all_img_list = list(all_images.values())
                n = len(articles)
                for i, article in enumerate(articles):
                    chunk = len(all_img_list) // n
                    start = i * chunk
                    end = start + chunk if i < n - 1 else len(all_img_list)
                    image_alloc[article.article_id] = all_img_list[start:end]

            progress["message"] = f"Plánuji {len(articles)} článků..."

            multi_plan = plan_multi_article_layout(
                multi_text=multi_text,
                image_allocation=image_alloc,
                project_id=project_id,
                use_ai=req.use_ai,
                api_key=api_key,
            )

            meta["multi_plan"] = multi_plan.model_dump()
            meta["phase"] = "multi_planned"
            _save_project_meta(project_id, meta)

            progress["status"] = "done"
            progress["message"] = f"Plán hotov: {multi_plan.total_pages} stránek, {len(multi_plan.article_plans)} článků"
            progress["result"] = {
                "total_pages": multi_plan.total_pages,
                "article_count": len(multi_plan.article_plans),
                "boundaries": multi_plan.article_boundaries,
            }

        except Exception as e:
            logger.error(f"Multi-plan error: {e}", exc_info=True)
            progress["status"] = "error"
            progress["message"] = str(e)
            progress["result"] = {"error": str(e)}

    thread = threading.Thread(target=run_multi_plan, daemon=True)
    thread.start()

    return {"status": "started", "message": "Multi-article plánování spuštěno"}


@router.get("/api/layout/multi/plan/{project_id}/progress")
def api_multi_plan_progress(project_id: str):
    """Polling progress multi-article plánování."""
    plan_key = f"{project_id}_multi_plan"
    progress = _layout_progress.get(plan_key)
    if not progress or progress.get("stage") != "multi_planning":
        try:
            meta = _load_project_meta(project_id)
            if meta.get("multi_plan"):
                mp = meta["multi_plan"]
                return {
                    "status": "done",
                    "message": f"Plán hotov: {mp['total_pages']} stránek",
                    "result": {
                        "total_pages": mp["total_pages"],
                        "article_count": len(mp["article_plans"]),
                        "boundaries": mp.get("article_boundaries", []),
                    },
                }
        except Exception:
            pass
        return {"status": "idle"}

    resp = {
        "status": progress["status"],
        "message": progress.get("message", ""),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }
    if progress["status"] in ("done", "error"):
        resp["result"] = progress.get("result")
    return resp


@router.post("/api/layout/multi/generate/{project_id}")
def api_multi_generate(project_id: str, req: GenerateRequest = GenerateRequest()):
    """Vygeneruje jeden IDML z multi-article plánu."""
    meta = _load_project_meta(project_id)

    if not meta.get("multi_plan"):
        raise HTTPException(400, "Nejdřív spusť multi-article plánování")

    skeleton = None
    if req.skeleton_idml:
        skeleton = Path(req.skeleton_idml)
        if not skeleton.exists():
            raise HTTPException(400, f"Skeleton IDML neexistuje: {req.skeleton_idml}")
    else:
        skeleton = _find_skeleton_idml()
        if not skeleton:
            raise HTTPException(400, "Žádný skeleton IDML k dispozici")

    gen_key = f"{project_id}_multi_gen"
    if gen_key in _layout_progress and _layout_progress[gen_key].get("status") == "running":
        raise HTTPException(409, "Generování již běží")

    _layout_progress[gen_key] = {
        "status": "running",
        "stage": "multi_generating",
        "started_at": time.time(),
        "message": "Generuji multi-article IDML...",
        "result": None,
    }

    skeleton_str = str(skeleton)

    def run_multi_generate():
        progress = _layout_progress[gen_key]
        try:
            from models_layout import MultiArticlePlan
            from services.layout.idml_builder import build_from_multi_article_plans

            multi_plan = MultiArticlePlan(**meta["multi_plan"])
            articles_data = meta.get("articles", [])

            progress["message"] = "Sestavuji text sekce per article..."

            article_text_sections: dict[str, dict[str, str]] = {}
            for plan_data, article_data in zip(multi_plan.article_plans, articles_data):
                sections: dict[str, str] = {}
                if article_data.get("headline"):
                    sections["headline"] = article_data["headline"]
                if article_data.get("deck"):
                    sections["deck"] = article_data["deck"]
                if article_data.get("byline"):
                    sections["byline"] = article_data["byline"]
                for i, para in enumerate(article_data.get("body_paragraphs", [])):
                    sections[f"body_{i}"] = para
                for i, cap in enumerate(article_data.get("captions", [])):
                    sections[f"caption_{i}"] = cap
                for i, pq in enumerate(article_data.get("pull_quotes", [])):
                    sections[f"pullquote_{i}"] = pq
                article_text_sections[plan_data.project_id] = sections

            article_image_paths: dict[str, dict[str, list[str]]] = {}
            images_dir = _project_dir(project_id) / "images"

            for plan_data in multi_plan.article_plans:
                img_map: dict[str, list[str]] = {}
                for spread in plan_data.spreads:
                    if spread.assigned_images:
                        spread_imgs = []
                        for img_fn in spread.assigned_images:
                            img_path = images_dir / img_fn
                            if img_path.exists():
                                spread_imgs.append(str(img_path))
                            else:
                                for info in spread.assigned_image_infos or []:
                                    p = Path(info.get("path", "")) if isinstance(info, dict) else Path(info.path)
                                    if p.exists():
                                        spread_imgs.append(str(p))
                                        break
                        if spread_imgs:
                            img_map[str(spread.spread_index)] = spread_imgs
                article_image_paths[plan_data.project_id] = img_map

            total_spreads = sum(len(p.spreads) for p in multi_plan.article_plans)
            progress["message"] = f"Generuji IDML ({total_spreads} spreadů, {len(multi_plan.article_plans)} článků)..."

            output_path = _project_dir(project_id) / f"{project_id}_multi.idml"
            result_path = build_from_multi_article_plans(
                multi_plan=multi_plan,
                skeleton_idml=skeleton_str,
                output_path=str(output_path),
                article_text_sections=article_text_sections,
                article_image_paths=article_image_paths,
            )

            export_path = EXPORTS_DIR / f"{project_id}_multi.idml"
            shutil.copy2(result_path, export_path)

            meta["generated_idml"] = str(result_path)
            meta["phase"] = "multi_generated"
            _save_project_meta(project_id, meta)

            progress["status"] = "done"
            progress["message"] = f"Multi-article IDML vygenerován: {result_path.name}"
            progress["result"] = {
                "idml_path": str(result_path),
                "export_path": str(export_path),
                "size_kb": round(result_path.stat().st_size / 1024, 1),
                "total_pages": multi_plan.total_pages,
                "article_count": len(multi_plan.article_plans),
            }

        except Exception as e:
            logger.error(f"Multi-IDML generation error: {e}", exc_info=True)
            progress["status"] = "error"
            progress["message"] = str(e)
            progress["result"] = {"error": str(e)}

    thread = threading.Thread(target=run_multi_generate, daemon=True)
    thread.start()

    return {"status": "started", "message": "Multi-article IDML generování spuštěno"}


@router.get("/api/layout/multi/generate/{project_id}/progress")
def api_multi_generate_progress(project_id: str):
    """Polling progress multi-article IDML generování."""
    gen_key = f"{project_id}_multi_gen"
    progress = _layout_progress.get(gen_key)
    if not progress or progress.get("stage") != "multi_generating":
        return {"status": "idle"}

    resp = {
        "status": progress["status"],
        "message": progress.get("message", ""),
        "elapsed_s": round(time.time() - progress.get("started_at", time.time()), 1),
    }
    if progress["status"] in ("done", "error"):
        resp["result"] = progress.get("result")
    return resp
