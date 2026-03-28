#!/usr/bin/env bash
# Part 2: tmux sessions for years 2004 → 1985 (one session per year).
# Each session: cd to this script’s directory, source venv next to it, run script_revised.py.
#
# Venv path: same directory as part2.sh →  <dir>/venv/bin/activate
#
# Usage:
#   ./part2.sh
# Optional env (same as part1.sh):
#   HEADLESS, DISTRICT, TAHSIL

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

y=2004
while [[ "$y" -ge 1985 ]]; do
  launch_one "$y"
  y=$((y - 1))
done

echo "Part 2 done. List: tmux ls | grep igr-"
