#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_ACTIVATE=""
if [ -f "${PROJECT_DIR}/venv/bin/activate" ]; then
  VENV_ACTIVATE="${PROJECT_DIR}/venv/bin/activate"
elif [ -f "${PROJECT_DIR}/.venv/bin/activate" ]; then
  VENV_ACTIVATE="${PROJECT_DIR}/.venv/bin/activate"
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed. Please install tmux and retry."
  exit 1
fi

echo "Starting part2 tmux sessions for years 2004..1985"
LOG_DIR="${PROJECT_DIR}/tmux_logs"
mkdir -p "${LOG_DIR}"

for YEAR in $(seq 2004 -1 1985); do
  SESSION_NAME="igr_y${YEAR}"
  LOG_FILE="${LOG_DIR}/${SESSION_NAME}.log"
  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session ${SESSION_NAME} already exists, skipping."
    continue
  fi

  if [ -n "${VENV_ACTIVATE}" ]; then
    tmux new-session -d -s "${SESSION_NAME}" \
      "bash -lc 'cd \"${PROJECT_DIR}\" && source \"${VENV_ACTIVATE}\" && python3 script_revised.py 1 ${YEAR} 1 12 >> \"${LOG_FILE}\" 2>&1 || { echo FAILED_YEAR_${YEAR}; exec bash; }'"
  else
    tmux new-session -d -s "${SESSION_NAME}" \
      "bash -lc 'cd \"${PROJECT_DIR}\" && python3 script_revised.py 1 ${YEAR} 1 12 >> \"${LOG_FILE}\" 2>&1 || { echo FAILED_YEAR_${YEAR}; exec bash; }'"
  fi
  echo "Started ${SESSION_NAME}"
done

echo "Part2 complete. Use: tmux ls"
echo "Logs: ${LOG_DIR}"
