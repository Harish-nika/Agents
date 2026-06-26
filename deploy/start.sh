#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

pkill -f "${ROOT_DIR}/venv/bin/uvicorn app.api.main:app" 2>/dev/null || true
sleep 1

API_PORT="${API_PORT:-8512}"
mkdir -p "$ROOT_DIR/data"
echo "$API_PORT" > "$ROOT_DIR/data/.port"

OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
for i in {1..15}; do
  curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1 && break
  sleep 2
done

# Build frontend if dist missing or src newer
if [[ ! -d "$ROOT_DIR/frontend/dist" ]] && [[ -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Building React frontend..."
  (cd "$ROOT_DIR/frontend" && npm run build)
fi

source "$ROOT_DIR/venv/bin/activate"
export PYTHONPATH="$ROOT_DIR"

echo "Starting Recruiting Agent API + React on port $API_PORT"
exec uvicorn app.api.main:app --host 0.0.0.0 --port "$API_PORT"
