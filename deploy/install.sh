#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Fact Entry Recruiting Agent — Install ==="

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example — please update APP_PASSWORD"
fi

if [[ ! -d "$ROOT_DIR/venv" ]]; then
  python3 -m venv "$ROOT_DIR/venv"
fi

source "$ROOT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements.txt"

export PYTHONPATH="$ROOT_DIR"
python -c "from app.db.models import init_db; init_db(); print('Database initialized')"

chmod +x "$ROOT_DIR/deploy/start.sh"
chmod +x "$ROOT_DIR/scripts/pull_models.sh"

echo "Pulling Ollama models..."
bash "$ROOT_DIR/scripts/pull_models.sh" || echo "Warning: model pull failed, ensure Ollama is running"

SERVICE_FILE="/etc/systemd/system/fact-entry-recruiting.service"
if [[ -w "/etc/systemd/system" ]] || sudo -n true 2>/dev/null; then
  sudo cp "$ROOT_DIR/deploy/fact-entry-recruiting.service" "$SERVICE_FILE"
  sudo systemctl daemon-reload
  sudo systemctl enable fact-entry-recruiting
  sudo systemctl restart fact-entry-recruiting
  sleep 3
  sudo systemctl status fact-entry-recruiting --no-pager || true
  PORT=$(cat "$ROOT_DIR/data/.port" 2>/dev/null || echo "8510")
  echo ""
  echo "=== Installation complete ==="
  echo "Access: http://192.168.0.162:${PORT}"
else
  echo ""
  echo "=== App installed locally (systemd requires sudo) ==="
  echo "To enable auto-start, run:"
  echo "  sudo cp deploy/fact-entry-recruiting.service /etc/systemd/system/"
  echo "  sudo systemctl daemon-reload && sudo systemctl enable --now fact-entry-recruiting"
  echo ""
  echo "Or start manually: ./deploy/start.sh"
fi
