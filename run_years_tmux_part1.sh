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

echo "Starting part1 tmux sessions for years 2025..2005"

for YEAR in $(seq 2025 -1 2005); do
  SESSION_NAME="igr_y${YEAR}"
  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session ${SESSION_NAME} already exists, skipping."
    continue
  fi

  CMD="cd "${PROJECT_DIR}" && "
  if [ -n "${VENV_ACTIVATE}" ]; then
    CMD+="source "${VENV_ACTIVATE}" && "
  fi
  CMD+="python3 script_revised.py 1 ${YEAR} 1 12"

  tmux new-session -d -s "${SESSION_NAME}" "${CMD}"
  echo "Started ${SESSION_NAME}"
done

echo "Part1 complete. Use: tmux ls"
