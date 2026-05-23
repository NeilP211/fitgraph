#!/usr/bin/env bash
#
# _demo_watchdog.sh. memory-pressure seatbelt for the FitGraph demo.
#
# Polls the macOS kernel memory-pressure level and swap usage. If the machine
# starts to genuinely struggle, it gracefully stops the demo BEFORE the UI can
# hang, and posts a macOS notification so you know why. Started automatically by
# demo_up.sh; not meant to be run directly.
#
# Trip conditions (any one):
#   - kernel pressure CRITICAL (level 4)        -> immediate stop
#   - kernel pressure WARNING (level 2) for ~12s -> stop
#   - swap used > 4096 MB                        -> stop
# These are tuned to ignore brief, harmless spikes but catch a real slide
# toward a freeze. To disable the seatbelt, just don't run demo_up.sh's
# watchdog (or `kill $(cat .demo/watchdog.pid)`).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.demo"
WARN_STREAK=0
POLL=3
WARN_STREAK_LIMIT=4   # 4 * 3s = ~12s sustained warning
SWAP_LIMIT_MB=4096

trap 'rm -f "$RUN/watchdog.pid"' EXIT

while true; do
  sleep "$POLL"
  level="$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null || echo 1)"
  swap="$(sysctl -n vm.swapusage 2>/dev/null | sed -nE 's/.*used = ([0-9.]+)M.*/\1/p')"
  swap="${swap%.*}"; swap="${swap:-0}"

  danger=0; reason=""
  if [[ "$level" -ge 4 ]]; then danger=1; reason="kernel memory pressure CRITICAL"; fi
  if [[ "$level" -ge 2 ]]; then WARN_STREAK=$((WARN_STREAK + 1)); else WARN_STREAK=0; fi
  if [[ "$WARN_STREAK" -ge "$WARN_STREAK_LIMIT" ]]; then danger=1; reason="sustained memory-pressure warning (~$((WARN_STREAK*POLL))s)"; fi
  if [[ "$swap" -gt "$SWAP_LIMIT_MB" ]]; then danger=1; reason="swap usage ${swap} MB"; fi

  if [[ "$danger" == 1 ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG TRIPPED: $reason. stopping demo to prevent a freeze"
    osascript -e "display notification \"$reason. Demo stopped to prevent a freeze.\" with title \"FitGraph watchdog\"" 2>/dev/null || true
    bash "$ROOT/scripts/demo_down.sh" --from-watchdog || true
    exit 0
  fi
done
