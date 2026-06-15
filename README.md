# Station 121 HOA Guest Parking Compliance Tracker

A Streamlit web application for HOA volunteers to track guest parking violations, enforce parking rules, and maintain compliance records using Google Sheets as the backend database.

## Features

- 📝 Log vehicle sightings with license plate, tag number, make, and model
- ⚡ Quick-select dropdown to auto-fill previously seen vehicles when adding entries
- 📸 Optional photo uploads stored in Google Drive with monthly organization
- 📊 Real-time scoreboard showing most frequent violators with dark-themed cards
- ⚠️ Automated tracking of 9-day/30-day parking rule violations
- 🔍 Vehicle history search by license plate, tag number, make, or model (with dropdowns)
- 🚀 Quick-add and History buttons on each scoreboard card
- 🎨 Color-coded visual indicators for warned and towed vehicles
- 📅 Automatic monthly tab/folder creation
- 📎 Quick links to Google Sheet and Google Drive from the app header
- 📜 Built-in Rules page documenting all parking enforcement policies

## Parking Rules Enforced

1. Every car must have an HOA issued placard or paper parking tag (or can be towed)
2. Cars cannot be parked more than 9 unique days in any 30-day period
3. First violation over 9 days requires one warning
4. Continued parking in same 30-day period after warning = eligible for towing
5. Future violations in different 30-day periods = eligible for towing (already warned)

## Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account (free tier is sufficient)
- Google Sheet for data storage
- Google Drive folder for photo storage

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
   GOOGLE_SHEET_ID=your_actual_sheet_id_from_step_5
   GOOGLE_DRIVE_FOLDER_ID=your_actual_folder_id_from_step_6
   GOOGLE_APPLICATION_CREDENTIALS=service-account-key.json
   SCOREBOARD_TOP_N=20
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
4. Optionally upload a photo (max 10MB, any image format)
5. Check **Warned** or **Towed** if applicable (timestamps are auto-captured)
6. Click **Submit**

### Scoreboard

1. View the **📊 Scoreboard** tab to see the top vehicles in the last 30 days
2. Cards are color-coded: dark gray (active), dark amber (warned), dark red (towed)
3. Each card shows unique days parked, last seen date, and status
4. Click **➕ Quick Add** to log a new sighting for that vehicle (pre-filled)
5. Click **🔍 History** to jump directly to that vehicle's full history

### Vehicle History

1. Go to the **🔍 Vehicle History** tab (or click History from the scoreboard)
2. Search by any combination of:
   - **License Plate** — type full or partial, or pick from dropdown
   - **Tag Number** — type or pick from dropdown
   - **Make** — type or pick from dropdown
   - **Model** — type or pick from dropdown
3. Multiple filters can be combined (e.g., search by tag AND make)
4. View all historical entries, warnings, tows, and photos for matching vehicles

### Rules

The **📜 Rules** tab displays all parking enforcement rules including:
- Tag/placard requirements
- The 9-day/30-day rule
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
├── Jan-2026/
│   ├── ABC123_TAG001_20260107_143022.jpg
│   ├── XYZ789_TAG002_20260107_145533.jpg
│   └── ...
├── Feb-2026/
│   └── ...
└── ...
```

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

## Security Notes

- Never commit your `service-account-key.json` or `.env` file to version control
- The `.gitignore` file already excludes these files
- Keep your service account credentials secure
- Limit service account permissions to only the specific Sheet and Drive folder needed

## License

This project is intended for HOA internal use.

## Support

For issues or questions, contact your HOA technical administrator.
