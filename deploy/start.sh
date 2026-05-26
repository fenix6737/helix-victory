#!/bin/sh
set -e

export API_URL_INTERNAL="${API_URL_INTERNAL:-http://127.0.0.1:8000}"
export HELIX_COOKIE_SECURE="${HELIX_COOKIE_SECURE:-1}"

cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

cd /app/frontend
export HOSTNAME=0.0.0.0
export PORT="${PORT:-8080}"
node server.js &
WEB_PID=$!

trap 'kill $API_PID $WEB_PID 2>/dev/null' TERM INT

wait $WEB_PID
