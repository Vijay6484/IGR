#!/usr/bin/env bash

# Start tmux sessions for the SECOND half of years, each running `run_year.py`.
# Years covered here: 2005 down to 1985 (inclusive).

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
  2005 2004 2003 2002 2001 2000 1999 1998 1997
  1996 1995 1994 1993 1992 1991 1990 1989 1988 1987
  1986 1985
)

echo "Starting tmux sessions (part 2) for years: ${YEARS[*]}"

for YEAR in "${YEARS[@]}"; do
  SESSION_NAME="igr_${YEAR}"

  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session ${SESSION_NAME} already exists, skipping."
    continue
  fi

  echo "Creating tmux session ${SESSION_NAME} for year ${YEAR}..."

  if [ -n "${VENV_ACTIVATE}" ]; then
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && source \"${VENV_ACTIVATE}\" && python3 run_year.py ${YEAR}"
  else
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && python3 run_year.py ${YEAR}"
  fi
done

echo "Part 2 tmux sessions started (or already existed)."
echo "Attach with: tmux attach -t igr_2005   # replace 2005 with any year in part 2"

