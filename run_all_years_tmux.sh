#!/usr/bin/env bash

# Start tmux sessions, each running `run_year.py` for a specific year.
# Years covered: 2026 down to 1985 (inclusive).

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

# Adjust this list if you want a different year range.
YEARS=(
  2026 2025 2024 2023 2022 2021 2020 2019 2018 2017
  2016 2015 2014 2013 2012 2011 2010 2009 2008 2007
  2006 2005 2004 2003 2002 2001 2000 1999 1998 1997
  1996 1995 1994 1993 1992 1991 1990 1989 1988 1987
  1986 1985
)

echo "Starting tmux sessions for years: ${YEARS[*]}"

for YEAR in "${YEARS[@]}"; do
  SESSION_NAME="igr_${YEAR}"

  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session ${SESSION_NAME} already exists, skipping."
    continue
  fi

  echo "Creating tmux session ${SESSION_NAME} for year ${YEAR}..."

  if [ -n "${VENV_ACTIVATE}" ]; then
    # Activate virtualenv then run the script
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && source \"${VENV_ACTIVATE}\" && python run_year.py ${YEAR}"
  else
    # Fallback: no venv detected, use system python
    tmux new-session -d -s "${SESSION_NAME}" "cd \"${PROJECT_DIR}\" && python3 run_year.py ${YEAR}"
  fi
done

echo "All requested tmux sessions started (or already existed)."
echo "Attach to a session with: tmux attach -t igr_2026   # replace 2026 with any year"

