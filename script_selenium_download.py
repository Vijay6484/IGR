#!/usr/bin/env python3
"""
Browser-driven IGR downloader using Selenium (mirrors real ScriptManager posts).

Flow (same as a human):
1) Open site → Rest of Maharashtra → year / district / tahsil / village / property no.
2) First search uses dummy captcha txtImg1=1 to force a new captcha image (server rejects
   the search but returns Handler.ashx + message).
3) Solve GIF via CapSolver, second search with real captcha → grid loads.
4) For each target page, click indexII$N on the grid; report opens in a new tab
   (HtmlReport.aspx?IndexClick=...). Save that HTML under output/selenium/...

Why raw requests sometimes get 0|error|500 on grid AJAX:
- ASP.NET expects the same field bundle the browser sends with each async post. Sending
  only a handful of fields + viewstate can invalidate __EVENTVALIDATION or control state,
  and the server throws; MS AJAX surfaces that as 0|error|500. Selenium always submits
  the live DOM-backed payload.

Env:
  CAPTCHA_API_KEY — CapSolver client key (required)
  CHROME_BINARY — optional path to Chrome (e.g. /Applications/Google Chrome.app/Contents/MacOS/Google Chrome)

Usage:
  python3 script_selenium_download.py 0 2025 1 1 1 0 3 0
  # headless year d_idx t_idx v_idx property_no max_page max_index_on_last_page
  # max_index_on_last_page: 0 = only index 0 per page; 9 = all ten slots
"""

from __future__ import annotations

import base64
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


def _wait_select_options(driver, el_id: str, min_count: int = 2, timeout: int = 60):
    WebDriverWait(driver, timeout).until(
        lambda d: len(Select(d.find_element(By.ID, el_id)).options) >= min_count
    )


def _save_html(out_root: Path, prop: str, page: int, index_no: int, html: str) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    p = out_root / f"report_prop_{prop}_page_{page}_index_{index_no}.html"
    p.write_text(html or "", encoding="utf-8")
    return p


def _click_index_and_save_report(driver, wait, grid, page_no: int, index_no: int, out_root: Path, prop: str):
    arg = f"indexII${index_no}"
    link = grid.find_element(By.XPATH, f".//a[contains(@href, '{arg}')]")
    main = driver.current_window_handle
    before = driver.window_handles[:]
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
    time.sleep(0.2)
    link.click()
    time.sleep(1.5)
    after = driver.window_handles[:]
    new_tabs = [h for h in after if h not in before]
    if new_tabs:
        driver.switch_to.window(new_tabs[-1])
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(0.5)
        path = _save_html(out_root, prop, page_no, index_no, driver.page_source)
        print(f"[saved] {path}")
        driver.close()
        driver.switch_to.window(main)
    else:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        path = _save_html(out_root, prop, page_no, index_no, driver.page_source)
        print(f"[saved same-window] {path}")
        if driver.current_window_handle != main:
            driver.switch_to.window(main)


def main():
    argv = sys.argv[1:]
    headless = int(argv[0]) if len(argv) > 0 and str(argv[0]).isdigit() else 0
    year = str(argv[1]) if len(argv) > 1 else "2025"
    d_idx = int(argv[2]) if len(argv) > 2 else 1
    t_idx = int(argv[3]) if len(argv) > 3 else 1
    v_idx = int(argv[4]) if len(argv) > 4 else 1
    prop = str(argv[5]) if len(argv) > 5 else "0"
    max_page = int(argv[6]) if len(argv) > 6 else 3
    max_index = int(argv[7]) if len(argv) > 7 else 0

    api_key = os.environ.get("CAPTCHA_API_KEY", "").strip()
    if not api_key:
        print("CAPTCHA_API_KEY is required in the environment.", file=sys.stderr)
        sys.exit(1)

    out_root = Path(os.environ.get("IGR_SELENIUM_OUT", "output/selenium"))

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    chrome_bin = os.environ.get("CHROME_BINARY", "").strip()
    if chrome_bin:
        opts.binary_location = chrome_bin

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    wait = WebDriverWait(driver, 90)

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
            raise RuntimeError("Captcha handler not found after dummy search")
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
        b64 = base64.b64encode(gr.content).decode("ascii")
        solved = (_solve_captcha_b64(b64, api_key) or "").strip().upper()
        print("[captcha]", solved)

        driver.find_element(By.ID, "txtImg1").clear()
        driver.find_element(By.ID, "txtImg1").send_keys(solved)
        driver.find_element(By.ID, "btnSearch_RestMaha").click()
        time.sleep(3.0)

        wait.until(EC.presence_of_element_located((By.ID, "RegistrationGrid")))

        for page_no in range(1, max_page + 1):
            for ix in range(max_index + 1):
                try:
                    grid = driver.find_element(By.ID, "RegistrationGrid")
                    _click_index_and_save_report(driver, wait, grid, page_no, ix, out_root, prop)
                except Exception as e:
                    print(f"[skip] page={page_no} index={ix}: {e}")
                    main = driver.window_handles[0]
                    while len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.close()
                    driver.switch_to.window(main)
                    break

            if page_no < max_page:
                grid = driver.find_element(By.ID, "RegistrationGrid")
                arg = f"Page${page_no + 1}"
                try:
                    plink = grid.find_element(By.XPATH, f".//a[contains(@href, '{arg}')]")
                except Exception:
                    plink = grid.find_element(By.LINK_TEXT, str(page_no + 1))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", plink)
                time.sleep(0.2)
                plink.click()
                time.sleep(2.5)
                wait.until(EC.presence_of_element_located((By.ID, "RegistrationGrid")))

        print(f"Done. Output under {out_root.resolve()}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
