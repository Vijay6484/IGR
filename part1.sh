#!/usr/bin/env bash
# Part 1: tmux sessions for years 2025 → 2005 (one session per year).
# Each session: cd to this script’s directory, source venv next to it, run script_revised.py.
#
# Venv path: same directory as part1.sh →  <dir>/venv/bin/activate
#
# Usage:
#   ./part1.sh
# Optional env:
#   HEADLESS   — 1 or 0 (default: 1)
#   DISTRICT   — district index (default: 1)
#   TAHSIL     — tahsil index (default: 1)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# venv is in the same folder as part1.sh / part2.sh
VENV_ROOT="$SCRIPT_DIR/venv"
ACTIVATE="$VENV_ROOT/bin/activate"
if [[ ! -f "$ACTIVATE" ]]; then
  echo "Expected venv at: $VENV_ROOT" >&2
  echo "Create it in the same directory as this script, e.g.: python3 -m venv \"$VENV_ROOT\"" >&2
  exit 1
fi

HEADLESS="${HEADLESS:-1}"
DISTRICT="${DISTRICT:-1}"
TAHSIL="${TAHSIL:-12}"

launch_one() {
  local year="$1"
  local sname="igr-${year}"
  if tmux has-session -t "$sname" 2>/dev/null; then
    echo "Skip: tmux session '$sname' already exists (tmux kill-session -t $sname to replace)"
    return
  fi
  tmux new-session -d -s "$sname" bash -lc "
    cd '$SCRIPT_DIR'
    source '$ACTIVATE'
    python3 script_revised.py $HEADLESS $year $DISTRICT $TAHSIL
    st=\$?
    echo \"[igr-$year] script finished (exit \$st)\"
    exec bash -l
  "
  echo "Started tmux session: $sname  (year=$year)"
}

y=2025
while [[ "$y" -ge 2005 ]]; do
  launch_one "$y"
  y=$((y - 1))
done

echo "Part 1 done. List: tmux ls | grep igr-"
