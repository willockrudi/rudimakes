#!/usr/bin/env bash
set -euo pipefail

WORKDIR="/home/rudi/Documents/rudimakes"
PYTHON_BIN="/home/rudi/Documents/rudimakes/.venv/bin/python"
LOG_FILE="/tmp/rudimakes-admin.log"
HOST="127.0.0.1"
PORT="8081"

cd "$WORKDIR"

if ! pgrep -f "manage.py web-ui ${HOST} ${PORT}" >/dev/null 2>&1; then
  nohup "$PYTHON_BIN" "$WORKDIR/manage.py" web-ui "$HOST" "$PORT" >"$LOG_FILE" 2>&1 &
  sleep 1
fi

xdg-open "http://${HOST}:${PORT}/" >/dev/null 2>&1 &
