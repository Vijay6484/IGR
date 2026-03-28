import json
import os
import re
import sys
import time
import shutil
import tempfile
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    ElementNotInteractableException,
)


class NoRegistrationRecordsError(Exception):
    """Search ran (captcha OK) but the registration grid has no rows to scrape for this property."""


class IndexDocumentUnavailableError(Exception):
    """indexII POST returned 0|error|500|| — that grid cell has no document; skip rest of this property."""


# Phrases in lblMsg / grid that mean zero results (skip property, do not treat as hard failure).
_NO_RECORD_LABEL_PHRASES = (
    "no data",
    "no record",
    "not found",
    "does not exist",
    "no result",
    "no registration",
    "no document",
)

# ==============================
# CONFIG
# ==============================
URL = "https://freesearchigrservice.maharashtra.gov.in/"
CAPTCHA_API_KEY = "CAP-03DD9281E150148DCB0705A6F665CF337303C5FDC399749D977BEAC6CD398191"
REPORT_URL = "https://freesearchigrservice.maharashtra.gov.in/isaritaHTMLReportSuchiKramank2_RegLive.aspx"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "X-MicrosoftAjax": "Delta=true",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://freesearchigrservice.maharashtra.gov.in",
    "Referer": "https://freesearchigrservice.maharashtra.gov.in/",
    "Accept": "*/*",
}

# ==============================
# PARAMS
# ==============================
HEADLESS = int(sys.argv[1]) if len(sys.argv) > 1 else 1
YEAR = sys.argv[2] if len(sys.argv) > 2 else "2020"
DISTRICT_INDEX = int(sys.argv[3]) if len(sys.argv) > 3 else 1
TAHSIL_INDEX = int(sys.argv[4]) if len(sys.argv) > 4 else 1

PROPERTY_START = 0
PROPERTY_END = 9
PROPERTY_RETRY_MAX = 3
SELENIUM_BATCH_MAX = 4
HTTP_RETRY_MAX = 4
HTTP_RETRY_SLEEP_SEC = 2.0
PAGE_RECOVERY_MAX = 3
# Report download: only GET retries (never re-POST indexII). 1 initial + 3 retries = 4 attempts.
REPORT_GET_MAX_ATTEMPTS = 4
REPORT_GET_RETRY_SLEEP_SEC = 0.35


def _debug_port():
    # Avoid collisions across parallel tmux processes
    return 10000 + (os.getpid() % 50000)

print(
    f"HEADLESS={HEADLESS}, YEAR={YEAR}, D={DISTRICT_INDEX}, "
    f"T={TAHSIL_INDEX}, V=AUTO, PROPS={PROPERTY_START}-{PROPERTY_END}"
)


def solve_captcha(driver):
    print("Solving captcha...")
    img_base64 = None
    for _ in range(8):
        try:
            img = driver.find_element(By.ID, "imgCaptcha_new")
            img_base64 = driver.execute_script(
                """
                var img = arguments[0];
                var canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                var ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                return canvas.toDataURL('image/png').split(',')[1];
                """,
                img,
            )
            break
        except StaleElementReferenceException:
            time.sleep(0.25)
    if img_base64 is None or img_base64 == "":
        raise RuntimeError("could not snapshot captcha image after retries")

    task = {
        "clientKey": CAPTCHA_API_KEY,
        "task": {"type": "ImageToTextTask", "body": img_base64},
    }

    r = requests.post("https://api.capsolver.com/createTask", json=task).json()
    print("Task created:", r)

    if r.get("status") == "ready":
        print("Captcha solved instantly")
        return r["solution"]["text"]

    task_id = r.get("taskId")
    if not task_id:
        raise Exception("CapSolver task creation failed")

    start = time.time()
    while True:
        if time.time() - start > 60:
            raise Exception("Captcha solve timeout")
        time.sleep(2)
        res = requests.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": CAPTCHA_API_KEY, "taskId": task_id},
        ).json()
        if res.get("status") == "ready":
            return res["solution"]["text"]


def _wait_for_dropdown_population(driver, dropdown_id, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: len(Select(d.find_element(By.ID, dropdown_id)).options) > 1
    )


def _wait_for_dropdown_has_index(driver, dropdown_id, index, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: len(Select(d.find_element(By.ID, dropdown_id)).options) > index
    )


def _wait_for_aspnet_ajax_idle(driver, timeout=45, poll=0.12):
    """
    Wait until ASP.NET AJAX (ScriptManager / PageRequestManager) finishes an async
    postback so UpdatePanel DOM is stable (reduces stale element errors).
    """
    deadline = time.time() + timeout
    stable = 0
    required_stable = 2
    while time.time() < deadline:
        try:
            busy = driver.execute_script(
                """
                try {
                    if (typeof Sys !== 'undefined' && Sys.WebForms && Sys.WebForms.PageRequestManager) {
                        var prm = Sys.WebForms.PageRequestManager.getInstance();
                        if (prm && typeof prm.get_isInAsyncPostBack === 'function') {
                            return prm.get_isInAsyncPostBack();
                        }
                    }
                } catch (e) {}
                return false;
                """
            )
        except Exception:
            busy = False
        if not busy:
            stable += 1
            if stable >= required_stable:
                time.sleep(0.22)
                return
        else:
            stable = 0
        time.sleep(poll)


def _select_by_visible_text_safe(driver, select_id: str, text: str, timeout=30, retries=6):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, select_id)))
            WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.ID, select_id)))
            sel = Select(driver.find_element(By.ID, select_id))
            sel.select_by_visible_text(text)
            _wait_for_aspnet_ajax_idle(driver, timeout=min(timeout, 45))
            return
        except (StaleElementReferenceException, TimeoutException, ElementNotInteractableException) as e:
            last_exc = e
            time.sleep(0.4)
    raise last_exc


def _select_by_index_safe(driver, select_id: str, index: int, timeout=30, retries=6):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, select_id)))
            WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.ID, select_id)))
            WebDriverWait(driver, timeout).until(
                lambda d: len(Select(d.find_element(By.ID, select_id)).options) > index
            )
            sel = Select(driver.find_element(By.ID, select_id))
            sel.select_by_index(index)
            _wait_for_aspnet_ajax_idle(driver, timeout=min(timeout, 45))
            return
        except (StaleElementReferenceException, TimeoutException, ElementNotInteractableException) as e:
            last_exc = e
            time.sleep(0.4)
    raise last_exc


def _click_by_id_safe(
    driver,
    element_id: str,
    timeout=25,
    retries=8,
    wait_ajax_after=True,
):
    last_exc = None
    for _ in range(1, retries + 1):
        try:
            WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.ID, element_id)))
            driver.find_element(By.ID, element_id).click()
            if wait_ajax_after:
                _wait_for_aspnet_ajax_idle(driver, timeout=50)
            return
        except (StaleElementReferenceException, TimeoutException, ElementNotInteractableException) as e:
            last_exc = e
            time.sleep(0.35)
    if last_exc:
        raise last_exc
    raise TimeoutException(f"click failed: {element_id}")


