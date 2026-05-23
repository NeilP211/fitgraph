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
#   - kernel pressure CRITICAL (level 4) sustained ~9s -> stop
#   - swap used > 7168 MB                              -> stop
# Deliberately relaxed: the demo serves a production build (~1 GB) that does not
# balloon, so routine WARNING pressure from other apps (Chrome, etc.) is left
# alone. Only a genuine slide toward a hang trips it. To disable the seatbelt,
# run `kill $(cat .demo/watchdog.pid)`.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.demo"
CRIT_STREAK=0
POLL=3
CRIT_STREAK_LIMIT=3   # 3 * 3s = ~9s sustained CRITICAL pressure
SWAP_LIMIT_MB=7168

trap 'rm -f "$RUN/watchdog.pid"' EXIT

while true; do
  sleep "$POLL"
  level="$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null || echo 1)"
  swap="$(sysctl -n vm.swapusage 2>/dev/null | sed -nE 's/.*used = ([0-9.]+)M.*/\1/p')"
  swap="${swap%.*}"; swap="${swap:-0}"

  danger=0; reason=""
  if [[ "$level" -ge 4 ]]; then CRIT_STREAK=$((CRIT_STREAK + 1)); else CRIT_STREAK=0; fi
  if [[ "$CRIT_STREAK" -ge "$CRIT_STREAK_LIMIT" ]]; then danger=1; reason="sustained CRITICAL memory pressure (~$((CRIT_STREAK*POLL))s)"; fi
  if [[ "$swap" -gt "$SWAP_LIMIT_MB" ]]; then danger=1; reason="swap usage ${swap} MB"; fi

  if [[ "$danger" == 1 ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG TRIPPED: $reason. stopping demo to prevent a freeze"
    osascript -e "display notification \"$reason. Demo stopped to prevent a freeze.\" with title \"FitGraph watchdog\"" 2>/dev/null || true
    bash "$ROOT/scripts/demo_down.sh" --from-watchdog || true
    exit 0
  fi
done
