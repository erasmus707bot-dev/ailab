#!/usr/bin/env bash
# Desktop launcher: restarts the AI Lab (stops a running copy, starts fresh), then opens it.
# AILAB_NO_RESTART=1 = old behaviour (only start if not running).
# Runs on 127.0.0.1 only. Log: ~/.config/ailab/serve.log
set -u
# Desktop icons start with a bare PATH — add the user installs so the Lab finds srt and node.
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
PORT="${AILAB_PORT:-8850}"
URL="http://127.0.0.1:${PORT}/"
LOG="${HOME}/.config/ailab/serve.log"
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
up() { curl -fsS -m 2 "${URL}api/state" >/dev/null 2>&1; }
if up && [ -z "${AILAB_NO_RESTART:-}" ]; then
  echo "--- $(date '+%F %T') launcher restart" >>"$LOG"
  pkill -u "$(id -u)" -f "python3 -m ailab serve" 2>/dev/null
  for _ in $(seq 1 20); do up || break; sleep 0.3; done
fi
if ! up; then
  mkdir -p "$(dirname "$LOG")"
  echo "--- $(date '+%F %T') launcher start" >>"$LOG"
  setsid nohup python3 -m ailab serve --port "$PORT" </dev/null >>"$LOG" 2>&1 &
  for _ in $(seq 1 25); do up && break; sleep 0.3; done
fi
if up; then
  xdg-open "$URL" >/dev/null 2>&1 &
else
  notify-send "🧪 AI Lab" "It didn't start — see ${LOG}" 2>/dev/null || echo "AI Lab didn't start — see ${LOG}" >&2
  exit 1
fi
