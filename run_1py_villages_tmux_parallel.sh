#!/usr/bin/env bash

# Run multiple tmux sessions in parallel for 1.py with different village indices.
# Command pattern in each tmux session:
#   python3 1.py <year> <district_index> <tehsil_index> <village_index>
#
# Edit YEAR / DISTRICT_INDEX / TEHSIL_INDEX / VILLAGE_INDICES below as needed.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- User-configurable inputs ---
YEAR="2025"
DISTRICT_INDEX="1"
TEHSIL_INDEX="12"

# Village dropdown index list (1-based). One tmux session is created per village index.
VILLAGE_INDICES=(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 50 51 52 53 54 55 56 57 58 59 60 61 )
# -------------------------------

# Optional: prefer project venv if present
VENV_ACTIVATE=""
if [ -f "${PROJECT_DIR}/venv/bin/activate" ]; then
  VENV_ACTIVATE="${PROJECT_DIR}/venv/bin/activate"
elif [ -f "${PROJECT_DIR}/.venv/bin/activate" ]; then
  VENV_ACTIVATE="${PROJECT_DIR}/.venv/bin/activate"
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed. Please install tmux and try again."
  exit 1
fi

if [ "${#VILLAGE_INDICES[@]}" -eq 0 ]; then
  echo "VILLAGE_INDICES is empty. Please provide at least one village index."
  exit 1
fi

echo "Starting tmux sessions for year=${YEAR}, district=${DISTRICT_INDEX}, tehsil=${TEHSIL_INDEX}"
echo "Village indices: ${VILLAGE_INDICES[*]}"

for VILLAGE_INDEX in "${VILLAGE_INDICES[@]}"; do
  SESSION_NAME="igr_y${YEAR}_d${DISTRICT_INDEX}_t${TEHSIL_INDEX}_v${VILLAGE_INDEX}"

  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session ${SESSION_NAME} already exists, skipping."
    continue
  fi

  echo "Creating tmux session ${SESSION_NAME}..."

  if [ -n "${VENV_ACTIVATE}" ]; then
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && source \"${VENV_ACTIVATE}\" && python3 1.py ${YEAR} ${DISTRICT_INDEX} ${TEHSIL_INDEX} ${VILLAGE_INDEX}"
  else
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && python3 1.py ${YEAR} ${DISTRICT_INDEX} ${TEHSIL_INDEX} ${VILLAGE_INDEX}"
  fi
done

echo "All requested tmux sessions started (or skipped if already existing)."
echo "List sessions: tmux ls"
echo "Attach one session: tmux attach -t igr_y${YEAR}_d${DISTRICT_INDEX}_t${TEHSIL_INDEX}_v<index>"
