#!/usr/bin/env python3
"""
Full-flow network capture for IGR (diagnose MS-AJAX 0|error|500 vs requests script).

Selenium does NOT attach to an already-open Brave window. It starts a *new* browser.
Use Brave by pointing at its binary, e.g. on macOS:

  export CHROME_BINARY="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"

Install full POST/response bodies (strongly recommended):

  pip install selenium-wire

Without selenium-wire this script falls back to Chrome performance logs (post bodies
are often truncated).

Outputs under selenium_capture/ (override with IGR_SELENIUM_CAPTURE_DIR):
  summary.txt          — ordered POSTs, status, MS-AJAX 500 flag, field counts
  grid_field_compare.txt — browser grid POST key names vs minimal script set
  NNN_*.req.txt / NNN_*.res.txt — raw request line + body / response status + body prefix

Env: CAPTCHA_API_KEY (CapSolver). Same argv as selenium_igr_probe.py.

Usage:
  pip install selenium-wire webdriver-manager
  export CAPTCHA_API_KEY=...
  export CHROME_BINARY="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"   # optional
  python3 selenium_igr_flow_capture.py 0 2025 1 1 1 0 2
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urljoin

import requests
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

try:
    from seleniumwire import webdriver as WireChrome
except ImportError:
    WireChrome = None

from selenium import webdriver as PlainChrome

from selenium_igr_probe import URL, _solve_captcha_b64, _wait_select_options

# Keys sent by script_revised minimal grid path (reference for compare)
_MINIMAL_GRID_KEYS_ORDERED = [
    "ddlFromYear1",
    "ddlDistrict1",
    "ddltahsil",
    "ddlvillage",
    "txtAttributeValue1",
    "txtImg1",
    "FS_PropertyNumber",
    "FS_IGR_FLAG",
    "__EVENTTARGET",
    "__EVENTARGUMENT",
    "__LASTFOCUS",
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__ASYNCPOST",
]


def _parse_form_keys_ordered(post_body: str) -> list[str]:
    if not post_body:
        return []
    text = post_body.strip()
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    keys = []
    seen = set()
    for k, _v in parse_qsl(text, keep_blank_values=True):
        if k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def _is_msajax_500(text: str) -> bool:
    t = text or ""
    return "0|error|500" in t


def _slug(s: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w]+", "_", s, flags=re.ASCII)[:max_len].strip("_")
    return s or "req"


def _build_driver(headless: int, use_wire: bool):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    chrome_bin = os.environ.get("CHROME_BINARY", "").strip()
    if chrome_bin:
        opts.binary_location = chrome_bin
    service = Service(ChromeDriverManager().install())
    if use_wire and WireChrome is not None:
        return WireChrome(
            service=service,
            options=opts,
            seleniumwire_options={"disable_encoding": True, "verify_ssl": False},
        )
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return PlainChrome.Chrome(service=service, options=opts)


def _dump_performance_posts_plain(driver, out_dir: Path, counter: list) -> None:
    """Fallback when selenium-wire missing: short postData from CDP performance log."""
    for entry in driver.get_log("performance"):
        try:
            msg = json.loads(entry["message"])["message"]
        except (json.JSONDecodeError, KeyError):
            continue
        if msg.get("method") != "Network.requestWillBeSent":
            continue
        req = msg.get("params", {}).get("request", {})
        if req.get("method") != "POST":
            continue
        u = req.get("url", "")
        if "freesearchigrservice.maharashtra.gov.in" not in u:
            continue
        body = req.get("postData") or ""
        counter[0] += 1
        n = counter[0]
        base = f"{n:03d}_{_slug(u)}"
        p_req = out_dir / f"{base}.req.txt"
        p_req.write_text(f"POST {u}\n\n{body}", encoding="utf-8")


def _flush_wire_captures(driver, out_dir: Path, counter: list, summary_lines: list[str]) -> None:
    for req in getattr(driver, "requests", []) or []:
        if req.method != "POST" or "freesearchigrservice.maharashtra.gov.in" not in (req.url or ""):
            continue
        counter[0] += 1
        n = counter[0]
        base = f"{n:03d}_{_slug(req.url)}"
        body = req.body
        if isinstance(body, bytes):
            try:
                body_s = body.decode("utf-8")
            except UnicodeDecodeError:
                body_s = body.decode("utf-8", errors="replace")
        else:
            body_s = str(body or "")

        p_req = out_dir / f"{base}.req.txt"
        p_req.write_text(f"POST {req.url}\n\n{body_s}", encoding="utf-8")

        resp = req.response
        status = getattr(resp, "status_code", None) if resp else None
        rbody = b""
        if resp and resp.body:
            rbody = resp.body
        try:
            rtext = rbody.decode("utf-8", errors="replace")
        except Exception:
            rtext = str(rbody[:2000])
        p_res = out_dir / f"{base}.res.txt"
        head = f"HTTP {status}\n\n"
        p_res.write_text(head + rtext[:80000], encoding="utf-8")

        keys = _parse_form_keys_ordered(body_s)
        sm = ""
        m = re.search(r"ScriptManager1=([^&]+)", body_s)
        if m:
            sm = unquote(m.group(1))
        ajax500 = _is_msajax_500(rtext)
        line = (
            f"{n:03d} POST status={status} ajax500={ajax500} sm={sm!r} "
            f"fields={len(keys)} len_req={len(body_s)} len_res={len(rtext)}"
        )
        summary_lines.append(line)

        if "tupRegistrationGrid" in body_s or "RegistrationGrid" in sm:
            extra = out_dir / f"{base}.grid_keys.txt"
            browser_keys = keys
            only_min = [k for k in _MINIMAL_GRID_KEYS_ORDERED if k in browser_keys]
            only_browser = [k for k in browser_keys if k not in _MINIMAL_GRID_KEYS_ORDERED]
            extra.write_text(
                "Browser grid POST field names (order first occurrence):\n"
                + "\n".join(browser_keys)
                + "\n\n--- In minimal script set ---\n"
                + "\n".join(only_min)
                + "\n\n--- Extra vs minimal script (send these for parity) ---\n"
                + "\n".join(only_browser),
                encoding="utf-8",
            )


def main():
    a = sys.argv[1:]
    headless = int(a[0]) if len(a) > 0 and a[0].isdigit() else 0
    year = str(a[1]) if len(a) > 1 else "2025"
    d_idx = int(a[2]) if len(a) > 2 else 1
    t_idx = int(a[3]) if len(a) > 3 else 1
    v_idx = int(a[4]) if len(a) > 4 else 1
    prop = str(a[5]) if len(a) > 5 else "0"
    max_page = int(a[6]) if len(a) > 6 else 2

    api_key = os.environ.get("CAPTCHA_API_KEY", "").strip()
    if not api_key:
        print("Set CAPTCHA_API_KEY for CapSolver.", file=sys.stderr)
        sys.exit(1)

    use_wire = WireChrome is not None
    if not use_wire:
        print(
            "[WARN] selenium-wire not installed; POST bodies may be truncated. "
            "Run: pip install selenium-wire",
            file=sys.stderr,
        )

    out_dir = Path(os.environ.get("IGR_SELENIUM_CAPTURE_DIR", "selenium_capture"))
    out_dir.mkdir(parents=True, exist_ok=True)

    driver = _build_driver(headless, use_wire)
    wait = WebDriverWait(driver, 90)
    counter = [0]
    summary_lines: list[str] = []

    try:
        driver.get(URL)
        wait.until(EC.element_to_be_clickable((By.ID, "btnOtherdistrictSearch"))).click()
        wait.until(EC.presence_of_element_located((By.ID, "ddlFromYear1")))
        time.sleep(0.5)

        Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_value(year)
        _wait_select_options(driver, "ddlDistrict1", 3)
        Select(driver.find_element(By.ID, "ddlDistrict1")).select_by_index(d_idx)
        _wait_select_options(driver, "ddltahsil", 2)
        Select(driver.find_element(By.ID, "ddltahsil")).select_by_index(t_idx)
        _wait_select_options(driver, "ddlvillage", 2)
        Select(driver.find_element(By.ID, "ddlvillage")).select_by_index(v_idx)

        driver.find_element(By.ID, "txtAttributeValue1").clear()
        driver.find_element(By.ID, "txtAttributeValue1").send_keys(prop)
        driver.find_element(By.ID, "txtImg1").clear()
        driver.find_element(By.ID, "txtImg1").send_keys("1")
        driver.find_element(By.ID, "btnSearch_RestMaha").click()
        time.sleep(2.5)

        html = driver.page_source
        m = re.search(r"Handler\.ashx\?txt=[^\s\"'&<>]+", html)
        if not m:
            raise RuntimeError("captcha handler not found after dummy search")
        cap_url = m.group(0)
        if not cap_url.startswith("http"):
            cap_url = urljoin(URL, cap_url.lstrip("/"))
        sess = requests.Session()
        for c in driver.get_cookies():
            sess.cookies.set(c["name"], c["value"])
        gr = sess.get(
            cap_url,
            headers={"User-Agent": driver.execute_script("return navigator.userAgent;"), "Referer": URL},
            timeout=60,
        )
        gr.raise_for_status()
        solved = (_solve_captcha_b64(base64.b64encode(gr.content).decode("ascii"), api_key) or "").strip().upper()
        print("[captcha]", solved)

        driver.find_element(By.ID, "txtImg1").clear()
        driver.find_element(By.ID, "txtImg1").send_keys(solved)
        driver.find_element(By.ID, "btnSearch_RestMaha").click()
        time.sleep(3.0)

        wait.until(EC.presence_of_element_located((By.ID, "RegistrationGrid")))
        grid = driver.find_element(By.ID, "RegistrationGrid")

        # First index → often opens report tab (captures index POST + any follow-ups)
        main_h = driver.current_window_handle
        try:
            arg0 = "indexII$0"
            link0 = grid.find_element(By.XPATH, f".//a[contains(@href, '{arg0}')]")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link0)
            time.sleep(0.2)
            link0.click()
            time.sleep(2.0)
            for h in driver.window_handles:
                if h != main_h:
                    driver.switch_to.window(h)
                    time.sleep(0.5)
                    driver.close()
            driver.switch_to.window(main_h)
        except Exception as e:
            print(f"[WARN] indexII$0 click skipped: {e}")

        grid = driver.find_element(By.ID, "RegistrationGrid")
        if max_page >= 2:
            arg = "Page$2"
            try:
                plink = grid.find_element(By.XPATH, f".//a[contains(@href, '{arg}')]")
            except Exception:
                plink = grid.find_element(By.LINK_TEXT, "2")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", plink)
            time.sleep(0.2)
            plink.click()
            time.sleep(2.5)

        time.sleep(0.5)
        if use_wire:
            _flush_wire_captures(driver, out_dir, counter, summary_lines)
        else:
            _dump_performance_posts_plain(driver, out_dir, counter)

        compare_parts = []
        for p in sorted(out_dir.glob("*.grid_keys.txt")):
            compare_parts.append(f"=== {p.name} ===\n{p.read_text(encoding='utf-8')}\n")
        if compare_parts:
            (out_dir / "grid_field_compare.txt").write_text("\n".join(compare_parts), encoding="utf-8")

        intro = (
            "IGR flow capture\n"
            f"selenium-wire={'yes' if use_wire else 'no (truncated POST likely)'}\n"
            f"CHROME_BINARY={os.environ.get('CHROME_BINARY') or '(default Chrome)'}\n\n"
            "If any line shows ajax500=True, the server returned MS-AJAX 0|error|500 for that POST.\n"
            "Compare *.grid_keys.txt 'Extra vs minimal' list with script_revised grid_form_baseline.\n\n"
        )
        (out_dir / "summary.txt").write_text(intro + "\n".join(summary_lines), encoding="utf-8")
        print(f"Done. Captures in {out_dir.resolve()}")
        print("Read summary.txt and *.grid_keys.txt to tune script_revised.py.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
