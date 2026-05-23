#!/usr/bin/env bash
#
# demo_down.sh — stop everything started by demo_up.sh.
# Stops the web server, the API, the watchdog, and the Docker compose stack
# (Postgres + Redis). Leaves Docker Desktop itself running and KEEPS the pgdata
# volume (your seeded catalog is preserved).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.demo"
FROM_WD=0
[[ "${1:-}" == "--from-watchdog" ]] && FROM_WD=1

kill_pidfile() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  local pid; pid="$(cat "$f" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  rm -f "$f"
}

kill_port() {
  local pids; pids="$(lsof -ti tcp:"$1" 2>/dev/null || true)"
  [[ -n "$pids" ]] && kill $pids 2>/dev/null || true
}

# Stop the watchdog first, unless it's the one calling us (it exits on its own).
[[ "$FROM_WD" == 0 ]] && kill_pidfile "$RUN/watchdog.pid"

# Web + API: kill by pidfile and by port (catches npm -> next child trees).
kill_pidfile "$RUN/web.pid"; kill_port 3012
kill_pidfile "$RUN/api.pid"; kill_port 8011

# Docker services (keep the volume; `down` without -v preserves pgdata).
( cd "$ROOT" && docker compose down ) >/dev/null 2>&1 || true

echo "FitGraph demo stopped."
