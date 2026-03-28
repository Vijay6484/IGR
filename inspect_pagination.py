#!/usr/bin/env python3
"""
Capture how the IGR site renders RegistrationGrid pagination in HTML, including
ellipsis controls that advance to the next block of ~10 page numbers.

Uses the same argv convention as script_revised.py (those values are read when
script_revised is imported):

  python inspect_pagination.py <headless> <year> <district> <tahsil> [property_no] [village_index]

Artifacts are written under output/pagination_probe/<timestamp>/:
  *_RegistrationGrid_outer.html   — full grid markup
  *_pagination_summary.json       — parsed links, ellipsis-like nodes, pager-looking tables
  *_pagination_links.txt          — short human-readable link list

Examples:
  python inspect_pagination.py 0 2020 1 1 0 1
  python inspect_pagination.py 0 2020 1 1 4521 3

Use a property_no that returns more than 10 pages so ellipsis and Page$11 appear.
Headed mode (0) helps if captcha or layout differs from headless.
"""

from __future__ import annotations

import os
import sys
import time

if __name__ == "__main__" and len(sys.argv) < 5:
    print(__doc__)
    sys.exit(2)

import script_revised as igr


def main() -> None:
    prop = int(sys.argv[5]) if len(sys.argv) > 5 else igr.PROPERTY_START
    village = int(sys.argv[6]) if len(sys.argv) > 6 else 1
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join("output", "pagination_probe", stamp)
    os.makedirs(out, exist_ok=True)
    print(f"[inspect_pagination] property={prop} village_index={village}")
    print(f"[inspect_pagination] writing under {out}")
    igr.run_selenium_for_property(prop, village, pagination_probe_out_dir=out)
    print(f"[inspect_pagination] done. Inspect HTML and JSON in:\n  {out}")


if __name__ == "__main__":
    main()
