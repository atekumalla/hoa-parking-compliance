"""
FastAPI entrypoint.

Local dev: run this on :8000, run the Vite dev server separately on :5173
(it proxies /api to here — see frontend/vite.config.ts). No CORS needed
since the browser only ever talks to one origin.

Prod: this same process also serves the built frontend (frontend/dist) as
static files, so the whole app is one Render service, one origin, no CORS.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import config
from .state import state
from .routers import admin, auth, entries, scoreboard, history, storage

app = FastAPI(title="HOA Parking Compliance API")

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(scoreboard.router)
app.include_router(history.router)
app.include_router(storage.router)


@app.on_event("startup")
def _startup():
    # One load for the whole process, shared by every user — this is the
    # structural fix for the old per-browser-session full reload.
    state.init_managers()
    state.load(force=True)


@app.get("/api/health")
def health():
    return {"ok": True, "data_last_loaded": state.last_loaded.isoformat() if state.last_loaded else None}


_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")
    _FRONTEND_DIST_RESOLVED = _FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        """Serve the built React app for any non-API route (client-side routing).

        Resolves and containment-checks the path first — without this, a
        request like /%2e%2e/%2e%2e/service-account-key.json walks straight
        out of frontend/dist and serves arbitrary files on the server,
        secrets included.
        """
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(_FRONTEND_DIST_RESOLVED)
        ):
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
