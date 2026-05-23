#!/usr/bin/env bash
#
# demo_up.sh — bring up FitGraph for a STABLE local demo on a 16 GB Mac.
#
# Why this exists: `next dev` (Next.js 16 + Turbopack) compiles the homepage
# route on-demand the moment a browser hits it, and that dev-mode compile
# balloons system memory to ~8 GB in seconds — enough to hard-freeze a 16 GB
# Mac (compressor/swap thrash -> UI hang -> power-button reset). The identical
# page served as a PRODUCTION build uses ~1 GB. So this script serves a prod
# build (`next build` + `next start`) instead of the dev server, and runs a
# memory-pressure watchdog that stops the stack before the machine can hang.
#
# Usage:
#   scripts/demo_up.sh            # reuse existing web/.next build
#   scripts/demo_up.sh --rebuild  # force a fresh `next build` first
# Stop everything: scripts/demo_down.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$ROOT/web"
RUN="$ROOT/.demo"
API_PORT=8011
WEB_PORT=3012
REBUILD=0
[[ "${1:-}" == "--rebuild" ]] && REBUILD=1

mkdir -p "$RUN"
log()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }

[[ -x "$ROOT/.venv/bin/uvicorn" ]] || { echo "Missing $ROOT/.venv (run the venv setup first)."; exit 1; }

# 1. Docker daemon ----------------------------------------------------------
if ! docker info >/dev/null 2>&1; then
  log "Starting Docker Desktop…"
  open -a Docker
  for _ in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 2
  done
  docker info >/dev/null 2>&1 || { echo "Docker did not come up in time."; exit 1; }
fi

# 2. Postgres + Redis (Docker VM is capped to 4 GB in Docker Desktop) --------
log "Starting Postgres + Redis (docker compose up -d)…"
( cd "$ROOT" && docker compose up -d )
log "Waiting for Postgres health…"
for _ in $(seq 1 30); do
  health="$(cd "$ROOT" && docker compose ps --format '{{.Health}}' db 2>/dev/null || true)"
  [[ "$health" == healthy* ]] && break
  sleep 2
done

# 3. API (uvicorn) on :8011 — must run from repo root for relative data/ paths
if curl -fsS -m 2 "http://localhost:$API_PORT/healthz" >/dev/null 2>&1; then
  warn "API already up on :$API_PORT — reusing it."
else
  log "Starting API (uvicorn) on :${API_PORT}…"
  cd "$ROOT"
  nohup .venv/bin/uvicorn fitgraph.api.main:create_app --factory --port "$API_PORT" \
    >"$RUN/api.log" 2>&1 &
  echo $! >"$RUN/api.pid"
  log "Waiting for API /healthz…"
  for _ in $(seq 1 45); do
    if curl -fsS -m 2 "http://localhost:$API_PORT/healthz" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  curl -fsS -m 2 "http://localhost:$API_PORT/healthz" >/dev/null 2>&1 \
    || warn "API not healthy yet — check $RUN/api.log"
fi

# 4. Web — PRODUCTION build + next start (NOT next dev) ----------------------
if [[ "$REBUILD" == 1 || ! -d "$WEB/.next" ]]; then
  log "Building web (next build)…"
  ( cd "$WEB" && npm run build )
else
  log "Reusing existing web/.next (pass --rebuild for a fresh build)."
fi
log "Starting web (next start) on :${WEB_PORT}…"
cd "$WEB"
nohup npm run start -- -p "$WEB_PORT" >"$RUN/web.log" 2>&1 &
echo $! >"$RUN/web.pid"
for _ in $(seq 1 30); do
  if curl -fsS -m 2 "http://localhost:$WEB_PORT/" >/dev/null 2>&1; then break; fi
  sleep 1
done

# 5. Memory-pressure watchdog seatbelt --------------------------------------
log "Starting memory watchdog…"
nohup bash "$ROOT/scripts/_demo_watchdog.sh" >"$RUN/watchdog.log" 2>&1 &
echo $! >"$RUN/watchdog.pid"

cat <<EOF

✅ FitGraph demo is up (production mode — freeze-safe)
   Web : http://localhost:$WEB_PORT
   API : http://localhost:$API_PORT/healthz
   Logs: $RUN/{api,web,watchdog}.log
   Stop: scripts/demo_down.sh
EOF