def _clear_send_keys_safe(driver, element_id: str, text: str, timeout=25, retries=8):
    last_exc = None
    for _ in range(1, retries + 1):
        try:
            WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.ID, element_id)))
            el = driver.find_element(By.ID, element_id)
            el.clear()
            el.send_keys(text)
            return
        except (StaleElementReferenceException, TimeoutException, ElementNotInteractableException) as e:
            last_exc = e
            time.sleep(0.35)
    if last_exc:
        raise last_exc
    raise TimeoutException(f"input failed: {element_id}")


def _selected_value_or_text(driver, select_id):
    last_exc = None
    for _ in range(1, 10):
        try:
            sel = Select(driver.find_element(By.ID, select_id))
            opt = sel.first_selected_option
            val = opt.get_attribute("value")
            if val is not None and val != "":
                return val
            return (opt.text or "").strip()
        except StaleElementReferenceException as e:
            last_exc = e
            time.sleep(0.3)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"could not read selected value for {select_id}")


def _selected_text(driver, select_id):
    last_exc = None
    for _ in range(1, 10):
        try:
            sel = Select(driver.find_element(By.ID, select_id))
            return (sel.first_selected_option.text or "").strip()
        except StaleElementReferenceException as e:
            last_exc = e
            time.sleep(0.3)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"could not read selected text for {select_id}")


def _wait_for_captcha_loaded(driver, baseline_src=None, timeout=30):
    def _ready(d):
        try:
            img = d.find_element(By.ID, "imgCaptcha_new")
            src = img.get_attribute("src")
            if not src:
                return False
            if baseline_src is not None and src == baseline_src:
                return False
            natural_width = d.execute_script("return arguments[0].naturalWidth;", img)
            return natural_width and int(natural_width) > 0
        except Exception:
            return False

    WebDriverWait(driver, timeout).until(_ready)


def _any_visible_error_text(driver):
    error_keywords = (
        "captcha",
        "invalid",
        "error",
        "required",
        "enter",
        "incorrect",
        "no record",
        "not found",
        "does not exist",
        "please select",
        "please enter",
    )

    ignore_phrases = (
        "information provided on this site is updated",
        "no physical visit is required",
        "all physically available data at sr offices from 1985 is available online",
        "mumbai city and suburb districts",
    )

    candidates = [
        (By.ID, "lblMsgCTS1"),
        (By.ID, "lblMsg"),
        (By.ID, "lblMessage"),
        (By.ID, "lblError"),
        (By.ID, "message"),
        (By.ID, "ValidationSummary1"),
        (By.CSS_SELECTOR, ".validation-summary-errors"),
        (By.CSS_SELECTOR, ".error"),
        (By.CSS_SELECTOR, ".errormsg"),
        (By.CSS_SELECTOR, ".alert"),
        (By.CSS_SELECTOR, ".alert-danger"),
        (By.CSS_SELECTOR, ".text-danger"),
    ]

    for by, value in candidates:
        try:
            el = driver.find_element(by, value)
            if el and el.is_displayed():
                txt = (el.text or "").strip()
                if txt:
                    tl = txt.lower()
                    if any(p in tl for p in ignore_phrases):
                        continue
                    if any(k in tl for k in error_keywords):
                        return txt
        except Exception:
            pass
    return None


