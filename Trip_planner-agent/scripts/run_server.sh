#!/usr/bin/env bash
# Run with the same Python that has google-adk (avoid bare `uvicorn` on another Python).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
exec python3 -m uvicorn trip_planner.api.app:app --host "${TRIP_PLANNER_HOST:-0.0.0.0}" --port "${TRIP_PLANNER_PORT:-8080}" "$@"
