"""FastAPI application: REST API + static SPA."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.api import router as api_router

app = FastAPI(title="Video Template Studio", version="0.1.0")
app.include_router(api_router)

try:
    from fastapi.responses import FileResponse

    @app.get("/health")
    async def health():
        return {"ok": True, "service": "videotemplate"}
except Exception:  # pragma: no cover
    pass

from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware

SPA_DIR = Path(__file__).resolve().parent.parent / "web"


class NoCacheSpa(BaseHTTPMiddleware):
    """Static pages/assets must never be cached, or the SPA is stale after deploys."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method == "GET" and request.url.path in ("/", "/index.html", "/app.js", "/app.css"):
            response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(NoCacheSpa)

if SPA_DIR.exists() and any(SPA_DIR.glob("*")):
    app.mount("/", StaticFiles(directory=str(SPA_DIR), html=True), name="web")