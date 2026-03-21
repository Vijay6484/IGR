#!/usr/bin/env python3
"""
Run the IGR scraper in VPS/headless mode by default and only process:
  - 1st district  (dropdown index 1)
  - 12th tehsil   (dropdown index 12)

Villages from the 3rd onward in the dropdown are processed (MIN_VILLAGE_INDEX=3). Override with
  MIN_VILLAGE_INDEX=1 for all villages, or set ONLY_VILLAGE_INDEX for a single village.

Captcha flow (same as 1.py — watch the terminal):
  1) First try: enter "1" and click Search; the script waits until the captcha image URL changes.
  2) Second try: only then OCR reads the NEW image and submits the real value (never OCRs the pre-"1" image).
  After second try, results wait up to 40s before NO_LOAD is decided.
  Index II: one document per click (popup → save → close).
  If NO_LOAD after that: repeat full form, first try = 1 again, second try = CapSolver API.
  If still NO_LOAD: next property number (gut).

Set VPS_MODE=0 before running for a visible browser (local debugging).

Equivalent (default headless):
  VPS_MODE=1 ONLY_DISTRICT_INDEX=1 ONLY_TAHSIL_INDEX=12 MIN_VILLAGE_INDEX=3 python3 1.py <year>
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
    # Headless Chrome on Linux/VPS (same as run_year.py). Override with VPS_MODE=0 for visible UI.
    if not str(env.get("VPS_MODE", "")).strip():
        env["VPS_MODE"] = "1"
    env["ONLY_DISTRICT_INDEX"] = "1"
    env["ONLY_TAHSIL_INDEX"] = "12"
    # Start at 3rd village in the dropdown (skip villages 1 and 2)
    if not str(env.get("MIN_VILLAGE_INDEX", "")).strip():
        env["MIN_VILLAGE_INDEX"] = "1"

    mode = "headless (VPS)" if env.get("VPS_MODE", "").lower() in ("1", "true", "yes") else "visible"
    print(
        f"[run_first_district_12th_tahsil] Year: {year}, {mode}, "
        "ONLY_DISTRICT_INDEX=1, ONLY_TAHSIL_INDEX=12, MIN_VILLAGE_INDEX="
        f"{env.get('MIN_VILLAGE_INDEX', '1')}"
    )
    print(
        "[run_first_district_12th_tahsil] Captcha: (1) First try — enter 1, submit, WAIT until image changes. "
        "(2) Second try — OCR/CapSolver on the NEW image only. NO_LOAD → CapSolver path; still NO_LOAD → next gut."
    )
    rc = subprocess.run([sys.executable, one_py, year], env=env, cwd=script_dir)
    sys.exit(rc.returncode)


if __name__ == "__main__":
    main()
