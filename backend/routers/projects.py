"""CRUD endpointy pro projekty."""

from fastapi import APIRouter, HTTPException

from models import Project, ProjectCreate
from services.project_store import (
    list_projects,
    get_project,
    create_project,
    delete_project,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[Project])
async def api_list_projects():
    return list_projects()


@router.post("", response_model=Project)
async def api_create_project(req: ProjectCreate):
    return create_project(req)


@router.get("/{project_id}", response_model=Project)
async def api_get_project(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project '{project_id}' not found")
    return project


@router.delete("/{project_id}")
async def api_delete_project(project_id: str):
    if not delete_project(project_id):
        raise HTTPException(404, f"Project '{project_id}' not found")
    return {"deleted": project_id}
