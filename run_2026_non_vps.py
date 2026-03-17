#!/usr/bin/env python3
"""
Run the IGR scraper for year 2026 only, in non-VPS mode (visible Brave window),
and restrict processing to ONLY the 15th village (1-based index) within each tahsil.

Effectively:
  VPS_MODE=0
  ONLY_VILLAGE_INDEX=15
  python 1.py 2026
"""
import os
import sys
import subprocess


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    one_py = os.path.join(script_dir, "1.py")
    if not os.path.isfile(one_py):
        print(f"Not found: {one_py}", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()
    # Force non-VPS mode so browser is visible and sounds play
    env["VPS_MODE"] = "0"
    # Only process the 15th village (1-based index) per tahsil
    env["ONLY_VILLAGE_INDEX"] = "15"

    print("[run_2026_non_vps] Year: 2026, mode: non-VPS (visible browser), ONLY_VILLAGE_INDEX=15")
    rc = subprocess.run([sys.executable, one_py, "2026"], env=env, cwd=script_dir)
    sys.exit(rc.returncode)


if __name__ == "__main__":
    main()

