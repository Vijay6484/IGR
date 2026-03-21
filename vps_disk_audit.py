#!/usr/bin/env python3
"""
Disk audit for IGR scraper / VPS troubleshooting.

Run on the VPS (same user as the scraper) and paste the full output:

    python3 vps_disk_audit.py

Optional:

    python3 vps_disk_audit.py --project /path/to/IGR
    python3 vps_disk_audit.py --top 25
    python3 vps_disk_audit.py --full-home   # slow: du every top-level dir in $HOME

Output is plain text so you can copy it into a chat.
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def _human(n: int) -> str:
    if n < 0:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{int(n)} B"


def du_bytes(path: str) -> int | None:
    """
    Total size of path using `du` when available (fast on large trees).
    Returns None if path missing or du failed.
    """
    if not os.path.exists(path):
        return None
    # Prefer GNU-style -sb (bytes); fall back to -sk (KiB) for BSD/macOS.
    for args in (["du", "-sb", path], ["du", "-sk", path]):
        try:
            p = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if p.returncode != 0 or not p.stdout.strip():
                continue
            first = p.stdout.strip().splitlines()[0].split()
            n = int(first[0])
            if args[-2] == "-sk":
                n *= 1024
            return n
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            continue
    # Slow fallback
    try:
        total = 0
        for root, _dirs, files in os.walk(path, followlinks=False):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total
    except OSError:
        return None


def top_subdirs(root: str, limit: int) -> list[tuple[str, int]]:
    """Largest immediate children of root by du_bytes."""
    if not os.path.isdir(root):
        return []
    out: list[tuple[str, int]] = []
    try:
        for name in os.listdir(root):
            p = os.path.join(root, name)
            # Skip special / virtual if any
            if os.path.islink(p) and not os.path.isdir(p):
                continue
            sz = du_bytes(p)
            if sz is not None:
                out.append((p, sz))
    except OSError:
        return []
    out.sort(key=lambda x: x[1], reverse=True)
    return out[:limit]


def glob_sizes(pattern: str) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for p in sorted(glob.glob(pattern)):
        if os.path.isdir(p):
            sz = du_bytes(p)
            if sz is not None:
                rows.append((p, sz))
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Disk audit for scraper VPS (copy full output).")
    ap.add_argument(
        "--project",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="IGR project directory (default: this script's folder)",
    )
    ap.add_argument("--top", type=int, default=20, help="How many largest subdirs to list per section")
    ap.add_argument(
        "--full-home",
        action="store_true",
        help="Measure every top-level item in $HOME (slow on large desktops; default skips this)",
    )
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    home = os.path.expanduser("~")

    print("IGR / VPS DISK AUDIT REPORT")
    print(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    print(f"Host: {platform.node()}")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {sys.version.split()[0]}")
    print(f"USER: {os.environ.get('USER', '?')}")
    print(f"HOME: {home}")
    print(f"PWD (at launch): {os.getcwd()}")
    print(f"PROJECT (--project): {project}")

    # Root filesystem
    try:
        u = shutil.disk_usage("/")
        print()
        print("=== FILESYSTEM / (root) ===")
        print(f"  total: {_human(u.total)} ({u.total:,} bytes)")
        print(f"  used:  {_human(u.used)} ({u.used:,} bytes)")
        print(f"  free:  {_human(u.free)} ({u.free:,} bytes)")
    except OSError as e:
        print(f"\n=== FILESYSTEM / ===\n  (could not read: {e})")

    # Env hints (no secrets)
    print()
    print("=== RELEVANT ENV (non-secret hints) ===")
    for key in (
        "DRIVE_ONLY",
        "GDRIVE_UPLOAD_ENABLED",
        "VPS_MODE",
        "HEADLESS_MODE",
        "TMPDIR",
        "TEMP",
        "TMP",
        "XDG_CACHE_HOME",
    ):
        v = os.environ.get(key)
        if v is not None:
            print(f"  {key}={v!r}")
        else:
            print(f"  {key}=(unset)")

    candidates = [
        ("Project root", project),
        ("scraper_output under project", os.path.join(project, "scraper_output")),
        ("logs (common)", os.path.join(project, "logs")),
        ("webdriver_manager cache", os.path.join(home, ".wdm")),
        ("pip cache", os.path.join(home, ".cache", "pip")),
        ("~/.cache (all)", os.path.join(home, ".cache")),
        ("/tmp", "/tmp"),
        ("/var/tmp", "/var/tmp"),
    ]

    print()
    print("=== FIXED PATHS (single directories) ===")
    for label, path in candidates:
        if "*" in path:
            continue
        sz = du_bytes(path)
        if sz is None:
            print(f"  {label}: {path} -> missing or empty")
        else:
            print(f"  {label}: {_human(sz)}  |  {path}")

    # Glob: all chrome scraper profiles
    chrome_pattern = os.path.join(home, ".chrome_scraper_*")
    chrome_rows = glob_sizes(chrome_pattern)
    total_chrome = sum(s for _p, s in chrome_rows)
    print()
    print(f"=== CHROME PROFILE DIRS ({chrome_pattern}) ===")
    print(f"  count: {len(chrome_rows)}")
    print(f"  total (sum of dirs): {_human(total_chrome)} ({total_chrome:,} bytes)")
    if chrome_rows:
        print("  per directory (largest first):")
        for p, sz in chrome_rows[: max(15, args.top)]:
            print(f"    {_human(sz):>12}  {p}")
    else:
        print("  (none found)")

    print()
    print("=== EXTRA PATHS UNDER HOME ===")
    for label, rel in (
        ("webdriver_manager", os.path.join(home, ".wdm")),
        ("pip cache", os.path.join(home, ".cache", "pip")),
        ("XDG_CACHE_HOME or ~/.cache", os.environ.get("XDG_CACHE_HOME") or os.path.join(home, ".cache")),
    ):
        sz = du_bytes(rel)
        if sz is None:
            print(f"  {label}: {rel} -> missing")
        else:
            print(f"  {label}: {_human(sz)}  |  {rel}")

    print()
    print("=== LARGEST DIRECT ENTRIES UNDER PROJECT ===")
    for p, sz in top_subdirs(project, args.top):
        print(f"  {_human(sz):>12}  {p}")

    print()
    print("=== KNOWN PATHS UNDER HOME (scraper / common heavy dirs) ===")
    home_known: list[tuple[str, str]] = [
        ("~/.wdm (ChromeDriver cache)", os.path.join(home, ".wdm")),
        ("~/.cache/pip", os.path.join(home, ".cache", "pip")),
        ("~/.cache (entire)", os.path.join(home, ".cache")),
        ("~/.local", os.path.join(home, ".local")),
        ("~/snap", os.path.join(home, "snap")),
        ("~/.npm", os.path.join(home, ".npm")),
        ("~/.cargo", os.path.join(home, ".cargo")),
        ("~/.rustup", os.path.join(home, ".rustup")),
    ]
    sized: list[tuple[str, str, int]] = []
    for label, path in home_known:
        sz = du_bytes(path)
        if sz is not None and sz > 0:
            sized.append((label, path, sz))
    sized.sort(key=lambda x: x[2], reverse=True)
    if not sized:
        print("  (none of the known paths exist or all are empty)")
    for label, path, sz in sized:
        print(f"  {_human(sz):>12}  {label}")
        print(f"                {path}")

    if args.full_home:
        print()
        print("=== LARGEST DIRECT ENTRIES UNDER HOME (--full-home; can be slow) ===")
        for p, sz in top_subdirs(home, args.top):
            print(f"  {_human(sz):>12}  {p}")
    else:
        print()
        print("=== HOME TOP-LEVEL SCAN ===")
        print("  (skipped; use --full-home to measure every item in $HOME — slow on big machines)")

    # Optional: docker
    docker_root = "/var/lib/docker"
    if os.path.isdir(docker_root):
        sz = du_bytes(docker_root)
        print()
        print("=== DOCKER (if present) ===")
        if sz is None:
            print(f"  {docker_root}: could not measure")
        else:
            print(f"  {_human(sz)}  |  {docker_root}")

    print()
    print("=== END (copy everything from IGR / VPS DISK AUDIT REPORT above) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
