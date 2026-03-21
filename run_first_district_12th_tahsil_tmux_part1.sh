#!/usr/bin/env bash

# Start tmux sessions for the FIRST half of years, each running
# `run_first_district_12th_tahsil.py` (district 1, tehsil 12, headless/VPS).
# Captcha flow is in 1.py: first submit "1", then OCR the real captcha.
# Years covered here: 2026 down to 2005 (22 years, inclusive).

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
  2026 2025 2024 2023 2022 2021 2020 2019 2018 2017
  2016 2015
)

echo "Starting tmux sessions (part 1, d1/t12) for years: ${YEARS[*]}"

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

echo "Part 1 tmux sessions started (or already existed)."
echo "Attach with: tmux attach -t igr_d1t12_2026   # replace 2026 with any year in part 1"
