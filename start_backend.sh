#!/usr/bin/env bash
set -e

# Write the service account JSON from the environment variable to a file
printenv GOOGLE_CREDENTIALS_JSON > /tmp/service-account-key.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/service-account-key.json

# Reduce glibc memory arena fragmentation — same reasoning as the Streamlit
# start.sh, still relevant on Render's small containers.
export MALLOC_ARENA_MAX=2
export PYTHONMALLOC=malloc

cd "$(dirname "$0")/backend"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
