#!/usr/bin/env bash

# Start tmux sessions for the SECOND half of years, each running
# `run_first_district_12th_tahsil.py` (district 1, tehsil 12, headless/VPS).
# Years covered here: 2004 down to 1984 (21 years, inclusive).

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect virtual environment (prefer PROJECT_DIR/venv, then PROJECT_DIR/.venv)
VENV_ACTIVATE=""
if [ -f "${PROJECT_DIR}/venv/bin/activate" ]; then
  VENV_ACTIVATE="${PROJECT_DIR}/venv/bin/activate"
elif [ -f "${PROJECT_DIR}/.venv/bin/activate" ]; then
  VENV_ACTIVATE="${PROJECT_DIR}/.venv/bin/activate"
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed. Please install tmux on the VPS and try again."
  exit 1
fi

YEARS=(
  2004 2003 2002 2001 2000 1999 1998 1997
  1996 1995 1994 1993 1992 1991 1990 1989 1988 1987
  1986 1985 1984
)

echo "Starting tmux sessions (part 2, d1/t12) for years: ${YEARS[*]}"

for YEAR in "${YEARS[@]}"; do
  SESSION_NAME="igr_d1t12_${YEAR}"

  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session ${SESSION_NAME} already exists, skipping."
    continue
  fi

  echo "Creating tmux session ${SESSION_NAME} for year ${YEAR}..."

  if [ -n "${VENV_ACTIVATE}" ]; then
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && source \"${VENV_ACTIVATE}\" && python3 run_first_district_12th_tahsil.py ${YEAR}"
  else
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && python3 run_first_district_12th_tahsil.py ${YEAR}"
  fi
done

echo "Part 2 tmux sessions started (or already existed)."
echo "Attach with: tmux attach -t igr_d1t12_2004   # replace 2004 with any year in part 2"
