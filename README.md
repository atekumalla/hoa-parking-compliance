# Station 121 HOA Guest Parking Compliance Tracker

A web app for HOA volunteers to track guest parking violations, enforce parking rules, and maintain compliance records using Google Sheets as the backend database. The app is a FastAPI backend (Python) paired with a React + Vite single-page frontend (TypeScript).

> The project originally shipped as a single Streamlit app (`app.py` and friends at
> the repo root). Those files are kept only as historical reference — the active
> application is `backend/` + `frontend/`. See [Architecture](#architecture) below.

## Features

- 📝 Log vehicle sightings with license plate, tag number, make, and model
- ⚡ Type-to-filter autocomplete to auto-fill previously seen vehicles when adding entries — narrows as you type instead of requiring a dropdown click
- 📷 Built-in camera capture (rear camera, live preview) with a zoom slider **and** quick zoom-preset buttons (1×/2×/3×/4×/6×/8×/Max, plus −/+ step buttons) and a selectable Min/Mid/Max resolution quality toggle that remembers your last choice
- 📁 File upload as an alternative to the camera (jpg, jpeg, png, webp, heic, bmp, gif, max 10MB)
- 🤖 Optional AI photo analysis that auto-fills plate, make, and model from a photo
- 🖼️ Photos stored in Google Drive with monthly organization and an automatic timestamp stamp
- ⚠️ Duplicate-entry detection — warns if the same plate was already logged today, with a one-click override
- 📊 Real-time scoreboard showing most frequent violators
- 🏷️ Top-used parking tags over the last 90 days
- 🚨 "Needs attention" list surfacing unwarned vehicles approaching the 9-day limit
- ⚠️ Automated tracking of 9-day/30-day parking rule violations
- 🔍 Vehicle history search by license plate, tag number, make, or model (with autocomplete suggestions)
- 📤 Export all photos for a vehicle into a single Drive folder
- 💾 Storage management: usage metrics and bulk photo cleanup by month or date range
- 🚀 Quick-add and History buttons on each scoreboard card, plus a confirmation modal before deleting an entry
- 🔒 Shared admin passcode gate protecting destructive actions (add/delete entries, delete photos, force-refresh) — reads stay open to everyone
- 🌓 Light/dark theme toggle ("day shift" / "night patrol"), persisted per browser
- 🎨 Color-coded visual indicators for warned and towed vehicles
- 📅 Automatic monthly tab/folder creation
- 📎 Quick links to Google Sheet and Google Drive from the app header
- 📜 Built-in Rules page documenting all parking enforcement policies

## Architecture

```
backend/            FastAPI app — Google Sheets/Drive integration, compliance
  app/              rules engine, AI photo analysis, admin + OAuth sessions
    routers/        /api/entries, /api/scoreboard, /api/vehicle-history,
                     /api/storage, /api/admin, /api/auth
    services/        sheets_manager, drive_manager, compliance_engine,
                     vehicle_recognition, photo_utils
frontend/           React + TypeScript SPA (Vite), one page per feature area
  src/pages/        AddVehiclePage, ScoreboardPage, VehicleHistoryPage,
                     StoragePage, RulesPage
```

- In local development the two run as separate processes: the FastAPI backend
  on `:8000` and the Vite dev server on `:5173`, which proxies `/api/*` requests
  to the backend (see `frontend/vite.config.ts`) so the browser sees everything
  as same-origin.
- In production, `npm run build` produces `frontend/dist`, and the FastAPI app
  serves those static files directly — one process, one origin, no CORS needed.
- A shared in-memory cache (`backend/app/state.py`) is loaded once per process
  and reused across requests/users, instead of each browser session re-reading
  the whole Google Sheet.

## Parking Rules Enforced

1. Every vehicle in a guest spot must display an HOA-issued placard or paper parking tag
2. Vehicles without a valid tag or placard are subject to immediate towing, without warning
3. Guest vehicles cannot be parked more than 9 unique days in any rolling 30-day period
   (multiple sightings on the same calendar day count as one day)
4. First violation over 9 days requires one written warning
5. Continued parking in the same 30-day period after a warning = eligible for towing
6. Future violations in a different 30-day period = eligible for towing, since a prior
   warning carries forward permanently

## Prerequisites

- Python 3.11.6 (pinned in `runtime.txt`; 3.9+ works for local development)
- Node.js 18+ and npm (to run/build the React frontend)
- Google Cloud Platform account (free tier is sufficient)
- Google Sheet for data storage
- Google Drive folder for photo storage
- *(Optional)* Google OAuth client credentials — lets each user upload photos against
  their own Drive quota instead of the service account's
- *(Optional)* OpenAI API key — enables AI photo analysis
- *(Optional but recommended)* An admin passcode — gates destructive actions
  (add/delete entries, delete photos, force-refresh) behind a shared passcode

## Setup Instructions

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Create Project** or select an existing project
3. Give your project a name (e.g., "HOA Parking Tracker")
4. Click **Create**

### Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for and enable the following APIs:
   - **Google Sheets API**
   - **Google Drive API**
3. Click **Enable** for each API

### Step 3: Create Service Account

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **Service Account**
3. Enter a service account name (e.g., "parking-tracker-service")
4. Click **Create and Continue**
5. Skip the optional permissions (click **Continue** then **Done**)

### Step 4: Generate Service Account Key

1. In the **Service Accounts** list, click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Select **JSON** as the key type
5. Click **Create**
6. The JSON key file will download automatically
7. **IMPORTANT**: Keep this file secure - it provides access to your Google resources
8. Save the file in your project directory (e.g., `service-account-key.json`)

### Step 5: Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new blank spreadsheet
3. Name it (e.g., "HOA Parking Compliance")
4. **Important**: Copy the Sheet ID from the URL
   - URL format: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit`
   - The Sheet ID is the long string between `/d/` and `/edit`
5. Share the sheet with your service account:
   - Click the **Share** button
   - Paste the service account email (found in your JSON key file, looks like `parking-tracker-service@project-id.iam.gserviceaccount.com`)
   - Give it **Editor** access
   - Uncheck "Notify people"
   - Click **Share**

### Step 6: Create Google Drive Folder (Shared Drive Required)

> ⚠️ **Important**: You must use a **Shared Drive** (not a regular "My Drive" folder). Service accounts have no personal Drive storage quota, so uploads to regular folders will fail with a "storage quota" error. Files in a Shared Drive use the organization's pooled storage instead.

#### Option A: Google Workspace (Recommended)

1. Go to [Google Drive](https://drive.google.com/) > **Shared Drives** (in the left sidebar)
2. Click **+ New** to create a Shared Drive (e.g., "HOA Parking")
3. Add your service account email as a **Content Manager**:
   - Click the Shared Drive name > **Manage members**
   - Paste the service account email (found in your JSON key file as `client_email`)
   - Set role to **Content Manager**
   - Click **Send**
4. Create a folder inside the Shared Drive (e.g., "Parking Photos")
5. **Important**: Copy the Folder ID from the URL
   - URL format: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID`
   - The Folder ID is the string after `/folders/`

#### Option B: Personal Gmail (No Shared Drives Available)

If you're on a free personal Gmail account, Shared Drives are not available. As an alternative:

1. Go to [Google Drive](https://drive.google.com/)
2. Create a new folder (e.g., "HOA Parking Photos")
3. Copy the Folder ID from the URL
   - URL format: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID`
   - The Folder ID is the string after `/folders/`
4. Share the folder with your service account:
   - Right-click the folder > **Share**
   - Paste the service account email
   - Give it **Editor** access
   - Uncheck "Notify people"
   - Click **Share**

> **Note for Option B**: If you encounter "storage quota exceeded" errors, you may need to use [domain-wide delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority) to have the service account impersonate your personal account for Drive uploads.

### Step 7: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your actual values:
   ```bash
   # Required
   GOOGLE_SHEET_ID=your_actual_sheet_id_from_step_5
   GOOGLE_DRIVE_FOLDER_ID=your_actual_folder_id_from_step_6
   GOOGLE_APPLICATION_CREDENTIALS=service-account-key.json

   # Optional
   SCOREBOARD_TOP_N=20
   DATA_CACHE_TTL_SECONDS=300
   ADMIN_PASSCODE=choose_a_shared_passcode
   SESSION_SECRET_KEY=a_long_random_string
   ```
   - `ADMIN_PASSCODE` gates destructive actions (add/delete entries, delete photos,
     force-refresh, and the AI photo analysis call). Leave it unset to disable those
     routes entirely rather than leave them unprotected.
   - `SESSION_SECRET_KEY` signs the admin/OAuth session cookies. It falls back to a
     fixed dev-only value locally, but **must** be set to a real secret in production
     (the backend refuses to start in prod without it).

3. *(Optional)* To let users upload photos against their own Google Drive quota,
   create an OAuth 2.0 Client ID (Web application) in **APIs & Services > Credentials**,
   add your app URL as an authorized redirect URI, then add:
   ```bash
   GOOGLE_OAUTH_CLIENT_ID=your_oauth_client_id
   GOOGLE_OAUTH_CLIENT_SECRET=your_oauth_client_secret
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/callback
   FRONTEND_URL=http://localhost:5173
   ```
   When these are set, a "Sign in with Google" control appears in the app header.
   This sidesteps the service-account storage quota problem described in Step 6.
   `FRONTEND_URL` is where the backend redirects back to after the OAuth callback
   (set it to your deployed URL in production).

4. *(Optional)* To enable AI photo analysis:
   ```bash
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_VISION_MODEL=gpt-4o-mini
   ```

### Step 8: Install Dependencies

Backend (Python), from the repo root:

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

Frontend (Node), in a separate terminal:

```bash
cd frontend
npm install
```

### Step 9: Run the Application

Run the backend and frontend as two separate processes during local development.

Terminal 1 — FastAPI backend on `:8000`:
```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — Vite dev server on `:5173` (proxies `/api/*` to the backend):
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser. The frontend talks to the backend
through the Vite proxy, so there's no CORS configuration to worry about.

> To run the production build locally instead (single process, no proxy):
> `cd frontend && npm run build`, then start the backend as above — it will
> serve `frontend/dist` directly at `http://localhost:8000`.

## Usage

### Logging a Vehicle

1. Navigate to the **Add Vehicle** page
2. **Quick Select**: Start typing in the autocomplete box at the top to narrow down
   previously seen vehicles, then click (or arrow-key + Enter) a match to auto-fill all fields
3. Or manually enter the license plate and tag number (make/model are optional)
4. Optionally attach a photo, either by:
   - **Take Photo** — opens the built-in capture view (rear camera by default, with a
     zoom slider, quick zoom-preset buttons up to 8×, and a Min/Mid/Max quality toggle
     that remembers your last choice)
   - **Upload File** — jpg, jpeg, png, webp, heic, bmp, or gif, max 10MB
5. If an OpenAI key and admin passcode are configured, click **Analyze with AI** to
   auto-fill the plate, make, and model from the photo (first unlock with the admin
   passcode via the lock icon in the header). If the detected plate matches an existing
   record, the tag number is filled in from history too. Always verify the reading
   before submitting.
6. Check **Warned** or **Towed** if applicable (timestamps are auto-captured)
7. Click **Submit** — if the plate was already logged today, you'll be asked to confirm
   before a duplicate entry is added

> **Photo quality tip**: the **Mid** camera preset gives the best results for AI plate
> reading. **Min** captures below the resolution the analysis pipeline can use, and
> **Max** is slower with no meaningful accuracy gain.

### Scoreboard

1. View the **Scoreboard** page to see the top vehicles in the last 30 days
2. The page opens with **Top Used Tags** (last 90 days) and a **Needs Attention**
   list of unwarned vehicles approaching the 9-day limit
3. Vehicle cards are color-coded: active, warned, and towed statuses
4. Each card shows unique days parked, last seen date, and status
5. Click **Quick Add** to log a new sighting for that vehicle (pre-filled)
6. Click **History** to jump directly to that vehicle's full history

### Vehicle History

1. Go to the **Vehicle History** page (or click History from the scoreboard)
2. Search by any combination of:
   - **License Plate** — type to search, with autocomplete suggestions from past entries
   - **Tag Number** — type to search, with autocomplete suggestions
   - **Make** — type to search, with autocomplete suggestions
   - **Model** — type to search, with autocomplete suggestions
3. Multiple filters can be combined (e.g., search by tag AND make)
4. View all historical entries, warnings, tows, and photos for matching vehicles
5. Click **Export Photos** to collect every photo for a vehicle into a single Drive
   folder. This creates shortcuts rather than copies, so it consumes no extra storage.
   Requires Google sign-in.

### Storage

The **Storage** page manages the Drive photo archive:

1. View total usage, file counts, and a per-month breakdown
2. Delete photos in bulk by month or by date range (each deletion asks for confirmation
   and requires the admin passcode)
3. Use **Refresh Cache** if the numbers look stale

> ⚠️ Deletions are permanent. Photo URLs already written to the Google Sheet will
> stop resolving for any photos you remove.

### Rules

The **Rules** page displays all six parking enforcement rules including:
- Tag/placard requirements
- The 9-day/30-day rolling window rule
- Warning and towing policy with a summary table

### Admin Unlock

Click the lock icon in the header and enter the shared `ADMIN_PASSCODE` to unlock
destructive actions (adding/deleting entries, deleting photos, force-refreshing data,
and AI photo analysis) for your current browser session. Unlock state expires after
12 hours of inactivity; AI photo analysis trust persists for 7 days so it doesn't
need re-entering constantly on a shared device.

### Refreshing Data

Click the **Refresh Data** button on the Scoreboard page to reload the cache and
recalculate warning counts from the Google Sheet.

## Data Structure

### Google Sheet Schema

Each monthly tab (e.g., "Jan-2026") contains the following columns:

| Column | Description |
|--------|-------------|
| Timestamp | Date and time of entry |
| License Plate | Normalized (uppercase) license plate |
| Tag Number | Parking tag/pass number |
| Make | Vehicle make |
| Model | Vehicle model |
| Warned | Y/N - Was vehicle warned |
| Warned Date | Timestamp when warned checkbox was checked |
| Warning Count | Total number of warnings for this vehicle |
| Towed | Y/N - Was vehicle towed |
| Towed Date | Timestamp when towed checkbox was checked |
| Photo URL | Google Drive link to vehicle photo |

### Google Drive Structure

```
HOA Parking Photos/
├── 2026-01/
│   ├── ABC123_TAG001_20260107_143022.jpg
│   ├── XYZ789_TAG002_20260107_145533.jpg
│   └── ...
├── 2026-02/
│   └── ...
└── ...
```

Photos are stamped with a PST timestamp before upload and capped at 2048px to keep
memory use predictable on small containers.

## Deployment

The app runs on [Render](https://render.com/) as a single web service. The build step
installs backend dependencies and builds the React frontend into `frontend/dist`;
`start_backend.sh` then starts the FastAPI backend, which serves that built frontend
as static files. See [DEPLOY_RENDER.md](DEPLOY_RENDER.md) for the full step-by-step guide.

**Build Command:**
```bash
pip install -r backend/requirements.txt && cd frontend && npm install && npm run build
```

**Start Command:**
```bash
sh start_backend.sh
```

**Environment variables** (Render dashboard → your service → Environment):

| Key | Value |
|-----|-------|
| `GOOGLE_SHEET_ID` | Your Google Sheet ID |
| `GOOGLE_DRIVE_FOLDER_ID` | Your Google Drive folder ID |
| `GOOGLE_CREDENTIALS_JSON` | The entire contents of your `service-account-key.json` file |
| `SESSION_SECRET_KEY` | A long random string — **required** in production |
| `ADMIN_PASSCODE` | Shared passcode for destructive actions (optional but recommended) |
| `SCOREBOARD_TOP_N` | `20` (optional) |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Optional, for per-user Drive uploads |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://your-app.onrender.com/api/auth/callback` (must match Google Cloud Console) |
| `FRONTEND_URL` | `https://your-app.onrender.com` |
| `OPENAI_API_KEY` / `OPENAI_VISION_MODEL` | Optional, for AI photo analysis |
| `PYTHON_VERSION` | `3.11.6` |

Key differences from local development:

- The service account JSON is passed as a single `GOOGLE_CREDENTIALS_JSON` environment
  variable rather than a file. `start_backend.sh` writes it to a temp file at boot and
  points `GOOGLE_APPLICATION_CREDENTIALS` at it, so no credentials live in the repo.
- `GOOGLE_OAUTH_REDIRECT_URI` and `FRONTEND_URL` must match your deployed URL and the
  redirect URI must be registered in Google Cloud Console.
- `start_backend.sh` sets `MALLOC_ARENA_MAX=2` and `PYTHONMALLOC=malloc` to limit glibc
  arena fragmentation, which matters on a 512MB instance.
- Uploads are capped at 10MB (enforced in `backend/app/services/drive_manager.py`).
- The backend refuses to start in production if `SESSION_SECRET_KEY` isn't set.

## Troubleshooting

### Authentication Errors

- **Error**: "Permission denied" or "403 Forbidden"
  - **Solution**: Verify the service account email has Editor access to both the Sheet and Drive folder

### Module/Package Not Found

- **Error**: `ModuleNotFoundError: No module named 'fastapi'` (or similar)
  - **Solution**: Install backend dependencies with `pip install -r backend/requirements.txt`
- **Error**: `vite: command not found` or missing frontend modules
  - **Solution**: Run `npm install` inside `frontend/`

### Sheet Not Found

- **Error**: "Spreadsheet not found"
  - **Solution**: Double-check the `GOOGLE_SHEET_ID` in your `.env` file

### Photo Upload Fails

- **Error**: "Service accounts don't have storage quota" or "storageQuotaExceeded"
  - **Cause**: Service accounts have 0 bytes of personal Drive storage. Files uploaded to regular folders are owned by the service account, which has no quota.
  - **Solution**: Use a **Shared Drive** (Team Drive) instead of a regular folder. See Step 6 above for setup instructions. The `GOOGLE_DRIVE_FOLDER_ID` must point to a folder inside a Shared Drive.

- **Error**: General photo upload errors / "Permission denied"
  - **Solution**: Ensure the service account has **Content Manager** access on the Shared Drive, and verify `GOOGLE_DRIVE_FOLDER_ID` is correct

### Environment Variables Not Loaded

- **Error**: Missing configuration
  - **Solution**: Ensure `.env` file exists in the project root directory

### AI Analysis Unavailable

- **Symptom**: The **Analyze with AI** button does not appear
  - **Solution**: Set `OPENAI_API_KEY` in your `.env` and restart the app. The button is
    hidden entirely when no key is configured.
- **Symptom**: Clicking **Analyze with AI** returns a 401
  - **Solution**: Unlock the admin passcode first (lock icon in the header) — the call
    is gated behind `ADMIN_PASSCODE` as a cost/abuse control.

- **Symptom**: The plate is read incorrectly
  - **Solution**: Set the camera quality toggle to **Mid**, get closer or use the zoom
    control so the plate fills more of the frame, and avoid steep angles. You can also
    try a stronger model by setting `OPENAI_VISION_MODEL` (e.g. `gpt-4o` or `gpt-4.1`).
    Always verify AI-filled fields before submitting.

### Camera Not Working

- **Symptom**: Camera view is blank or permission is denied
  - **Solution**: Browsers only allow camera access over HTTPS or on `localhost`. If you
    are accessing the app over plain HTTP on a LAN IP, the camera will not start — use
    the file upload option or deploy behind HTTPS.
  - The zoom slider and preset buttons only appear when the device reports zoom
    capability; many desktop webcams do not.

## Security Notes

- Never commit your `service-account-key.json` or `.env` file to version control
- The `.gitignore` file already excludes these files (including a `*service-account*.json` glob)
- In production, pass credentials as environment variables instead of files — see Deployment
- Keep your service account credentials secure
- Limit service account permissions to only the specific Sheet and Drive folder needed
- OAuth refresh tokens are stored in browser `localStorage`, with a URL query parameter
  as a fallback. Avoid sharing a URL containing an `?rt=` parameter, since it grants
  Drive upload access to your account.

## License

This project is intended for HOA internal use.

## Support

For issues or questions, contact your HOA technical administrator.
