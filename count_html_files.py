"""
Count the number of downloaded HTML files under scraper_output.

Usage:
    python3 count_html_files.py
"""

import os
from pathlib import Path


def count_html_files(root: Path) -> int:
    count = 0
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".html"):
                count += 1
    return count


def main() -> None:
    base = Path(__file__).resolve().parent
    scraper_output = base / "scraper_output"

    if not scraper_output.exists():
        print(f"No scraper_output directory found at: {scraper_output}")
        return

    total = count_html_files(scraper_output)
    print(f"Total HTML files in {scraper_output}: {total}")


if __name__ == "__main__":
    main()

