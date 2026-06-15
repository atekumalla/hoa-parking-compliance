# Deploying to Render

This guide walks you through deploying the HOA Guest Parking Compliance Tracker to [Render](https://render.com).

---

## Prerequisites

- A [Render account](https://dashboard.render.com/register) (free tier works)
- Your code pushed to a GitHub repository
- Your Google service account JSON key contents (you'll paste it as an env var)

---

## Step 1: Prepare Your Repository

Make sure the following files are committed and pushed to GitHub:

- `app.py`
- `sheets_manager.py`
- `drive_manager.py`
- `compliance_engine.py`
- `requirements.txt`

> ⚠️ **Do NOT commit** `service-account-key.json` or `.env` to your repo. Add them to `.gitignore`.

---

## Step 2: Create a `render.yaml` (Optional — Blueprint)

You can either configure via the Render dashboard (Step 3) or add this file to your repo for one-click deploy:

```yaml
services:
  - type: web
    name: hoa-parking-compliance
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: sh start.sh
    envVars:
      - key: GOOGLE_SHEET_ID
        sync: false
      - key: GOOGLE_DRIVE_FOLDER_ID
        sync: false
      - key: GOOGLE_CREDENTIALS_JSON
        sync: false
      - key: SCOREBOARD_TOP_N
        value: "20"
      - key: PYTHON_VERSION
        value: "3.11.6"
```

---

## Step 3: Create a Start Script

Create a file called `start.sh` in your project root:

```bash
#!/usr/bin/env bash

# Write the service account JSON from the environment variable to a file
echo "$GOOGLE_CREDENTIALS_JSON" > /tmp/service-account-key.json

# Export the path so the app can find it
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/service-account-key.json

# Run Streamlit on Render's expected port
streamlit run app.py \
  --server.port=${PORT:-8501} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
```

Make it executable locally:

```bash
chmod +x start.sh
```

Commit and push both `start.sh` (and optionally `render.yaml`) to your repo.

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
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `sh start.sh` |
| **Instance Type** | Free (or Starter for better performance) |

---

## Step 5: Set Environment Variables

In the Render dashboard, go to your service → **Environment** tab and add:

| Key | Value |
|-----|-------|
| `GOOGLE_SHEET_ID` | Your Google Sheet ID (from the sheet URL) |
| `GOOGLE_DRIVE_FOLDER_ID` | Your Google Drive folder ID |
| `GOOGLE_CREDENTIALS_JSON` | The **entire contents** of your `service-account-key.json` file (paste the full JSON) |
| `SCOREBOARD_TOP_N` | `20` (optional, defaults to 20) |
| `PYTHON_VERSION` | `3.11.6` |

### How to get the credentials JSON value:

```bash
# On your local machine, copy the file contents:
cat service-account-key.json | pbcopy
```

Then paste it directly into the `GOOGLE_CREDENTIALS_JSON` value field in Render.

---

## Step 6: Deploy

Click **Create Web Service** (or if already created, push to your repo and it auto-deploys).

Render will:
1. Clone your repo
2. Install dependencies from `requirements.txt`
3. Run `start.sh` which writes the credentials file and starts Streamlit

---

## Summary of Files to Add

| File | Purpose |
|------|---------|
| `start.sh` | Writes credentials from env var & launches Streamlit on correct port |
| `render.yaml` | (Optional) Blueprint for one-click deploy config |
| `.gitignore` | Should include `service-account-key.json`, `.env`, `__pycache__/` |

---

## Troubleshooting

### App crashes on startup
- Check the **Logs** tab in Render dashboard
- Ensure `GOOGLE_CREDENTIALS_JSON` is the raw JSON (not base64 encoded)
- Verify the JSON is valid (no extra quotes or escaping issues)

### "Missing required environment variables" error
- Make sure all three env vars (`GOOGLE_SHEET_ID`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_CREDENTIALS_JSON`) are set in Render

### Port binding issues
- The `start.sh` script uses `${PORT}` which Render sets automatically — don't hardcode a port

### Free tier spin-down
- Render free tier services spin down after 15 minutes of inactivity
- First request after spin-down takes ~30–60 seconds to respond
- Upgrade to Starter ($7/mo) for always-on

---

## Notes

- The free tier gives you 750 hours/month of runtime — more than enough for a single service
- Render auto-deploys on every push to your connected branch
- Custom domains are supported (even on free tier with manual DNS config)