def _wait_for_search_outcome(driver, timeout=120):
    _wait_for_aspnet_ajax_idle(driver, timeout=min(60, max(15, timeout // 2)))
    start = time.time()
    time.sleep(0.35)
    while True:
        try:
            grid = driver.find_element(By.ID, "RegistrationGrid")
            if grid and grid.is_displayed():
                return ("success", None)
        except Exception:
            pass

        try:
            msg_el = driver.find_element(By.ID, "lblMsgCTS1")
            if msg_el and msg_el.is_displayed():
                txt = (msg_el.text or "").strip()
                if txt:
                    tl = txt.lower()
                    if any(p in tl for p in _NO_RECORD_LABEL_PHRASES):
                        return ("no_records", txt)
                    return ("message", txt)
        except Exception:
            pass

        msg = _any_visible_error_text(driver)
        if msg:
            return ("error", msg)

        if time.time() - start > timeout:
            return ("timeout", None)
        time.sleep(0.25)


def _selenium_has_any_registration_records(driver) -> bool:
    """True if the grid exposes index-II links (scrapable rows). Uses Selenium only."""
    try:
        msg_el = driver.find_element(By.ID, "lblMsgCTS1")
        if msg_el.is_displayed():
            t = (msg_el.text or "").strip().lower()
            if t and any(p in t for p in _NO_RECORD_LABEL_PHRASES):
                return False
    except Exception:
        pass
    try:
        html = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
        h = html.lower()
        return "indexii" in h or "indexii$" in h
    except Exception:
        return False


def _pager_shows_page_one(html: str) -> bool:
    if re.search(r"Page\s*1\s+of\s+\d+", html or "", re.I):
        return True
    if re.search(r"Page\s*1\s*/\s*\d+", html or "", re.I):
        return True
    m = re.search(r"Page\s*(\d+)\s+of\s+\d+", html or "", re.I)
    if m and int(m.group(1)) == 1:
        return True
    m2 = re.search(r"Page\s*(\d+)\s*/\s*\d+", html or "", re.I)
    return bool(m2 and int(m2.group(1)) == 1)


def _click_pager_first_or_prev(driver) -> bool:
    """Try First / « / Prev style pager links inside RegistrationGrid (go toward page 1)."""
    try:
        return bool(
            driver.execute_script(
                """
                var g = document.getElementById('RegistrationGrid');
                if (!g) return false;
                var links = g.querySelectorAll('a[href]');
                var tryTexts = ['first', '<<', '«', '<', 'prev', 'previous', 'back'];
                for (var i = 0; i < links.length; i++) {
                    var a = links[i];
                    var t = (a.textContent || '').trim().toLowerCase();
                    var h = (a.getAttribute('href') || '').toLowerCase();
                    for (var j = 0; j < tryTexts.length; j++) {
                        if (t === tryTexts[j] || t.indexOf(tryTexts[j]) === 0) {
                            a.click();
                            return true;
                        }
                    }
                    if (h.indexOf('first') >= 0 || h.indexOf('prev') >= 0) {
                        a.click();
                        return true;
                    }
                }
                return false;
                """
            )
        )
    except Exception:
        return False


def _click_grid_pager_page_number(driver, page_num: int) -> bool:
    """
    Click a RegistrationGrid pager link for page N: Page$N in href, or visible text 'N' on a Page$ postback.
    """
    try:
        return bool(
            driver.execute_script(
                """
                var n = arguments[0];
                var s = String(n);
                var needle1 = 'Page$' + s;
                var needle2 = 'Page%24' + s;
                var g = document.getElementById('RegistrationGrid');
                if (!g) return false;
                var links = g.querySelectorAll('a[href]');
                for (var i = 0; i < links.length; i++) {
                    var a = links[i];
                    var h = a.getAttribute('href') || '';
                    if (h.indexOf('doPostBack') < 0 && h.indexOf('__doPostBack') < 0) continue;
                    if (h.indexOf(needle1) >= 0 || h.indexOf(needle2) >= 0) {
                        a.click();
                        return true;
                    }
                }
                for (var j = 0; j < links.length; j++) {
                    var a2 = links[j];
                    var h2 = a2.getAttribute('href') || '';
                    if ((a2.textContent || '').trim() !== s) continue;
                    if (h2.indexOf('Page$') >= 0 || h2.indexOf('Page%24') >= 0) {
                        a2.click();
                        return true;
                    }
                }
                return false;
                """,
                int(page_num),
            )
        )
    except Exception:
        return False


def _try_dopostback_registration_grid_page_one(driver) -> bool:
    """Last resort: call ASP.NET __doPostBack for RegistrationGrid Page$1 if exposed on the page."""
    try:
        return bool(
            driver.execute_script(
                """
                try {
                    if (typeof __doPostBack === 'function') {
                        __doPostBack('RegistrationGrid', 'Page$1');
                        return true;
                    }
                } catch (e) {}
                return false;
                """
            )
        )
    except Exception:
        return False


def _selenium_ensure_grid_on_page_one(driver, max_rounds: int = 16, total_pages: int | None = None) -> None:
    """After pager exploration, return the grid to page 1 so ViewState matches HTTP start."""
    if total_pages == 1:
        print("[PAGER] total_pages=1 — already on the only page; skipping return-to-page-one")
        return
    for r in range(1, max_rounds + 1):
        _wait_for_aspnet_ajax_idle(driver, timeout=35)
        try:
            html = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
        except Exception:
            raise RuntimeError("RegistrationGrid missing while returning to page 1")
        if _pager_shows_page_one(html):
            print("[PAGER] grid is on page 1 (label/HTML check)")
            return
        if _click_grid_pager_page_number(driver, 1):
            time.sleep(0.2)
            continue
        if _pagination_probe_click_page_postback(driver, 1):
            time.sleep(0.2)
            continue
        if _click_pager_first_or_prev(driver):
            time.sleep(0.2)
            continue
        print(f"[PAGER] warn: could not move toward page 1 (round {r}/{max_rounds})")
        time.sleep(0.25)
    if _try_dopostback_registration_grid_page_one(driver):
        _wait_for_aspnet_ajax_idle(driver, timeout=35)
        time.sleep(0.3)
        try:
            html = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
            if _pager_shows_page_one(html):
                print("[PAGER] grid on page 1 after __doPostBack(Page$1)")
                return
        except Exception:
            pass
    try:
        html = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
        if _pager_shows_page_one(html):
            print("[PAGER] grid on page 1 after final check")
            return
    except Exception:
        pass
    raise RuntimeError(
        "Could not return RegistrationGrid to page 1 after counting pages; "
        "try headed browser or inspect pager markup."
    )


def _selenium_count_total_pages_via_ellipsis(driver) -> tuple[int, bool]:
    """
    Discover total page count. If 'Page X of Y' is present on the first paint, use Y and do not
    navigate (avoids useless ellipsis + return-to-page-one). Otherwise walk ellipsis.

    Returns (total_pages, pager_was_navigated).
    """
    _wait_for_aspnet_ajax_idle(driver, timeout=45)
    try:
        html0 = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
    except Exception:
        return 1, False

    label_tot, link_max0 = _pager_info_from_text(html0)
    if label_tot is not None:
        total = max(int(label_tot), 1)
        print(f"[PAGER] total_pages={total} from pager label (no navigation — skipping return-to-page-one)")
        return total, False

    max_n = link_max0 or 1
    moved = False
    for sweep in range(1, 200):
        _wait_for_aspnet_ajax_idle(driver, timeout=45)
        try:
            html = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
        except Exception:
            break
        _, link_max = _pager_info_from_text(html)
        if link_max:
            max_n = max(max_n, link_max)
        if _pagination_probe_click_ellipsis_in_grid(driver):
            moved = True
            time.sleep(0.25)
            continue
        break

    _wait_for_aspnet_ajax_idle(driver, timeout=35)
    try:
        html = driver.find_element(By.ID, "RegistrationGrid").get_attribute("outerHTML") or ""
        label2, link_max = _pager_info_from_text(html)
        if link_max:
            max_n = max(max_n, link_max)
        if label2:
            max_n = max(max_n, label2)
    except Exception:
        pass

    total = max(max_n, 1)
    if moved:
        print(f"[PAGER] Selenium counted total_pages={total} (ellipsis walk; will return to page 1)")
    else:
        print(f"[PAGER] total_pages={total} from visible pager links (no ellipsis — skipping return-to-page-one)")
    return total, moved


def _wait_hidden_fields_ready(driver, prev_viewstate="", timeout=30):
    def _ready(d):
        try:
            vs = d.find_element(By.ID, "__VIEWSTATE").get_attribute("value") or ""
            ev = d.find_element(By.ID, "__EVENTVALIDATION").get_attribute("value") or ""
            if not vs or not ev:
                return False
            if prev_viewstate and vs == prev_viewstate:
                return False
            return True
        except Exception:
            return False

    try:
        WebDriverWait(driver, timeout).until(_ready)
    except Exception:
        pass


def _field(driver, element_id):
    try:
        el = driver.find_element(By.ID, element_id)
        return (el.get_attribute("name") or element_id, el.get_attribute("value") or "")
    except Exception:
        return (element_id, "")


def _build_driver():
    options = webdriver.ChromeOptions()
    # Common stability options for both headed/headless runs.
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    if HEADLESS == 1:
        # VPS/headless-safe defaults
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--remote-debugging-port={_debug_port()}")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-software-rasterizer")

        # Optional explicit binary override for VPS
        env_bin = os.environ.get("CHROME_BINARY", "").strip()
        if env_bin and os.path.exists(env_bin):
            options.binary_location = env_bin
        else:
            # Common Linux VPS paths
            linux_candidates = (
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
            )
            for p in linux_candidates:
                if os.path.exists(p):
                    options.binary_location = p
                    break
    else:
        options.binary_location = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    return webdriver.Chrome(options=options)


def _cleanup_stale_chrome_profiles():
    """
    Remove leftover temp Chrome user-data dirs from previous runs.
    """
    tmp_root = tempfile.gettempdir()
    try:
        for name in os.listdir(tmp_root):
            if not name.startswith("igr_chrome_profile_"):
                continue
            path = os.path.join(tmp_root, name)
            if os.path.isdir(path):
                try:
                    shutil.rmtree(path, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass


def _save_pagination_probe_snapshot(driver, tag: str, out_dir: str) -> None:
    """
    Write RegistrationGrid outer HTML + structured pager/ellipsis/link summary for analysis.
    """
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r"[^\w.\-]+", "_", tag).strip("_") or "snap"
    prefix = os.path.join(out_dir, safe)

    try:
        grid = driver.find_element(By.ID, "RegistrationGrid")
        html = grid.get_attribute("outerHTML") or ""
    except Exception as e:
        html = f"<!-- RegistrationGrid missing: {e} -->\n"

    with open(prefix + "_RegistrationGrid_outer.html", "w", encoding="utf-8") as f:
        f.write(html)

    summary = None
    try:
        summary = driver.execute_script(
            """
            var g = document.getElementById('RegistrationGrid');
            if (!g) return {error: 'RegistrationGrid not found'};
            function norm(s) { return (s || '').trim().replace(/\\s+/g, ' '); }
            var links = [];
            var all = g.querySelectorAll('a');
            for (var i = 0; i < all.length; i++) {
                var a = all[i];
                var t = norm(a.textContent);
                var href = a.getAttribute('href') || '';
                if (!t && href.indexOf('doPostBack') < 0 && href.indexOf('Page') < 0) continue;
                links.push({
                    index: i,
                    text: t,
                    href: href.slice(0, 900),
                    displayed: a.offsetParent !== null
                });
            }
            var ell = [];
            var nodes = g.querySelectorAll('tr td, tr th, a, span, label');
            for (var j = 0; j < nodes.length; j++) {
                var el = nodes[j];
                var tx = norm(el.textContent);
                if (tx === '...' || tx === '…' || (tx.length >= 1 && tx.length <= 4 && /^[.…]+$/.test(tx))) {
                    ell.push({
                        tag: el.tagName,
                        text: tx,
                        htmlFragment: (el.outerHTML || '').slice(0, 500)
                    });
                }
            }
            var tables = g.querySelectorAll('table');
            var pagerish = [];
            for (var k = 0; k < tables.length; k++) {
                var tbl = tables[k];
                var cls = (tbl.className || '') + '';
                var ot = (tbl.outerHTML || '');
                if (cls.toLowerCase().indexOf('pager') >= 0 ||
                    ot.indexOf('Page$') >= 0 || ot.indexOf('Page%24') >= 0 ||
                    ot.indexOf('...') >= 0 || ot.indexOf('hellip') >= 0) {
                    pagerish.push({
                        className: cls,
                        outerHTML: ot.slice(0, 8000)
                    });
                }
            }
            return {
                linkCount: links.length,
                links: links,
                ellipsisLikeCells: ell.slice(0, 50),
                tablesThatLookLikePager: pagerish.slice(0, 5),
                gridTextHead: norm(g.innerText).slice(0, 3000)
            };
            """
        )
    except Exception as e:
        summary = {"error": str(e)}

    with open(prefix + "_pagination_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Human-readable link list
    try:
        lines = [f"# {tag}\n"]
        if isinstance(summary, dict) and "links" in summary:
            for L in summary["links"]:
                lines.append(f"- text={L.get('text')!r} displayed={L.get('displayed')} href={L.get('href', '')[:200]!r}...\n")
        with open(prefix + "_pagination_links.txt", "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass

    print(f"[PAGINATION PROBE] wrote {prefix}_* under {out_dir}")


def _pagination_probe_click_ellipsis_in_grid(driver) -> bool:
    """Click first '...' / ellipsis pager control inside RegistrationGrid (next batch of ~10 pages)."""
    try:
        clicked = driver.execute_script(
            """
            var g = document.getElementById('RegistrationGrid');
            if (!g) return false;
            var all = g.querySelectorAll('a');
            for (var i = 0; i < all.length; i++) {
                var a = all[i];
                var t = (a.textContent || '').trim();
                if (t === '...' || t === '…' || (t.length >= 1 && t.length <= 4 && /^[.…]+$/.test(t))) {
                    a.click();
                    return true;
                }
            }
            return false;
            """
        )
        return bool(clicked)
    except Exception:
        return False


def _pagination_probe_click_page_postback(driver, page_num: int) -> bool:
    """Click a pager link whose href contains Page$<page_num> (ASP.NET GridView style)."""
    try:
        clicked = driver.execute_script(
            """
            var n = arguments[0];
            var needle = 'Page$' + n;
            var enc = 'Page%24' + n;
            var g = document.getElementById('RegistrationGrid');
            if (!g) return false;
            var links = g.querySelectorAll('a[href]');
            for (var i = 0; i < links.length; i++) {
                var h = links[i].getAttribute('href') || '';
                if (h.indexOf(needle) >= 0 || h.indexOf(enc) >= 0) {
                    links[i].click();
                    return true;
                }
            }
            return false;
            """,
            int(page_num),
        )
        return bool(clicked)
    except Exception:
        return False


def _run_pagination_probe_sequence(driver, out_dir: str) -> None:
    """
    Capture how pagination is rendered (including ellipsis batches ~every 10 pages).
    """
    print("[PAGINATION PROBE] capturing initial grid / pager HTML…")
    _save_pagination_probe_snapshot(driver, "01_after_search", out_dir)

    if _pagination_probe_click_ellipsis_in_grid(driver):
        print("[PAGINATION PROBE] clicked ellipsis (…); waiting for AJAX…")
        _wait_for_aspnet_ajax_idle(driver, timeout=50)
        time.sleep(0.35)
        _save_pagination_probe_snapshot(driver, "02_after_ellipsis_click", out_dir)
    else:
        print("[PAGINATION PROBE] no ellipsis link found in grid (maybe ≤10 pages or different markup)")

    if _pagination_probe_click_page_postback(driver, 11):
        print("[PAGINATION PROBE] clicked Page$11; waiting for AJAX…")
        _wait_for_aspnet_ajax_idle(driver, timeout=50)
        time.sleep(0.35)
        _save_pagination_probe_snapshot(driver, "03_after_Page_11_click", out_dir)
    else:
        print("[PAGINATION PROBE] no Page$11 link in grid (fewer than 11 pages or ellipsis-only navigation)")

    if _pagination_probe_click_ellipsis_in_grid(driver):
        print("[PAGINATION PROBE] clicked second ellipsis; waiting for AJAX…")
        _wait_for_aspnet_ajax_idle(driver, timeout=50)
        time.sleep(0.35)
        _save_pagination_probe_snapshot(driver, "04_after_second_ellipsis_click", out_dir)


def run_selenium_for_property(property_no: int, village_index: int, pagination_probe_out_dir: str | None = None):
    _cleanup_stale_chrome_profiles()
    profile_dir = tempfile.mkdtemp(prefix="igr_chrome_profile_")
    driver = None
    # Build a per-session browser instance using dedicated user-data-dir.
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir={profile_dir}")
    if HEADLESS == 1:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--remote-debugging-port={_debug_port()}")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-software-rasterizer")

        env_bin = os.environ.get("CHROME_BINARY", "").strip()
        if env_bin and os.path.exists(env_bin):
            options.binary_location = env_bin
        else:
            linux_candidates = (
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
            )
            for p in linux_candidates:
                if os.path.exists(p):
                    options.binary_location = p
                    break
    else:
        options.binary_location = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(URL)

        try:
            popup = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btnclose"))
            )
            popup.click()
            print("Popup closed")
        except Exception:
            pass

        _click_by_id_safe(driver, "btnOtherdistrictSearch")
        WebDriverWait(driver, 20).until(
            lambda d: d.find_element(By.ID, "ddlFromYear1").is_displayed()
        )
        _wait_for_aspnet_ajax_idle(driver, timeout=25)
        print("Entered search form")

        _select_by_visible_text_safe(driver, "ddlFromYear1", YEAR)
        _wait_for_dropdown_population(driver, "ddlDistrict1", timeout=20)
        _wait_for_dropdown_has_index(driver, "ddlDistrict1", DISTRICT_INDEX, timeout=20)
        _wait_for_aspnet_ajax_idle(driver, timeout=35)

        _select_by_index_safe(driver, "ddlDistrict1", DISTRICT_INDEX)
        _wait_for_dropdown_population(driver, "ddltahsil", timeout=25)
        _wait_for_dropdown_has_index(driver, "ddltahsil", TAHSIL_INDEX, timeout=25)
        _wait_for_aspnet_ajax_idle(driver, timeout=35)

        _select_by_index_safe(driver, "ddltahsil", TAHSIL_INDEX)
        _wait_for_dropdown_population(driver, "ddlvillage", timeout=25)
        _wait_for_dropdown_has_index(driver, "ddlvillage", village_index, timeout=25)
        _wait_for_aspnet_ajax_idle(driver, timeout=35)

        _select_by_index_safe(driver, "ddlvillage", village_index)

        year_used = _selected_value_or_text(driver, "ddlFromYear1")
        district_used = _selected_value_or_text(driver, "ddlDistrict1")
        tahsil_used = _selected_value_or_text(driver, "ddltahsil")
        village_used = _selected_value_or_text(driver, "ddlvillage")
        district_name = _selected_text(driver, "ddlDistrict1")
        tahsil_name = _selected_text(driver, "ddltahsil")
        village_name = _selected_text(driver, "ddlvillage")

        _clear_send_keys_safe(driver, "txtAttributeValue1", str(property_no))

        max_dummy_attempts = 4
        for attempt in range(1, max_dummy_attempts + 1):
            old_src = ""
            try:
                old_src = driver.find_element(By.ID, "imgCaptcha_new").get_attribute("src") or ""
            except Exception:
                pass

            _clear_send_keys_safe(driver, "txtImg1", "1")
            _click_by_id_safe(driver, "btnSearch_RestMaha")
            print(f"Dummy captcha submitted (attempt {attempt}/{max_dummy_attempts}), waiting for new captcha...")

            try:
                _wait_for_captcha_loaded(driver, baseline_src=old_src if old_src else None, timeout=35)
            except Exception:
                if attempt == max_dummy_attempts:
                    raise
                _wait_for_captcha_loaded(driver, baseline_src=None, timeout=20)

            print("New captcha fully loaded")
            time.sleep(0.5)
            break

        captcha_text = (solve_captcha(driver) or "").upper()
        print("Captcha:", captcha_text)
        _clear_send_keys_safe(driver, "txtImg1", captcha_text)

        pre_submit_viewstate = ""
        try:
            pre_submit_viewstate = driver.find_element(By.ID, "__VIEWSTATE").get_attribute("value") or ""
        except Exception:
            pass

        _click_by_id_safe(driver, "btnSearch_RestMaha")
        status, message = _wait_for_search_outcome(driver, timeout=120)

        if status == "success":
            print("✅ Search completed — results grid visible")
        elif status == "no_records":
            raise NoRegistrationRecordsError(message or "no registration rows for this property")
        elif status == "message":
            print("ℹ️ Site message after submit:", message)
        elif status == "error":
            print("❌ Search did not complete:", message)
            raise Exception(f"Search failed: {message}")
        else:
            raise Exception("Search timed out waiting for results or error message")

        _wait_hidden_fields_ready(driver, prev_viewstate=pre_submit_viewstate, timeout=30)

        if not _selenium_has_any_registration_records(driver):
            raise NoRegistrationRecordsError("no index-II rows in grid for this property")

        total_pages, pager_moved = _selenium_count_total_pages_via_ellipsis(driver)
        if pager_moved:
            _selenium_ensure_grid_on_page_one(driver, total_pages=total_pages)
        else:
            print("[PAGER] no pager navigation during count — ViewState stays on page 1")
        _wait_hidden_fields_ready(driver, prev_viewstate="", timeout=35)

        _, viewstate = _field(driver, "__VIEWSTATE")
        _, eventvalidation = _field(driver, "__EVENTVALIDATION")
        _, viewstate_gen = _field(driver, "__VIEWSTATEGENERATOR")
        cookies = driver.get_cookies()

        print("✅ State + cookies ready")

        if pagination_probe_out_dir:
            try:
                _run_pagination_probe_sequence(driver, pagination_probe_out_dir)
            except Exception as e:
                print(f"[PAGINATION PROBE] sequence error (partial files may exist): {e}")

        return {
            "year_used": year_used,
            "district_used": district_used,
            "tahsil_used": tahsil_used,
            "village_used": village_used,
            "captcha_used": captcha_text,
            "district_name": district_name,
            "tahsil_name": tahsil_name,
            "village_name": village_name,
            "viewstate": viewstate,
            "viewstate_gen": viewstate_gen,
            "eventvalidation": eventvalidation,
            "cookies": cookies,
            "total_pages": total_pages,
        }
    finally:
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass


def _pager_info_from_text(text: str) -> tuple[int | None, int | None]:
    """
    Parse grid / pager markup. Returns (total_pages_from_label, max_page_button_number).
    Label (e.g. Page 2 of 7) is authoritative; page links are merged upward over responses.
    """
    if not text:
        return None, None
    label_tot = None
    for pat in (
        r"Page\s*(\d+)\s+of\s+(\d+)",
        r"page\s*(\d+)\s*/\s*(\d+)",
        r"(\d+)\s*-\s*\d+\s+of\s+(\d+)",
    ):
        m = re.search(pat, text, re.I)
        if m:
            try:
                cur, tot = int(m.group(1)), int(m.group(2))
                if 1 <= tot <= 5000 and 1 <= cur <= tot:
                    label_tot = tot
                    break
            except ValueError:
                pass
    link_nums = []
    for m in re.finditer(
        r"RegistrationGrid['\"]\s*,\s*['\"]Page\$([0-9]+)",
        text,
        re.I,
    ):
        link_nums.append(int(m.group(1)))
    for m in re.finditer(r"['\"]Page\$([0-9]+)['\"]", text):
        link_nums.append(int(m.group(1)))
    for m in re.finditer(r"Page%24(\d+)", text, re.I):
        link_nums.append(int(m.group(1)))
    link_max = max(link_nums) if link_nums else None
    if link_max is not None and (link_max < 1 or link_max > 5000):
        link_max = None
    return label_tot, link_max


def _extract_hidden_fields_from_msajax_delta(delta_text: str):
    if not delta_text:
        return {}
    parts = delta_text.split("|")
    out = {}
    i = 0
    while i < len(parts) - 2:
        if parts[i] == "hiddenField":
            key = parts[i + 1]
            val = parts[i + 2]
            if key:
                out[key] = val
            i += 3
            continue
        i += 1
    return out


def _is_terminal_page_response(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    return "0|error|500||" in t or "0|error|500|" in t


def _report_visible_text_len(html: str) -> int:
    if not html:
        return 0
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return len(re.sub(r"\s+", " ", t).strip())


def _is_no_data_report_html(text: str) -> bool:
    """Site 'no document' page (wording/casing variants)."""
    if not text:
        return False
    t = re.sub(r"\s+", " ", (text or "").lower())
    if "no data found" not in t:
        return False
    if "document" in t and "database" in t:
        return True
    if "selected database" in t:
        return True
    return False


def _report_get_should_retry(text: str | None, raw_len: int) -> bool:
    """
    True → repeat GET to REPORT_URL only (do not re-post indexII).
    Covers empty/0-byte body, no-data message, and empty report shell HTML.
    """
    text = text or ""
    if raw_len == 0:
        return True
    if not text.strip():
        return True
    if _is_no_data_report_html(text):
        return True
    tl = text.lower()
    if "report.jpg" in tl and "background" in tl and "no data" in tl:
        return True
    # Nearly empty report page: VIEWSTATE shell with almost no visible content
    if "__VIEWSTATE" in text and _report_visible_text_len(text) < 30:
        return True
    return False


def _build_common_payload(state: dict, property_no: int, hidden_state: dict) -> dict:
    return {
        "ScriptManager1": "upRegistrationGrid|RegistrationGrid",
        "ddlFromYear1": state["year_used"] or YEAR,
        "ddlDistrict1": state["district_used"] or str(DISTRICT_INDEX),
        "ddltahsil": state["tahsil_used"] or str(TAHSIL_INDEX),
        "ddlvillage": state["village_used"] or "",
        "txtAttributeValue1": str(property_no),
        "txtImg1": state["captcha_used"] or "",
        "__VIEWSTATE": hidden_state.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": hidden_state.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": hidden_state.get("__EVENTVALIDATION", ""),
        "__ASYNCPOST": "true",
        "__LASTFOCUS": "",
        "FS_PropertyNumber": "",
        "FS_IGR_FLAG": "",
    }


def _safe_part(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "unknown"
    return "".join(ch for ch in s if ch not in '/\\:*?"<>|').strip() or "unknown"


def _save_report_html(state: dict, property_no: int, page_no: int, index_no: int, text: str):
    district_part = _safe_part(state.get("district_name") or str(DISTRICT_INDEX))
    tahsil_part = _safe_part(state.get("tahsil_name") or str(TAHSIL_INDEX))
    village_part = _safe_part(state.get("village_name") or "unknown_village")
    year_part = _safe_part(str(state.get("year_used") or YEAR))

    output_dir = os.path.join("output", district_part, tahsil_part, village_part, year_part)
    os.makedirs(output_dir, exist_ok=True)

    fn = f"report_property_{property_no}_page_{page_no}_index_{index_no}.html"
    path = os.path.join(output_dir, fn)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text or "")


def _session_from_cookies(cookies):
    session = requests.Session()
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if name is not None and value is not None:
            session.cookies.set(name, value)
    return session


def _get_selenium_state_with_retries(property_no: int, village_index: int, context: str):
    """
    Retry Selenium multiple times; if a retry batch fails, start fresh browser
    sessions again while keeping caller state (property/page context).
    """
    last_exc = None
    for batch in range(1, SELENIUM_BATCH_MAX + 1):
        if batch > 1:
            print(f"[SELENIUM NEW SESSION BATCH] property={property_no}, context={context}, batch={batch}/{SELENIUM_BATCH_MAX}")
        for attempt in range(1, PROPERTY_RETRY_MAX + 1):
            try:
                print(
                    f"[SELENIUM START] property={property_no}, context={context}, "
                    f"attempt={attempt}/{PROPERTY_RETRY_MAX}, batch={batch}/{SELENIUM_BATCH_MAX}"
                )
                return run_selenium_for_property(property_no, village_index)
            except NoRegistrationRecordsError:
                raise
            except Exception as e:
                last_exc = e
                print(
                    f"[SELENIUM ERROR] property={property_no}, context={context}, "
                    f"attempt={attempt}/{PROPERTY_RETRY_MAX}, batch={batch}/{SELENIUM_BATCH_MAX}: {e}"
                )
                if attempt < PROPERTY_RETRY_MAX:
                    time.sleep(1.5)
                    print(f"[SELENIUM RETRY] property={property_no}, context={context}")
        # batch failed; move to fresh batch
        if batch < SELENIUM_BATCH_MAX:
            time.sleep(2.0)
    if last_exc:
        raise last_exc
    raise Exception(
        f"Selenium failed for property={property_no}, village_index={village_index}, context={context}"
    )


def _request_with_retry(send_fn, label: str, max_retries: int = HTTP_RETRY_MAX):
    """
    Retry network/server errors (e.g. 504) for the exact same request.
    """
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = send_fn()
            status = getattr(resp, "status_code", None)
            if status is not None and status >= 500:
                print(f"[RETRY] {label} attempt {attempt}/{max_retries} got HTTP {status}")
                if attempt < max_retries:
                    time.sleep(HTTP_RETRY_SLEEP_SEC)
                    continue
            return resp
        except requests.RequestException as e:
            last_exc = e
            print(f"[RETRY] {label} attempt {attempt}/{max_retries} request exception: {e}")
            if attempt < max_retries:
                time.sleep(HTTP_RETRY_SLEEP_SEC)
                continue
            raise
    if last_exc:
        raise last_exc
    return None


def process_property(property_no: int, village_index: int):
    print(f"\n=== PROPERTY {property_no} (village_index={village_index}) ===")
    state = _get_selenium_state_with_retries(
        property_no, village_index, context="initial"
    )
    session = _session_from_cookies(state["cookies"])

    hidden_state = {
        "__VIEWSTATE": state["viewstate"],
        "__VIEWSTATEGENERATOR": state["viewstate_gen"],
        "__EVENTVALIDATION": state["eventvalidation"],
    }

    total_pages_cap = state.get("total_pages")

    def _sync_total_pages_from_state():
        nonlocal total_pages_cap
        total_pages_cap = state.get("total_pages", total_pages_cap)

    if total_pages_cap is not None:
        print(f"[PAGER] HTTP will stop after page {total_pages_cap} (from Selenium for this property)")

    def _build_page_milestones(target_page: int):
        """
        Replay checkpoints in this order:
        21 -> 11,20,21
        41 -> 11,20,21,30,31,40,41
        """
        if target_page <= 1:
            return [target_page]

        milestones = []
        if target_page >= 11:
            milestones.append(11)

        n = 20
        while n <= target_page:
            milestones.append(n)
            if n + 1 <= target_page:
                milestones.append(n + 1)
            n += 10

        if not milestones or milestones[-1] != target_page:
            milestones.append(target_page)
        return milestones

    def _post_page_and_update_hidden(target_page: int):
        payload_page_local = _build_common_payload(state, property_no, hidden_state)
        payload_page_local["__EVENTTARGET"] = "RegistrationGrid"
        payload_page_local["__EVENTARGUMENT"] = f"Page${target_page}"

        response_page_local = _request_with_retry(
            lambda: session.post(URL, data=payload_page_local, headers=headers),
            label=f"page_post property={property_no} page={target_page}",
        )
        print("STATUS(page):", response_page_local.status_code)
        print((response_page_local.text or "")[:500])

        if _is_terminal_page_response(response_page_local.text):
            print(f"[PAGE WARN] property={property_no}, page={target_page} terminal-like response")
            return False, "terminal"

        page_updates_local = _extract_hidden_fields_from_msajax_delta(response_page_local.text)
        if not page_updates_local:
            print(f"[PAGE WARN] property={property_no}, page={target_page} no hidden updates")
            return False, "no_updates"

        hidden_state["__VIEWSTATE"] = page_updates_local.get("__VIEWSTATE", hidden_state["__VIEWSTATE"])
        hidden_state["__VIEWSTATEGENERATOR"] = page_updates_local.get("__VIEWSTATEGENERATOR", hidden_state["__VIEWSTATEGENERATOR"])
        hidden_state["__EVENTVALIDATION"] = page_updates_local.get("__EVENTVALIDATION", hidden_state["__EVENTVALIDATION"])
        return True, "ok"

    def _recover_and_load_page(target_page: int):
        """
        When page post returns terminal-like response unexpectedly, refresh Selenium
        and rebuild milestones (11,21,31,...) to the same target page.
        """
        nonlocal state, session, hidden_state
        for rec_try in range(1, PAGE_RECOVERY_MAX + 1):
            print(
                f"[PAGE RECOVERY] property={property_no}, page={target_page}, "
                f"attempt={rec_try}/{PAGE_RECOVERY_MAX}"
            )
            refresh_state = _get_selenium_state_with_retries(
                property_no,
                village_index,
                context=f"recover_page_{target_page}_try_{rec_try}",
            )
            session = _session_from_cookies(refresh_state["cookies"])
            state = refresh_state
            hidden_state = {
                "__VIEWSTATE": refresh_state["viewstate"],
                "__VIEWSTATEGENERATOR": refresh_state["viewstate_gen"],
                "__EVENTVALIDATION": refresh_state["eventvalidation"],
            }
            _sync_total_pages_from_state()

            milestones = _build_page_milestones(target_page)

            recovery_ok = True
            for milestone_page in milestones:
                print(f"[RECOVERY STEP] property={property_no}, page={milestone_page}")
                ok, reason = _post_page_and_update_hidden(milestone_page)
                if not ok:
                    recovery_ok = False
                    break
            if recovery_ok:
                return True
        return False

    page_no = 1
    while True:
        if total_pages_cap is not None and page_no > total_pages_cap:
            print(
                f"[PAGE END] property={property_no}, past last page ({total_pages_cap} from Selenium)"
            )
            break

        cap_disp = str(total_pages_cap) if total_pages_cap is not None else "?"
        print(f"[PAGE] property={property_no}, page={page_no}/{cap_disp}")
        index_had_activity = False

        for index_no in range(10):
            payload_index = _build_common_payload(state, property_no, hidden_state)
            payload_index["__EVENTTARGET"] = "RegistrationGrid"
            payload_index["__EVENTARGUMENT"] = f"indexII${index_no}"

            response_index = _request_with_retry(
                lambda: session.post(URL, data=payload_index, headers=headers),
                label=f"index_post property={property_no} page={page_no} index={index_no}",
            )
            print(f"STATUS(index {index_no}):", response_index.status_code)
            print((response_index.text or "")[:500])

            if _is_terminal_page_response(response_index.text):
                print(
                    f"[INDEX UNAVAILABLE] property={property_no}, page={page_no}, index={index_no} "
                    f"-> 0|error|500|| (document not available for this index) — next property"
                )
                raise IndexDocumentUnavailableError(
                    f"property={property_no} page={page_no} index={index_no}: indexII returned 0|error|500||"
                )

            idx_updates = _extract_hidden_fields_from_msajax_delta(response_index.text)
            if idx_updates:
                hidden_state["__VIEWSTATE"] = idx_updates.get("__VIEWSTATE", hidden_state["__VIEWSTATE"])
                hidden_state["__VIEWSTATEGENERATOR"] = idx_updates.get("__VIEWSTATEGENERATOR", hidden_state["__VIEWSTATEGENERATOR"])
                hidden_state["__EVENTVALIDATION"] = idx_updates.get("__EVENTVALIDATION", hidden_state["__EVENTVALIDATION"])

            response_doc = None
            for get_try in range(1, REPORT_GET_MAX_ATTEMPTS + 1):
                response_doc = _request_with_retry(
                    lambda: session.get(
                        REPORT_URL,
                        headers={"User-Agent": "Mozilla/5.0", "Referer": URL},
                    ),
                    label=(
                        f"report_get property={property_no} page={page_no} "
                        f"index={index_no} get={get_try}/{REPORT_GET_MAX_ATTEMPTS}"
                    ),
                )
                print("STATUS(report):", getattr(response_doc, "status_code", None))

                body = (response_doc.text if response_doc else "") or ""
                raw = response_doc.content if response_doc else b""
                raw_len = len(raw) if raw is not None else 0

                if not _report_get_should_retry(body, raw_len):
                    break

                print(
                    f"[REPORT GET RETRY] property={property_no} page={page_no} index={index_no} "
                    f"GET {get_try}/{REPORT_GET_MAX_ATTEMPTS} (empty/no-data/shell — GET only, no index re-post)"
                )

                if get_try < REPORT_GET_MAX_ATTEMPTS:
                    if get_try == REPORT_GET_MAX_ATTEMPTS - 1:
                        time.sleep(REPORT_GET_RETRY_SLEEP_SEC + 0.65)
                    else:
                        time.sleep(REPORT_GET_RETRY_SLEEP_SEC)

            _save_report_html(state, property_no, page_no, index_no, response_doc.text if response_doc else "")
            index_had_activity = True

        next_page = page_no + 1

        if total_pages_cap is not None and next_page > total_pages_cap:
            print(
                f"[PAGE END] property={property_no}, completed {total_pages_cap} page(s) "
                f"(Selenium total — not requesting page {next_page})"
            )
            break

        # At 11, 21, 31... refresh browser/session to avoid session drops.
        if next_page > 1 and (next_page % 10 == 1):
            print(f"[SESSION REFRESH] property={property_no}, target_page={next_page}")
            refresh_state = _get_selenium_state_with_retries(
                property_no, village_index, context=f"refresh_to_page_{next_page}"
            )
            session = _session_from_cookies(refresh_state["cookies"])
            state = refresh_state
            hidden_state = {
                "__VIEWSTATE": refresh_state["viewstate"],
                "__VIEWSTATEGENERATOR": refresh_state["viewstate_gen"],
                "__EVENTVALIDATION": refresh_state["eventvalidation"],
            }
            _sync_total_pages_from_state()

            # Rebuild page state in steps: 11, 21, 31 ... up to target page.
            milestones = _build_page_milestones(next_page)
            refresh_ok = True
            for milestone_page in milestones:
                print(f"[REFRESH PAGE STEP] property={property_no}, page={milestone_page}")
                ok, reason = _post_page_and_update_hidden(milestone_page)
                if not ok:
                    # terminal-like response here can be transient; recover once more
                    if reason == "terminal" and _recover_and_load_page(milestone_page):
                        continue
                    refresh_ok = False
                    break
            if not refresh_ok:
                break

            # We are now positioned at next_page; continue with index loop on this page.
            page_no = next_page
            continue

        ok, reason = _post_page_and_update_hidden(next_page)
        if not ok:
            if reason == "terminal":
                if _recover_and_load_page(next_page):
                    page_no = next_page
                    continue
            break

        page_no = next_page
        if not index_had_activity and page_no > 1:
            print(f"[PAGE END] property={property_no}, no index activity")
            break


def _discover_village_indices():
    """
    Discover all usable village dropdown indices for selected year/district/tahsil.
    """
    last_exc = None
    for attempt in range(1, 4):
        driver = _build_driver()
        try:
            print(f"[VILLAGE DISCOVERY] attempt {attempt}/3")
            driver.get(URL)

            try:
                popup = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".btnclose"))
                )
                popup.click()
            except Exception:
                pass

            # Site is flaky in headless mode; retry opening search form once after refresh.
            opened = False
            for open_try in range(1, 3):
                try:
                    _click_by_id_safe(driver, "btnOtherdistrictSearch")
                    WebDriverWait(driver, 20).until(
                        lambda d: d.find_element(By.ID, "ddlFromYear1").is_displayed()
                    )
                    _wait_for_aspnet_ajax_idle(driver, timeout=25)
                    opened = True
                    break
                except Exception:
                    if open_try == 1:
                        driver.refresh()
                        time.sleep(1.2)
                        try:
                            popup = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btnclose"))
                            )
                            popup.click()
                        except Exception:
                            pass
                        continue
                    raise

            if not opened:
                raise TimeoutException("Could not open search form")

            _select_by_visible_text_safe(driver, "ddlFromYear1", YEAR)
            _wait_for_dropdown_population(driver, "ddlDistrict1", timeout=20)
            _wait_for_dropdown_has_index(driver, "ddlDistrict1", DISTRICT_INDEX, timeout=20)
            _wait_for_aspnet_ajax_idle(driver, timeout=35)

            _select_by_index_safe(driver, "ddlDistrict1", DISTRICT_INDEX)
            _wait_for_dropdown_population(driver, "ddltahsil", timeout=25)
            _wait_for_dropdown_has_index(driver, "ddltahsil", TAHSIL_INDEX, timeout=25)
            _wait_for_aspnet_ajax_idle(driver, timeout=35)

            _select_by_index_safe(driver, "ddltahsil", TAHSIL_INDEX)
            _wait_for_dropdown_population(driver, "ddlvillage", timeout=30)
            _wait_for_aspnet_ajax_idle(driver, timeout=35)

            indices = []
            last_stale = None
            for _ in range(8):
                try:
                    sel = Select(driver.find_element(By.ID, "ddlvillage"))
                    for idx, opt in enumerate(sel.options):
                        txt = (opt.text or "").strip().lower()
                        val = (opt.get_attribute("value") or "").strip()
                        if idx == 0:
                            continue
                        if not txt:
                            continue
                        if "select" in txt:
                            continue
                        # Keep valid options even if value is text/empty-ish on this site.
                        if not val and len(txt) < 2:
                            continue
                        indices.append(idx)
                    return indices
                except StaleElementReferenceException as e:
                    last_stale = e
                    time.sleep(0.35)
            if last_stale:
                raise last_stale
            return indices
        except Exception as e:
            last_exc = e
            print(f"[VILLAGE DISCOVERY RETRY] attempt {attempt}/3 failed: {e}")
            time.sleep(1.5)
        finally:
            try:
                driver.quit()
            except Exception:
                pass
    raise last_exc


def main():
    village_indices = _discover_village_indices()
    if not village_indices:
        print("[STOP] No village indices found for given year/district/tahsil.")
        return

    print(f"[VILLAGES] discovered {len(village_indices)} indices: {village_indices}")
    for village_index in village_indices:
        print(f"\n=== VILLAGE START index={village_index} ===")
        for property_no in range(PROPERTY_START, PROPERTY_END + 1):
            try:
                print(f"[PROPERTY START] property={property_no}, village_index={village_index}")
                process_property(property_no, village_index)
            except IndexDocumentUnavailableError as e:
                print(
                    f"[NEXT PROPERTY] property={property_no}, village_index={village_index} "
                    f"(index document unavailable): {e}"
                )
                continue
            except NoRegistrationRecordsError as e:
                print(
                    f"[NO RECORDS — NEXT PROPERTY] property={property_no}, "
                    f"village_index={village_index}: {e}"
                )
                continue
            except Exception as e:
                print(f"[PROPERTY SKIP] property={property_no}, village_index={village_index} failed: {e}")
                continue


if __name__ == "__main__":
    main()
