#!/usr/bin/env python3
"""
Selenium probe: open IGR site, fill Rest-of-Maharashtra flow, dummy captcha search,
real captcha search (CapSolver), paginate to page 2–3, log every POST body seen on the wire.

Why browsers avoid 0|error|500 while minimal requests clients often hit it:
- The real browser sends ScriptManager-generated payloads that include the full set of
  fields ASP.NET expects for that async trigger (often 20k+ chars of __VIEWSTATE and
  many sibling controls). A trimmed replay can break __EVENTVALIDATION / control tree
  sync and the server throws → MS AJAX wraps it as 0|error|500.
- UpMain|btnSearch_RestMaha / ddl* posts use ScriptManager1=UpMain%7C...; grid paging
  and index clicks use ScriptManager1=tupRegistrationGrid%7CRegistrationGrid with
  __EVENTTARGET=RegistrationGrid&__EVENTARGUMENT=Page$N or indexII$N — the browser
  always pairs these with the current hidden triple from the last delta.

Env:
  CAPTCHA_API_KEY — CapSolver (required for real search)
  CHROME_BINARY — optional browser binary (Chrome or Brave), e.g. Brave on macOS:
    /Applications/Brave Browser.app/Contents/MacOS/Brave Browser

For full POST/response dumps and grid field comparison vs script_revised, run
selenium_igr_flow_capture.py (needs: pip install selenium-wire).

Usage:
  python3 selenium_igr_probe.py 0 2025 1 1 1 0 3
  # headless year district_idx tahsil_idx village_idx property_no max_page
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

URL = "https://freesearchigrservice.maharashtra.gov.in/"
TRACE_DIR = Path(os.environ.get("IGR_SELENIUM_TRACE_DIR", "selenium_trace"))


def _solve_captcha_b64(img_b64: str, api_key: str) -> str:
    task = {"clientKey": api_key, "task": {"type": "ImageToTextTask", "body": img_b64}}
    r = requests.post("https://api.capsolver.com/createTask", json=task, timeout=60)
    r.raise_for_status()
    jr = r.json()
    if jr.get("status") == "ready":
        return (jr.get("solution") or {}).get("text") or ""
    task_id = jr.get("taskId")
    if not task_id:
        raise RuntimeError(f"CapSolver createTask: {jr}")
    t0 = time.time()
    while time.time() - t0 < 90:
        time.sleep(2)
        res = requests.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": api_key, "taskId": task_id},
            timeout=60,
        )
        j = res.json()
        if j.get("status") == "ready":
            return (j.get("solution") or {}).get("text") or ""
    raise RuntimeError("CapSolver timeout")


def _drain_network_posts(driver) -> list[dict]:
    out = []
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
        flags = []
        if "0|error|500" in body:
            flags.append("body_has_500_string_unlikely")
        if "ScriptManager1=" in body:
            sm = re.search(r"ScriptManager1=([^&]+)", body)
            flags.append(f"SM={sm.group(1)[:80] if sm else '?'}")
        if "txtImg1=" in body:
            m = re.search(r"txtImg1=([^&]*)", body)
            flags.append(f"txtImg1={m.group(1)[:20] if m else ''}")
        out.append(
            {
                "url": u,
                "post_len": len(body),
                "flags": flags,
                "preview": body[:400].replace("\n", " "),
            }
        )
    return out


def _log_posts(tag: str, posts: list[dict], log_file) -> None:
    print(f"\n=== {tag}: {len(posts)} POST(s) ===")
    for i, p in enumerate(posts):
        line = f"{tag} #{i+1} len={p['post_len']} {'; '.join(p['flags'])} preview={p['preview'][:200]}..."
        print(line)
        log_file.write(line + "\n")


def _wait_select_options(driver, el_id: str, min_count: int = 2, timeout: int = 60):
    WebDriverWait(driver, timeout).until(
        lambda d: len(Select(d.find_element(By.ID, el_id)).options) >= min_count
    )


def main():
    a = sys.argv[1:]
    headless = int(a[0]) if len(a) > 0 and a[0].isdigit() else 0
    year = str(a[1]) if len(a) > 1 else "2025"
    d_idx = int(a[2]) if len(a) > 2 else 1
    t_idx = int(a[3]) if len(a) > 3 else 1
    v_idx = int(a[4]) if len(a) > 4 else 1
    prop = str(a[5]) if len(a) > 5 else "0"
    max_page = int(a[6]) if len(a) > 6 else 3

    api_key = os.environ.get("CAPTCHA_API_KEY", "").strip()
    if not api_key:
        print("Set CAPTCHA_API_KEY in the environment for CapSolver (real search).", file=sys.stderr)
        sys.exit(1)

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = TRACE_DIR / "probe_posts.log"
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    chrome_bin = os.environ.get("CHROME_BINARY", "").strip()
    if chrome_bin:
        opts.binary_location = chrome_bin
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    wait = WebDriverWait(driver, 90)

    try:
        with open(log_path, "w", encoding="utf-8") as logf:
            logf.write(
                "IGR Selenium probe — POST summaries (full bodies in Chrome do not persist in logs; "
                "use preview + len). For full bodies use browser DevTools or selenium-wire.\n\n"
            )

            driver.get(URL)
            wait.until(EC.element_to_be_clickable((By.ID, "btnOtherdistrictSearch"))).click()
            wait.until(EC.presence_of_element_located((By.ID, "ddlFromYear1")))
            time.sleep(0.5)
            _drain_network_posts(driver)

            Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_value(year)
            _wait_select_options(driver, "ddlDistrict1", 3)
            dist_sel = Select(driver.find_element(By.ID, "ddlDistrict1"))
            if d_idx >= len(dist_sel.options):
                raise RuntimeError(f"district index {d_idx} out of range ({len(dist_sel.options)})")
            dist_sel.select_by_index(d_idx)

            _wait_select_options(driver, "ddltahsil", 2)
            tah_sel = Select(driver.find_element(By.ID, "ddltahsil"))
            if t_idx >= len(tah_sel.options):
                raise RuntimeError(f"tahsil index {t_idx} out of range ({len(tah_sel.options)})")
            tah_sel.select_by_index(t_idx)

            _wait_select_options(driver, "ddlvillage", 2)
            vil_sel = Select(driver.find_element(By.ID, "ddlvillage"))
            if v_idx >= len(vil_sel.options):
                raise RuntimeError(f"village index {v_idx} out of range ({len(vil_sel.options)})")
            vil_sel.select_by_index(v_idx)

            driver.find_element(By.ID, "txtAttributeValue1").clear()
            driver.find_element(By.ID, "txtAttributeValue1").send_keys(prop)
            driver.find_element(By.ID, "txtImg1").clear()
            driver.find_element(By.ID, "txtImg1").send_keys("1")

            driver.find_element(By.ID, "btnSearch_RestMaha").click()
            time.sleep(2.5)
            posts = _drain_network_posts(driver)
            _log_posts("after_dummy_search", posts, logf)

            html = driver.page_source
            m = re.search(r"Handler\.ashx\?txt=[^\s\"'&<>]+", html)
            if not m:
                print("No Handler.ashx in page after dummy search; snippet:", html[:2000])
                raise RuntimeError("captcha handler not found")
            cap_path = m.group(0)
            cap_url = cap_path if cap_path.startswith("http") else urljoin(URL, cap_path.lstrip("/"))
            sess = requests.Session()
            for c in driver.get_cookies():
                sess.cookies.set(c["name"], c["value"])
            gr = sess.get(
                cap_url,
                headers={"User-Agent": driver.execute_script("return navigator.userAgent;"), "Referer": URL},
                timeout=60,
            )
            gr.raise_for_status()
            b64 = base64.b64encode(gr.content).decode("ascii")
            solved = (_solve_captcha_b64(b64, api_key) or "").strip().upper()
            print("Captcha solved:", solved)

            driver.find_element(By.ID, "txtImg1").clear()
            driver.find_element(By.ID, "txtImg1").send_keys(solved)
            driver.find_element(By.ID, "btnSearch_RestMaha").click()
            time.sleep(3.0)
            posts = _drain_network_posts(driver)
            _log_posts("after_real_search", posts, logf)

            wait.until(EC.presence_of_element_located((By.ID, "RegistrationGrid")))
            grid = driver.find_element(By.ID, "RegistrationGrid")

            for page in range(2, max_page + 1):
                arg = f"Page${page}"
                try:
                    link = grid.find_element(By.XPATH, f".//a[contains(@href, '{arg}')]")
                except Exception:
                    link = grid.find_element(By.LINK_TEXT, str(page))
                link.click()
                time.sleep(2.5)
                posts = _drain_network_posts(driver)
                _log_posts(f"after_page_{page}", posts, logf)
                grid = driver.find_element(By.ID, "RegistrationGrid")

            print(f"\nProbe done. Log: {log_path.resolve()}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
