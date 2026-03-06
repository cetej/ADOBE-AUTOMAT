"""Endpointy pro komunikaci s Illustratorem."""

from fastapi import APIRouter

from services.illustrator_bridge import check_connection, get_documents

router = APIRouter(prefix="/api/illustrator", tags=["illustrator"])


@router.get("/status")
async def api_status():
    """Zkontroluje pripojeni k proxy + Illustratoru."""
    return await check_connection()


@router.get("/documents")
async def api_documents():
    """Seznam otevrenych dokumentu v Illustratoru."""
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: get_documents(timeout=10))
        return result or {"documents": []}
    except Exception as e:
        return {"error": str(e), "documents": []}
