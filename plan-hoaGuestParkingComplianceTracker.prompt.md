# Plan: HOA Guest Parking Compliance Tracker (Final)

Build a Streamlit web app with Google Sheets backend and Drive photo storage for HOA volunteers to log guest parking. App normalizes license plates, counts unique parking days for 9-day/30-day violation rules, caches warning counts with manual refresh, auto-creates monthly tabs/folders, provides quick-add with pre-filled details, supports optional photo upload with error handling, displays color-coded scoreboard sorted by violation frequency, and searches vehicle history with partial license plate matching while preserving session state.

## Steps

1. **Set up Python project structure** with [requirements.txt](requirements.txt) including streamlit, gspread, google-auth, google-api-python-client, pandas, pillow, python-dotenv, and create [.env.example](.env.example) with `GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_FOLDER_ID`, `SCOREBOARD_TOP_N`, `GOOGLE_APPLICATION_CREDENTIALS`.

2. **Create comprehensive [README.md](README.md)** with step-by-step instructions for: creating Google Cloud project, enabling Google Sheets API and Google Drive API, generating service account JSON key file, sharing specific Google Sheet with service account email (editor access), sharing Drive folder with service account email (editor access), extracting Sheet ID from Sheet URL, extracting Folder ID from Drive folder URL, configuring `.env` file with all required variables.

3. **Build Google Sheets integration module** to authenticate via service account, define schema (Timestamp | License Plate | Tag Number | Make | Model | Warned | Warned Date | Warning Count | Towed | Towed Date | Photo URL), access/create monthly tabs (Jan-2026 format) with auto-creation at month boundaries, read all historical data for vehicle lookups, read 30-day rolling data for violation calculations, append normalized entries with optional photo URL, and update warning counts.

4. **Build Google Drive integration module** to authenticate with same service account, check/create monthly folders (Jan-2026) with auto-creation logic, validate file size (10MB max) and accept all image formats, convert to JPG using Pillow, rename as `{LICENSE}_{TAG}_{TIMESTAMP}.jpg`, upload to current month's folder, return shareable link, and handle failures gracefully with error messages.

5. **Implement core business logic** for license plate normalization (uppercase all letters), unique day counter (ignoring duplicate same-day entries) within 30-day rolling window, violation detection using 9 unique days threshold per five parking rules, warning count cache from historical data with refresh function, and frequency tracker for scoreboard.

6. **Create Streamlit UI with session state management** including: (1) Manual entry form with normalized license/tag/make/model inputs, warning/tow checkboxes with auto-timestamp, optional photo uploader with 10MB validation and error display; (2) Color-coded scoreboard sorted by unique days parked (descending) showing top N vehicles with columns (License | Tag | Unique Days | Last Seen | Warning Count | Last Warned | Towed | Towed Date), visual indicators for warned (yellow/orange) and towed (red) vehicles, plus quick-add buttons; (3) Quick-add modal pre-filling all details with photo upload, warning/tow checkboxes, current timestamp; (4) Vehicle history search with partial license plate matching showing all entries with Drive photo links and warning/tow events.

7. **Implement application initialization and utilities** to load Google credentials on startup, read full historical data to build warning count cache, provide "Refresh Data" button for on-demand recalculation, auto-create new monthly Sheet tabs and Drive folders when transitioning months, sync all writes immediately to Sheets, and preserve form inputs and session state across Streamlit reruns.

## Requirements

### Parking Rules
1. Every car parked in guest parking needs to have either an HOA issued placard or a paper parking tag. If either of those is missing, the car can be towed
2. With a valid parking tag/pass, a car cannot be parked in guest parking more than 9 days in any 30 day period
3. If a car is parked more than 9 days in a 30 day period, it has to be warned once
4. If the car continues to be parked in the same 30 day period after being warned, it can be towed
5. If the car is seen again in a different 30 day period and it exceeds the 9 day limit, it can be towed since it has already been warned once before

### Technical Requirements
- **Backend**: Python with Google Sheets as database
- **UI Framework**: Streamlit (pure Python, simple, no authentication needed)
- **Data Storage**: Google Sheets with monthly tabs (Jan-2026, Feb-2026, etc.)
- **Photo Storage**: Google Drive with monthly folders matching sheet tabs
- **License Plate Normalization**: All letters uppercased (7ghv567 → 7GHV567)
- **Unique Day Counting**: Multiple entries same day = 1 day for violation calculations
- **Historical Data**: Never delete entries, keep for full vehicle history
- **Photo Upload**: Optional, all formats accepted, 10MB limit, convert to JPG
- **Photo Naming**: `{LICENSE}_{TAG}_{TIMESTAMP}.jpg`
- **Scoreboard**: Top N vehicles (default 20, configurable via env var)
- **Warning/Tow Tracking**: Manual checkboxes with auto-timestamp capture
- **Warning Count**: Cached from historical data, manual refresh button
- **Quick Add**: Pre-fill license/tag/make/model from scoreboard selection
- **Vehicle History**: Partial license plate search across all historical data
- **Month Transitions**: Auto-create new Sheet tabs and Drive folders
- **Session State**: Preserve form inputs across Streamlit reruns

### Google Sheet Schema
| Timestamp | License Plate | Tag Number | Make | Model | Warned | Warned Date | Warning Count | Towed | Towed Date | Photo URL |
|-----------|---------------|------------|------|-------|--------|-------------|---------------|-------|------------|-----------|

### Environment Variables
- `GOOGLE_SHEET_ID` - ID from Google Sheet URL
- `GOOGLE_DRIVE_FOLDER_ID` - ID from Drive folder URL
- `SCOREBOARD_TOP_N` - Number of vehicles to show (default: 20)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON key

### UI Components

#### 1. Manual Entry Form
- License Plate (auto-normalized to uppercase)
- Tag Number (string, shared across cars)
- Make
- Model
- Warned checkbox (auto-captures timestamp when checked)
- Towed checkbox (auto-captures timestamp when checked)
- Photo upload (optional, with 10MB validation and error display)
- Submit button

#### 2. Scoreboard
- Display top N vehicles sorted by unique days parked (descending)
- Columns: License | Tag | Unique Days | Last Seen | Warning Count | Last Warned | Towed | Towed Date
- Color coding: Warned vehicles (yellow/orange), Towed vehicles (red)
- Quick-add button per row
- Refresh Data button to recalculate cache

#### 3. Quick-Add Modal
- Auto-populated: License, Tag, Make, Model (from selected vehicle)
- Photo upload (optional)
- Warned/Towed checkboxes
- Auto-timestamp on submission
- Submit button

#### 4. Vehicle History Search
- License plate input (supports partial matching after normalization)
- Display all historical entries for matching vehicles
- Show: Timestamp, Tag, Photo URL (as link), Warned status/date, Towed status/date
- Timeline of all warning/tow events

### Error Handling
- Photo upload failure: Show error message, allow entry submission without photo
- Google API failures: Display user-friendly error messages
- Missing environment variables: Fail fast with clear setup instructions
- Invalid file sizes: Block upload with validation message

## Implementation Ready

This plan is complete and ready for implementation. All clarifying questions have been addressed. The application will provide a streamlined workflow for HOA volunteers to track parking violations with automated rule enforcement, visual indicators for at-risk vehicles, and comprehensive historical tracking.
