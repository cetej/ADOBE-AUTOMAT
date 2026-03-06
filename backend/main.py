"""NGM Localizer — FastAPI backend pro lokalizaci map a casopisu."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import projects, illustrator, extract, translate, export, writeback

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = FastAPI(
    title="NGM Localizer",
    description="Webova aplikace pro lokalizaci map a casopisu National Geographic CZ",
    version="0.1.0",
)

# CORS pro Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "NGM Localizer", "version": "0.1.0"}

# Routery
app.include_router(projects.router)
app.include_router(illustrator.router)
app.include_router(extract.router)
app.include_router(translate.router)
app.include_router(export.router)
app.include_router(writeback.router)

# Serve frontend static files (production build) — MUSI byt posledni (catch-all)
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
