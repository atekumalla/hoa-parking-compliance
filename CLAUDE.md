# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Active code vs. legacy

The live app is **`backend/` (FastAPI) + `frontend/` (React + Vite + TypeScript)**. The root-level Python files (`app.py`, `sheets_manager.py`, `drive_manager.py`, `compliance_engine.py`, `oauth_manager.py`, `vehicle_recognition.py`, `start.sh`, root `requirements.txt`, `camera_component/`, `token_storage_component/`, `.streamlit/`) are the original Streamlit app, kept only as historical reference. Don't edit them unless asked; the maintained copies of the services live in `backend/app/services/`.

## Commands

Backend (from repo root, using `.venv`):
```bash
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend && npm install
npm run dev        # Vite on :5173, proxies /api/* to 127.0.0.1:8000
npm run build      # tsc --noEmit && vite build -> frontend/dist
npx tsc --noEmit   # type-check only
```

If `frontend/dist` exists, the backend serves it itself at `:8000` (production mode, single process).

There is no test suite and no linter configured. `npm run build` (the TypeScript strict type-check) is the only automated check.

## Architecture

- **Google Sheets is the database.** Entries live in one tab per month, named `%b-%Y` (e.g. `Oct-2026`), which is created on demand with the header row `SheetsManager.COLUMNS`. Photos go to Google Drive in per-month subfolders under `GOOGLE_DRIVE_FOLDER_ID`.
- **Shared in-process cache (`backend/app/state.py`).** A single `AppState` holds `historical` (all rows) and `rolling` (last 30 days) as pandas DataFrames, loaded once at startup and shared by all users. Routes get it through the `get_state` dependency, which refreshes it once `DATA_CACHE_TTL_SECONDS` has passed. Periodic refreshes are incremental: only the current and previous month's tabs are refetched. Writes update the cache directly via `append_local`/`remove_local` rather than refetching. There are two locks: `_lock` covers in-memory swaps only, and `_fetch_lock` serializes network fetches. Never hold `_lock` during a network call.
- **Compliance rules (`services/compliance_engine.py`).** The core rule is a maximum of 9 *unique calendar days* in a rolling 30-day window. A warning carries forward permanently, so a later violation in any period means the vehicle is eligible for towing. License plates are normalized to uppercase. The rules are also described for users in `frontend/src/pages/RulesPage.tsx` and the README; keep these in sync when rules change.
- **Timezone.** Timestamps are written and compared in `America/Los_Angeles` (see `sheets_manager.append_entry` and `routers/entries.py`).
- **Auth (two independent cookie-based mechanisms, both with in-memory server-side stores that are lost on restart):**
  - `admin_auth.py`: a single shared `ADMIN_PASSCODE` gates destructive routes via `Depends(admin_auth.require_admin)`. The `admin_sid` session lasts 7 days and slides forward on each use. A separate `photo_trust` cookie gates only `/api/analyze-photo` (the paid OpenAI call) through `require_photo_trust`. If `ADMIN_PASSCODE` is unset, gated routes return 503 instead of being left open. Reads are never gated.
  - `oauth.py`: optional per-user Google OAuth (`drive.file` scope) so photo uploads count against the user's own Drive quota. Service accounts have no Drive quota, so uploads without OAuth generally fail unless a Shared Drive is used. Tokens stay server-side; the browser holds only a signed `sid`.
- **Drive thread-safety.** `httplib2` isn't thread-safe, so every Drive API call goes through `_LockedHttp` and a global `_API_LOCK` in `drive_manager.py`. New Drive service objects must be built with `_build_locked_service`.
- **AI photo analysis (`services/vehicle_recognition.py`).** Uses OpenAI (`OPENAI_VISION_MODEL`, default `gpt-6-luna`, a reasoning model). It must use `max_completion_tokens`, not `max_tokens`.
- **Frontend.** `src/api.ts` is the only place that calls the backend. All paths are relative `/api/...` with `credentials: 'include'`, and FastAPI's `{"detail": ...}` error bodies are unwrapped into `ApiError.detail`, which can be a structured object (e.g. duplicate-entry info) rather than a string. Pages live in `src/pages/` and routes in `src/App.tsx`.
- **SPA fallback (`main.py`).** Non-API paths serve `frontend/dist/index.html`. The path containment check there prevents path traversal out of `dist`, which would otherwise expose `service-account-key.json`. Keep that check.

## Config & deployment

- `backend/app/config.py` loads the **repo-root** `.env` and resolves a relative `GOOGLE_APPLICATION_CREDENTIALS` against the repo root. Production is detected by the `RENDER` env var or `ENV=production`, and the app refuses to start in prod without `SESSION_SECRET_KEY`.
- The app deploys to Render as one native Python web service (no Docker, no `render.yaml`; build command and env vars are set in the dashboard). `start_backend.sh` writes `GOOGLE_CREDENTIALS_JSON` to `/tmp/service-account-key.json` and runs uvicorn on `$PORT`. See `DEPLOY_RENDER.md`.
- Outbound TLS from Python verifies against `certifi`, not the system store, which is why `certifi` is pinned in `backend/requirements.txt`.
