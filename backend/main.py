"""NGM Localizer — FastAPI backend pro lokalizaci map a casopisu."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import projects, illustrator, extract, translate, export, writeback, pipeline, layout, corrections, reports

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


@app.get("/api/traces/summary")
async def traces_summary(since: str = None, until: str = None, module: str = None):
    """Statistiky API volání — tokeny, náklady, latence."""
    from core.traces import get_trace_store
    store = get_trace_store()
    s = store.summary(since=since, until=until, module=module)
    return {
        "total_calls": s.total_calls,
        "total_input_tokens": s.total_input_tokens,
        "total_output_tokens": s.total_output_tokens,
        "total_cache_read_tokens": s.total_cache_read_tokens,
        "total_cost_usd": round(s.total_cost_usd, 4),
        "total_latency_seconds": round(s.total_latency_seconds, 1),
        "success_count": s.success_count,
        "error_count": s.error_count,
        "by_model": s.by_model,
        "by_module": s.by_module,
    }


@app.get("/api/traces/recent")
async def traces_recent(limit: int = 20):
    """Posledních N API volání."""
    from core.traces import get_trace_store
    store = get_trace_store()
    traces = store.recent(limit=limit)
    return [
        {
            "trace_id": t.trace_id,
            "timestamp": t.timestamp,
            "module": t.module,
            "model": t.model,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "cost_usd": round(t.cost_usd, 4),
            "latency_seconds": round(t.latency_seconds, 1),
            "success": t.success,
            "error": t.error,
        }
        for t in traces
    ]

# Routery
app.include_router(projects.router)
app.include_router(illustrator.router)
app.include_router(extract.router)
app.include_router(translate.router)
app.include_router(export.router)
app.include_router(writeback.router)
app.include_router(pipeline.router)
app.include_router(layout.router)
app.include_router(corrections.router)
app.include_router(reports.router)

# Serve frontend static files (production build) — MUSI byt posledni (catch-all)
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
