"""CRUD operace pro projekty ulozene jako JSON soubory."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import re
from datetime import datetime
from pathlib import Path

from config import PROJECTS_DIR
from models import Project, ProjectCreate, ProjectPhase, ProjectType
from services.text_pipeline.element_merger import strip_pipeline_markers


def _slugify(text: str) -> str:
    """Prevede text na bezpecny identifikator."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:64]


def _safe_id(project_id: str) -> str:
    """Sanitizuje project_id — povoli jen alfanumericke znaky, pomlcky a podtrzitka."""
    safe = re.sub(r"[^\w-]", "", project_id)
    if not safe:
        raise ValueError(f"Neplatne project_id: {project_id!r}")
    return safe


def _project_path(project_id: str) -> Path:
    path = PROJECTS_DIR / f"{_safe_id(project_id)}.json"
    # Guard: vysledna cesta musi byt uvnitr PROJECTS_DIR
    if not path.resolve().is_relative_to(PROJECTS_DIR.resolve()):
        raise ValueError(f"Path traversal attempt: {project_id!r}")
    return path


def list_projects() -> list[Project]:
    """Vrati seznam vsech projektu."""
    projects = []
    for f in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            projects.append(Project(**data))
        except Exception:
            continue
    return projects


def get_project(project_id: str) -> Project | None:
    """Nacte projekt podle ID."""
    path = _project_path(project_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Project(**data)


def create_project(req: ProjectCreate) -> Project:
    """Vytvori novy projekt."""
    project_id = _slugify(req.name)
    # Zajistit unikatnost
    base_id = project_id
    counter = 1
    while _project_path(project_id).exists():
        project_id = f"{base_id}-{counter}"
        counter += 1

    project = Project(
        id=project_id,
        name=req.name,
        type=req.type,
        source_file=req.source_file,
    )
    save_project(project)
    return project


def save_project(project: Project) -> None:
    """Ulozi projekt na disk. Stripne pipeline markery z elem.czech."""
    project.updated_at = datetime.now().isoformat()
    # Defence-in-depth: nikdy neuložit pipeline markery na disk
    for elem in project.elements:
        if elem.czech and '<!--[' in elem.czech:
            elem.czech = strip_pipeline_markers(elem.czech)
    path = _project_path(project.id)
    path.write_text(
        project.model_dump_json(indent=2),
        encoding="utf-8",
    )


def delete_project(project_id: str) -> bool:
    """Smaze projekt."""
    path = _project_path(project_id)
    if path.exists():
        path.unlink()
        return True
    return False
