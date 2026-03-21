#!/usr/bin/env python3
"""
One-time cleanup: remove leftover ~/.chrome_scraper_<year>_<timestamp> directories
left by older 1.py versions that did not delete the profile on browser quit.

Only run when NO scraper/tmux sessions are using Chrome for IGR.

Usage:
  python3 cleanup_chrome_scraper_profiles.py --dry-run
  python3 cleanup_chrome_scraper_profiles.py --yes
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys


def du_sk(path: str) -> int:
    try:
        p = subprocess.run(["du", "-sk", path], capture_output=True, text=True, timeout=3600)
        if p.returncode != 0:
            return 0
        return int(p.stdout.split()[0]) * 1024
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Delete ~/.chrome_scraper_* profile dirs (IGR scraper).")
    ap.add_argument("--dry-run", action="store_true", help="List dirs and sizes only")
    ap.add_argument("--yes", action="store_true", help="Actually delete (required)")
    args = ap.parse_args()

    home = os.path.expanduser("~")
    pattern = os.path.join(home, ".chrome_scraper_*")
    paths = sorted(glob.glob(pattern))
    dirs = [p for p in paths if os.path.isdir(p)]

    total = sum(du_sk(p) for p in dirs)
    print(f"Found {len(dirs)} directories matching {pattern}")
    print(f"Total size (approx): {total / (1024**3):.2f} GB")

    if args.dry_run or not args.yes:
        print("\nSample (up to 15 largest):")
        sized = sorted(((du_sk(p), p) for p in dirs), reverse=True)[:15]
        for sz, p in sized:
            print(f"  {sz / (1024**2):.1f} MB  {p}")
        if not args.dry_run:
            print("\nRe-run with --yes to delete ALL of them (after stopping scrapers).")
        return 0

    removed = 0
    for p in dirs:
        try:
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
        except Exception as e:
            print(f"WARN: {p}: {e}", file=sys.stderr)
    print(f"Removed {removed}/{len(dirs)} directories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
