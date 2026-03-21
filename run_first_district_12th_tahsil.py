#!/usr/bin/env python3
"""
Run the IGR scraper in VPS/headless mode by default and only process:
  - 1st district  (dropdown index 1)
  - 12th tehsil   (dropdown index 12)

All villages in that tehsil are processed unless ONLY_VILLAGE_INDEX is set in the environment.

Captcha (handled inside 1.py — no extra flags needed):
  - First captcha: always submit "1" (submit_dummy_captcha).
  - Second step: wait for the real image, then OCR (Tesseract/Paddle via CAPTCHA_SOLVER) and submit.
  - If NO_LOAD after OCR: form reload, again first=1 then CapSolver (captcha_config) for the second captcha.
  - If still NO_LOAD after CapSolver: skip to the next property number (gut).
  - Terminal: lines tagged [TRACK] show OCR → CapSolver flow (no extra log-file entries for tracking).

Set VPS_MODE=0 before running for a visible browser (local debugging).

Equivalent (default headless):
  VPS_MODE=1 ONLY_DISTRICT_INDEX=1 ONLY_TAHSIL_INDEX=12 python3 1.py <year>
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

    mode = "headless (VPS)" if env.get("VPS_MODE", "").lower() in ("1", "true", "yes") else "visible"
    print(
        f"[run_first_district_12th_tahsil] Year: {year}, {mode}, "
        "ONLY_DISTRICT_INDEX=1, ONLY_TAHSIL_INDEX=12"
    )
    print("[run_first_district_12th_tahsil] Captcha: first=1, then OCR; NO_LOAD→CapSolver; still NO_LOAD→next gut")
    rc = subprocess.run([sys.executable, one_py, year], env=env, cwd=script_dir)
    sys.exit(rc.returncode)


if __name__ == "__main__":
    main()
