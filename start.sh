#!/usr/bin/env bash

# Write the service account JSON from the environment variable to a file
# Using printf to preserve special characters (like \n in private keys)
printenv GOOGLE_CREDENTIALS_JSON > /tmp/service-account-key.json

# Export the path so the app can find it
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/service-account-key.json

# Reduce glibc memory arena fragmentation — critical on 512MB container
# Without this, glibc creates up to 8×CPU arenas, each holding freed-but-unreturned pages
export MALLOC_ARENA_MAX=2
export PYTHONMALLOC=malloc

# Run Streamlit on Render's expected port
streamlit run app.py \
  --server.port=${PORT:-8501} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.maxUploadSize=10 \
  --server.maxMessageSize=50 \
  --browser.gatherUsageStats=false
