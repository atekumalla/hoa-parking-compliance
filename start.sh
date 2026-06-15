#!/usr/bin/env bash

# Write the service account JSON from the environment variable to a file
# Using printf to preserve special characters (like \n in private keys)
printenv GOOGLE_CREDENTIALS_JSON > /tmp/service-account-key.json

# Export the path so the app can find it
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/service-account-key.json

# Run Streamlit on Render's expected port
streamlit run app.py \
  --server.port=${PORT:-8501} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
