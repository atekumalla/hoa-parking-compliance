# Station 121 HOA Guest Parking Compliance Tracker

A Streamlit web application for HOA volunteers to track guest parking violations, enforce parking rules, and maintain compliance records using Google Sheets as the backend database.

## Features

- 📝 Log vehicle sightings with license plate, tag number, make, and model
- ⚡ Quick-select dropdown to auto-fill previously seen vehicles when adding entries
- � Built-in camera capture (rear camera, zoom, selectable quality) plus file upload
- 🤖 Optional AI photo analysis that auto-fills plate, make, and model from a photo
- 🖼️ Photos stored in Google Drive with monthly organization and an automatic timestamp stamp
- 📊 Real-time scoreboard showing most frequent violators with dark-themed cards
- 🏷️ Top-used parking tags over the last 90 days
- 🚨 "Needs attention" list surfacing unwarned vehicles approaching the 9-day limit
- ⚠️ Automated tracking of 9-day/30-day parking rule violations
- 🔍 Vehicle history search by license plate, tag number, make, or model (with dropdowns)
- 📤 Export all photos for a vehicle into a single Drive folder
- 💾 Storage management: usage metrics and bulk photo cleanup by month or date range
- 🚀 Quick-add and History buttons on each scoreboard card
- 🎨 Color-coded visual indicators for warned and towed vehicles
- 📅 Automatic monthly tab/folder creation
- 📎 Quick links to Google Sheet and Google Drive from the app header
- 📜 Built-in Rules page documenting all parking enforcement policies

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
- Google Cloud Platform account (free tier is sufficient)
- Google Sheet for data storage
- Google Drive folder for photo storage
- *(Optional)* Google OAuth client credentials — lets each user upload photos against
  their own Drive quota instead of the service account's
- *(Optional)* OpenAI API key — enables AI photo analysis

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
   MEMORY_DEBUG=0
   ```

3. *(Optional)* To let users upload photos against their own Google Drive quota,
   create an OAuth 2.0 Client ID (Web application) in **APIs & Services > Credentials**,
   add your app URL as an authorized redirect URI, then add:
   ```bash
   GOOGLE_OAUTH_CLIENT_ID=your_oauth_client_id
   GOOGLE_OAUTH_CLIENT_SECRET=your_oauth_client_secret
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8501
   ```
   When these are set, a "Sign in with Google" control appears in the app header.
   This sidesteps the service-account storage quota problem described in Step 6.

4. *(Optional)* To enable AI photo analysis:
   ```bash
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_VISION_MODEL=gpt-4o-mini
   ```

### Step 8: Install Dependencies

```bash
pip install -r requirements.txt
```

Or use a virtual environment (recommended):

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 9: Run the Application

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`

## Usage

### Logging a Vehicle

1. Navigate to the **📝 Add Vehicle** tab
2. **Quick Select**: Use the dropdown at the top to pick a previously seen vehicle — this auto-fills all fields
3. Or manually enter the license plate and tag number (make/model are optional)
4. Optionally attach a photo, either by:
   - **📷 Camera** — opens the built-in capture view (rear camera by default, with zoom
     controls and a Min/Mid/Max quality toggle that remembers your last choice)
   - **📁 Upload** — jpg, jpeg, png, webp, heic, bmp, or gif, max 10MB
5. If an OpenAI key is configured, click **🔍 Analyze with AI** to auto-fill the plate,
   make, and model from the photo. If the detected plate matches an existing record,
   the tag number is filled in from history too. Always verify the reading before submitting.
6. Check **Warned** or **Towed** if applicable (timestamps are auto-captured)
7. Click **Submit**

> **Photo quality tip**: the **Mid** camera preset gives the best results for AI plate
> reading. **Min** captures below the resolution the analysis pipeline can use, and
> **Max** is slower with no meaningful accuracy gain.

### Scoreboard

1. View the **📊 Scoreboard** tab to see the top vehicles in the last 30 days
2. The tab opens with **🏷️ Top Used Tags** (last 90 days) and a **🚨 Needs Attention**
   list of unwarned vehicles approaching the 9-day limit
3. Vehicle cards are color-coded: dark gray (active), dark amber (warned), dark red (towed)
4. Each card shows unique days parked, last seen date, and status
5. Click **➕ Quick Add** to log a new sighting for that vehicle (pre-filled)
6. Click **🔍 History** to jump directly to that vehicle's full history

### Vehicle History

1. Go to the **🔍 Vehicle History** tab (or click History from the scoreboard)
2. Search by any combination of:
   - **License Plate** — type full or partial, or pick from dropdown
   - **Tag Number** — type or pick from dropdown
   - **Make** — type or pick from dropdown
   - **Model** — type or pick from dropdown
3. Multiple filters can be combined (e.g., search by tag AND make)
4. View all historical entries, warnings, tows, and photos for matching vehicles
5. Click **📤 Export Photos** to collect every photo for a vehicle into a single Drive
   folder. This creates shortcuts rather than copies, so it consumes no extra storage.
   Requires Google sign-in.

### Storage

The **💾 Storage** tab manages the Drive photo archive:

1. View total usage, file counts, and a per-month breakdown
2. Delete photos in bulk by month or by date range (each deletion asks for confirmation)
3. Use **Refresh Cache** if the numbers look stale

> ⚠️ Deletions are permanent. Photo URLs already written to the Google Sheet will
> stop resolving for any photos you remove.

### Rules

The **📜 Rules** tab displays all six parking enforcement rules including:
- Tag/placard requirements
- The 9-day/30-day rolling window rule
- Warning and towing policy with a summary table

### Refreshing Data

Click the **🔄 Refresh Data** button in the Scoreboard tab to reload cache and recalculate warning counts from the Google Sheet.

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

The app runs on [Render](https://render.com/) via `start.sh`. See
[DEPLOY_RENDER.md](DEPLOY_RENDER.md) for full instructions.

Key differences from local development:

- The service account JSON is passed as a single `GOOGLE_CREDENTIALS_JSON` environment
  variable rather than a file. `start.sh` writes it to a temp file at boot and points
  `GOOGLE_APPLICATION_CREDENTIALS` at it, so no credentials live in the repo.
- `GOOGLE_OAUTH_REDIRECT_URI` must match your deployed URL (e.g. `https://your-app.onrender.com`)
  and be registered as an authorized redirect URI in Google Cloud Console.
- `start.sh` sets `MALLOC_ARENA_MAX=2` and `PYTHONMALLOC=malloc` to limit glibc arena
  fragmentation, which matters on a 512MB instance.
- Uploads are capped at 10MB via `--server.maxUploadSize=10`.
- Set `MEMORY_DEBUG=1` to log RSS and peak memory at key checkpoints when diagnosing
  out-of-memory restarts.

## Troubleshooting

### Authentication Errors

- **Error**: "Permission denied" or "403 Forbidden"
  - **Solution**: Verify the service account email has Editor access to both the Sheet and Drive folder

### Module Not Found

- **Error**: `ModuleNotFoundError: No module named 'streamlit'`
  - **Solution**: Install dependencies with `pip install -r requirements.txt`

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

- **Symptom**: The **🔍 Analyze with AI** button does not appear
  - **Solution**: Set `OPENAI_API_KEY` in your `.env` and restart the app. The button is
    hidden entirely when no key is configured.

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
  - The zoom slider only appears when the device reports zoom capability; many desktop
    webcams do not.

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
