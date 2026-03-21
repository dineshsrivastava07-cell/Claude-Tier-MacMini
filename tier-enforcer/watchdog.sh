#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  DSR AI-LAB — TIER ENFORCER WATCHDOG
#  File: ~/tier-enforcer-mcp/watchdog.sh
#  Keeps tier-enforcer alive permanently.
#  Start: bash ~/tier-enforcer-mcp/watchdog.sh &
#  Stop:  pkill -f watchdog.sh
# ═══════════════════════════════════════════════════════════════════

SERVER="/Users/dsr-ai-lab/tier-enforcer-mcp/server.py"
LOG="/Users/dsr-ai-lab/.tier-enforcer/watchdog.log"
PID_FILE="/Users/dsr-ai-lab/.tier-enforcer/server.pid"
RESTART_DELAY=3   # seconds between restart attempts

mkdir -p "$(dirname "$LOG")"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

log "=== Watchdog started (PID $$) ==="

while true; do
  # Check if server is running
  if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
      # Still running — sleep and check again
      sleep 5
      continue
    fi
  fi

  # Server not running — start it
  log "Starting tier-enforcer server..."
  python3 "$SERVER" >> "$LOG" 2>&1 &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$PID_FILE"
  log "Server started with PID $SERVER_PID"

  # Wait for it to die
  wait "$SERVER_PID"
  EXIT_CODE=$?
  log "Server exited with code $EXIT_CODE — restarting in ${RESTART_DELAY}s"
  sleep "$RESTART_DELAY"
done
