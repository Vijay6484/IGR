import subprocess
import sys
import os


def ask_year() -> str:
    """Prompt the user for a year and validate it."""
    year = input("Enter year to scrape (e.g. 2026): ").strip()
    if not year.isdigit() or len(year) != 4:
        print(f"Invalid year '{year}'. Please provide a 4-digit year, e.g. 2026.")
        sys.exit(1)
    return year


def run_scraper_for_year(year: str) -> int:
    """Run 1.py for the given year via subprocess."""
    script_path = os.path.join(os.path.dirname(__file__), "1.py")

    if not os.path.exists(script_path):
        print(f"Could not find scraper script at {script_path}")
        return 1

    cmd = [sys.executable, script_path, year]
    print(f"Running: {' '.join(cmd)}")

    # Ensure VPS mode is enabled for the scraper process
    env = os.environ.copy()
    env["VPS_MODE"] = "1"

    result = subprocess.run(cmd, env=env)
    return result.returncode


def main():
    if len(sys.argv) > 1:
        year = sys.argv[1].strip()
    else:
        year = ask_year()

    if not year.isdigit() or len(year) != 4:
        print(f"Invalid year '{year}'. Please provide a 4-digit year, e.g. 2026.")
        sys.exit(1)

    exit_code = run_scraper_for_year(year)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

