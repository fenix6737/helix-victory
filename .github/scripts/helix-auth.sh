#!/usr/bin/env bash
# Fly API ログイン（リトライ付き）— 全スケジュールワークフロー共通
set -euo pipefail

: "${HELIX_API_URL:?HELIX_API_URL required}"
: "${ADMIN_USERNAME:?ADMIN_USERNAME required}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD required}"

HELIX_API_URL="${HELIX_API_URL%/}"
ATTEMPTS="${HELIX_AUTH_ATTEMPTS:-5}"
DELAY="${HELIX_AUTH_DELAY_SEC:-3}"

for i in $(seq 1 "$ATTEMPTS"); do
  body=$(curl -sS -w "\n%{http_code}" -X POST "$HELIX_API_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" || true)
  http=$(echo "$body" | tail -n1)
  json=$(echo "$body" | sed '$d')
  if [ "$http" = "200" ] && [ -n "$json" ]; then
    export HELIX_TOKEN
    HELIX_TOKEN=$(echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
    if [ -n "${GITHUB_ENV:-}" ]; then
      echo "HELIX_TOKEN=$HELIX_TOKEN" >> "$GITHUB_ENV"
    fi
    echo "Login OK"
    exit 0
  fi
  echo "Login attempt $i/$ATTEMPTS failed HTTP ${http:-?}"
  if [ "$http" = "401" ] || [ "$http" = "403" ]; then
    echo "Hint: run scripts/sync-github-secrets.ps1 after Fly deploy"
    if [ "$i" -eq "$ATTEMPTS" ]; then
      exit 1
    fi
  fi
  if [ "$i" -lt "$ATTEMPTS" ]; then
    sleep "$((DELAY * i))"
  fi
done
echo "Login failed after $ATTEMPTS attempts"
exit 1
