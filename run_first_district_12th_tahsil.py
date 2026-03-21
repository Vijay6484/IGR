#!/usr/bin/env python3
"""
Run the IGR scraper in non-VPS mode (visible browser) and only process:
  - 1st district  (dropdown index 1)
  - 12th tehsil   (dropdown index 12)

All villages in that tehsil are processed unless ONLY_VILLAGE_INDEX is set in the environment.

Equivalent:
  VPS_MODE=0 ONLY_DISTRICT_INDEX=1 ONLY_TAHSIL_INDEX=12 python3 1.py <year>
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

    year = sys.argv[1] if len(sys.argv) > 1 else "2026"

    env = os.environ.copy()
    env["VPS_MODE"] = "0"
    env["ONLY_DISTRICT_INDEX"] = "1"
    env["ONLY_TAHSIL_INDEX"] = "12"

    print(
        f"[run_first_district_12th_tahsil] Year: {year}, "
        "non-VPS, ONLY_DISTRICT_INDEX=1, ONLY_TAHSIL_INDEX=12"
    )
    rc = subprocess.run([sys.executable, one_py, year], env=env, cwd=script_dir)
    sys.exit(rc.returncode)


if __name__ == "__main__":
    main()
