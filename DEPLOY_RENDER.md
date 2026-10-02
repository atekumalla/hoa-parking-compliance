# Deploying to Render

This guide walks you through deploying the HOA Guest Parking Compliance Tracker to [Render](https://render.com).

The app is a FastAPI backend (`backend/`) that also serves a built React frontend
(`frontend/dist`) as static files, so it deploys as a **single** Render web service —
one build step compiles the frontend, one process serves both the API and the UI.

---

## Prerequisites

- A [Render account](https://dashboard.render.com/register) (free tier works)
- Your code pushed to a GitHub repository
- Your Google service account JSON key contents (you'll paste it as an env var)

---

## Step 1: Prepare Your Repository

Make sure the following are committed and pushed to GitHub:

- `backend/` (FastAPI app and `requirements.txt`)
- `frontend/` (React app, `package.json`, etc.)
- `start_backend.sh`

> ⚠️ **Do NOT commit** `service-account-key.json` or `.env` to your repo. Add them to `.gitignore`.

---

## Step 2: Create a `render.yaml` (Optional — Blueprint)

You can either configure via the Render dashboard (Step 3) or add this file to your repo for one-click deploy:

```yaml
services:
  - type: web
    name: hoa-parking-compliance
    runtime: python
    buildCommand: pip install -r backend/requirements.txt && cd frontend && npm install && npm run build
    startCommand: sh start_backend.sh
    envVars:
      - key: GOOGLE_SHEET_ID
        sync: false
      - key: GOOGLE_DRIVE_FOLDER_ID
        sync: false
      - key: GOOGLE_CREDENTIALS_JSON
        sync: false
      - key: SESSION_SECRET_KEY
        sync: false
      - key: ADMIN_PASSCODE
        sync: false
      - key: SCOREBOARD_TOP_N
        value: "20"
      - key: PYTHON_VERSION
        value: "3.11.6"
      - key: NODE_VERSION
        value: "20"
```

---

## Step 3: The Start Script

`start_backend.sh` already exists at the repo root and does the following:

```bash
#!/usr/bin/env bash
set -e

# Write the service account JSON from the environment variable to a file
printenv GOOGLE_CREDENTIALS_JSON > /tmp/service-account-key.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/service-account-key.json

# Reduce glibc memory arena fragmentation — matters on Render's small containers.
export MALLOC_ARENA_MAX=2
export PYTHONMALLOC=malloc

cd "$(dirname "$0")/backend"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

No edits needed — just make sure it's executable and committed:

```bash
chmod +x start_backend.sh
git add start_backend.sh
```

---

## Step 4: Create the Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `hoa-parking-compliance` (or your choice) |
| **Region** | Pick the closest to you |
| **Runtime** | `Python` |
| **Build Command** | `pip install -r backend/requirements.txt && cd frontend && npm install && npm run build` |
| **Start Command** | `sh start_backend.sh` |
| **Instance Type** | Free (or Starter for better performance) |

The build command installs Python dependencies from `backend/requirements.txt`, then
installs and builds the frontend into `frontend/dist`, which `backend/app/main.py`
serves directly at runtime.

---

## Step 5: Set Environment Variables

In the Render dashboard, go to your service → **Environment** tab and add:

| Key | Required? | Value |
|-----|-----------|-------|
| `GOOGLE_SHEET_ID` | Required | Your Google Sheet ID (from the sheet URL) |
| `GOOGLE_DRIVE_FOLDER_ID` | Required | Your Google Drive folder ID |
| `GOOGLE_CREDENTIALS_JSON` | Required | The **entire contents** of your `service-account-key.json` file (paste the full JSON) |
| `SESSION_SECRET_KEY` | Required | A long random string — signs admin/OAuth session cookies. The app **refuses to start** in production without this set |
| `ADMIN_PASSCODE` | Recommended | Shared passcode gating destructive actions (add/delete entries, delete photos, force-refresh, AI photo analysis). Leave unset to disable those routes entirely |
| `SCOREBOARD_TOP_N` | Optional | `20` (default) |
| `DATA_CACHE_TTL_SECONDS` | Optional | `300` (default) |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Optional | Enables per-user Google sign-in for Drive uploads |
| `GOOGLE_OAUTH_REDIRECT_URI` | Optional | `https://your-app.onrender.com/api/auth/callback` — must also be registered as an authorized redirect URI in Google Cloud Console |
| `FRONTEND_URL` | Optional | `https://your-app.onrender.com` — where the OAuth callback redirects back to |
| `OPENAI_API_KEY` / `OPENAI_VISION_MODEL` | Optional | Enables AI photo analysis (model defaults to `gpt-4o-mini`) |
| `PYTHON_VERSION` | Recommended | `3.11.6` |
| `NODE_VERSION` | Recommended | `20` (or newer) — needed for the frontend build step |

### How to get the credentials JSON value:

```bash
# On your local machine, copy the file contents:
cat service-account-key.json | pbcopy
```

Then paste it directly into the `GOOGLE_CREDENTIALS_JSON` value field in Render.

### How to generate a SESSION_SECRET_KEY:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Step 6: Deploy

Click **Create Web Service** (or if already created, push to your repo and it auto-deploys).

Render will:
1. Clone your repo
2. Run the build command — install backend deps, then install and build the frontend
3. Run `start_backend.sh`, which writes the credentials file and starts uvicorn

---

## Summary of Files Involved

| File | Purpose |
|------|---------|
| `start_backend.sh` | Writes credentials from env var & launches the FastAPI app via uvicorn on the correct port |
| `backend/requirements.txt` | Python dependencies for the FastAPI backend |
| `frontend/` | React app; `npm run build` produces `frontend/dist`, served by the backend |
| `render.yaml` | (Optional) Blueprint for one-click deploy config |
| `.gitignore` | Should include `service-account-key.json`, `.env`, `__pycache__/`, `frontend/dist/`, `frontend/node_modules/` |

---

## Troubleshooting

### App crashes on startup
- Check the **Logs** tab in Render dashboard
- Ensure `GOOGLE_CREDENTIALS_JSON` is the raw JSON (not base64 encoded)
- Verify the JSON is valid (no extra quotes or escaping issues)
- If the log shows `SESSION_SECRET_KEY is not set`, add it as an environment variable — the app intentionally refuses to start in production without it

### "Missing required environment variables" error
- Make sure `GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_FOLDER_ID`, and `GOOGLE_CREDENTIALS_JSON` are all set in Render

### Build fails on the frontend step
- Confirm `NODE_VERSION` is set (Render defaults to an older Node otherwise) and that `frontend/package.json` builds locally with `npm run build`

### Blank page / 404s after deploy
- Confirm the build command actually ran `npm run build` and that `frontend/dist` exists — check the build logs for frontend errors

### Port binding issues
- `start_backend.sh` uses `${PORT}` which Render sets automatically — don't hardcode a port

### Free tier spin-down
- Render free tier services spin down after 15 minutes of inactivity
- First request after spin-down takes ~30–60 seconds to respond
- Upgrade to Starter ($7/mo) for always-on

---

## Notes

- The free tier gives you 750 hours/month of runtime — more than enough for a single service
- Render auto-deploys on every push to your connected branch
- Custom domains are supported (even on free tier with manual DNS config)
