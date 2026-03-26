import os
import sys
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
VILLAGE_INDEX = int(sys.argv[5]) if len(sys.argv) > 5 else 1

PROPERTY_START = 0
PROPERTY_END = 9
PROPERTY_RETRY_MAX = 3
SELENIUM_BATCH_MAX = 4
HTTP_RETRY_MAX = 4
HTTP_RETRY_SLEEP_SEC = 2.0

print(
    f"HEADLESS={HEADLESS}, YEAR={YEAR}, D={DISTRICT_INDEX}, "
    f"T={TAHSIL_INDEX}, V={VILLAGE_INDEX}, PROPS={PROPERTY_START}-{PROPERTY_END}"
)


def solve_captcha(driver):
    print("Solving captcha...")
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


def _selected_value_or_text(driver, select_id):
    sel = Select(driver.find_element(By.ID, select_id))
    opt = sel.first_selected_option
    val = opt.get_attribute("value")
    if val is not None and val != "":
        return val
    return (opt.text or "").strip()


def _selected_text(driver, select_id):
    sel = Select(driver.find_element(By.ID, select_id))
    return (sel.first_selected_option.text or "").strip()


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
    start = time.time()
    time.sleep(1)
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
                    return ("message", txt)
        except Exception:
            pass

        msg = _any_visible_error_text(driver)
        if msg:
            return ("error", msg)

        if time.time() - start > timeout:
            return ("timeout", None)
        time.sleep(0.25)


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
        options.add_argument("--remote-debugging-port=9222")
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


def run_selenium_for_property(property_no: int):
    driver = _build_driver()
    wait = WebDriverWait(driver, 20)
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

        wait.until(EC.element_to_be_clickable((By.ID, "btnOtherdistrictSearch"))).click()
        WebDriverWait(driver, 20).until(
            lambda d: d.find_element(By.ID, "ddlFromYear1").is_displayed()
        )
        print("Entered search form")

        Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_visible_text(YEAR)
        _wait_for_dropdown_population(driver, "ddlDistrict1", timeout=20)
        _wait_for_dropdown_has_index(driver, "ddlDistrict1", DISTRICT_INDEX, timeout=20)

        Select(driver.find_element(By.ID, "ddlDistrict1")).select_by_index(DISTRICT_INDEX)
        _wait_for_dropdown_population(driver, "ddltahsil", timeout=25)
        _wait_for_dropdown_has_index(driver, "ddltahsil", TAHSIL_INDEX, timeout=25)

        wait.until(EC.element_to_be_clickable((By.ID, "ddltahsil")))
        Select(driver.find_element(By.ID, "ddltahsil")).select_by_index(TAHSIL_INDEX)
        _wait_for_dropdown_population(driver, "ddlvillage", timeout=25)
        _wait_for_dropdown_has_index(driver, "ddlvillage", VILLAGE_INDEX, timeout=25)

        wait.until(EC.element_to_be_clickable((By.ID, "ddlvillage")))
        Select(driver.find_element(By.ID, "ddlvillage")).select_by_index(VILLAGE_INDEX)

        year_used = _selected_value_or_text(driver, "ddlFromYear1")
        district_used = _selected_value_or_text(driver, "ddlDistrict1")
        tahsil_used = _selected_value_or_text(driver, "ddltahsil")
        village_used = _selected_value_or_text(driver, "ddlvillage")
        district_name = _selected_text(driver, "ddlDistrict1")
        tahsil_name = _selected_text(driver, "ddltahsil")
        village_name = _selected_text(driver, "ddlvillage")

        prop_input = driver.find_element(By.ID, "txtAttributeValue1")
        prop_input.clear()
        prop_input.send_keys(str(property_no))

        max_dummy_attempts = 4
        for attempt in range(1, max_dummy_attempts + 1):
            old_src = ""
            try:
                old_src = driver.find_element(By.ID, "imgCaptcha_new").get_attribute("src") or ""
            except Exception:
                pass

            cap_box = wait.until(EC.element_to_be_clickable((By.ID, "txtImg1")))
            cap_box.clear()
            cap_box.send_keys("1")
            driver.find_element(By.ID, "btnSearch_RestMaha").click()
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
        cap_input = driver.find_element(By.ID, "txtImg1")
        cap_input.clear()
        cap_input.send_keys(captcha_text)

        pre_submit_viewstate = ""
        try:
            pre_submit_viewstate = driver.find_element(By.ID, "__VIEWSTATE").get_attribute("value") or ""
        except Exception:
            pass

        driver.find_element(By.ID, "btnSearch_RestMaha").click()
        status, message = _wait_for_search_outcome(driver, timeout=120)

        if status == "success":
            print("✅ Search completed")
        elif status == "message":
            print("ℹ️ Site message after submit:", message)
        elif status == "error":
            print("❌ Search did not complete:", message)
            raise Exception(f"Search failed: {message}")
        else:
            raise Exception("Search timed out waiting for results or error message")

        _wait_hidden_fields_ready(driver, prev_viewstate=pre_submit_viewstate, timeout=30)

        _, viewstate = _field(driver, "__VIEWSTATE")
        _, eventvalidation = _field(driver, "__EVENTVALIDATION")
        _, viewstate_gen = _field(driver, "__VIEWSTATEGENERATOR")
        cookies = driver.get_cookies()

        print("✅ State + cookies ready")

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
        }
    finally:
        try:
            driver.quit()
        except Exception:
            pass


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


def _build_common_payload(state: dict, property_no: int, hidden_state: dict) -> dict:
    return {
        "ScriptManager1": "upRegistrationGrid|RegistrationGrid",
        "ddlFromYear1": state["year_used"] or YEAR,
        "ddlDistrict1": state["district_used"] or str(DISTRICT_INDEX),
        "ddltahsil": state["tahsil_used"] or str(TAHSIL_INDEX),
        "ddlvillage": state["village_used"] or str(VILLAGE_INDEX),
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
    village_part = _safe_part(state.get("village_name") or str(VILLAGE_INDEX))
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


def _get_selenium_state_with_retries(property_no: int, context: str):
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
                return run_selenium_for_property(property_no)
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
    raise Exception(f"Selenium failed for property={property_no}, context={context}")


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


def process_property(property_no: int):
    print(f"\n=== PROPERTY {property_no} ===")
    state = _get_selenium_state_with_retries(property_no, context="initial")
    session = _session_from_cookies(state["cookies"])

    hidden_state = {
        "__VIEWSTATE": state["viewstate"],
        "__VIEWSTATEGENERATOR": state["viewstate_gen"],
        "__EVENTVALIDATION": state["eventvalidation"],
    }

    page_no = 1
    while True:
        print(f"[PAGE] property={property_no}, page={page_no}")
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
                print(f"[INDEX STOP] property={property_no}, page={page_no}, index={index_no} -> terminal response")
                break

            idx_updates = _extract_hidden_fields_from_msajax_delta(response_index.text)
            if idx_updates:
                hidden_state["__VIEWSTATE"] = idx_updates.get("__VIEWSTATE", hidden_state["__VIEWSTATE"])
                hidden_state["__VIEWSTATEGENERATOR"] = idx_updates.get("__VIEWSTATEGENERATOR", hidden_state["__VIEWSTATEGENERATOR"])
                hidden_state["__EVENTVALIDATION"] = idx_updates.get("__EVENTVALIDATION", hidden_state["__EVENTVALIDATION"])

            response_doc = _request_with_retry(
                lambda: session.get(
                    REPORT_URL,
                    headers={"User-Agent": "Mozilla/5.0", "Referer": URL},
                ),
                label=f"report_get property={property_no} page={page_no} index={index_no}",
            )
            print("STATUS(report):", response_doc.status_code)
            _save_report_html(state, property_no, page_no, index_no, response_doc.text)
            index_had_activity = True

        next_page = page_no + 1
        # At 11, 21, 31... refresh browser/session to avoid session drops.
        if next_page > 1 and (next_page % 10 == 1):
            print(f"[SESSION REFRESH] property={property_no}, target_page={next_page}")
            refresh_state = _get_selenium_state_with_retries(
                property_no, context=f"refresh_to_page_{next_page}"
            )
            session = _session_from_cookies(refresh_state["cookies"])
            state = refresh_state
            hidden_state = {
                "__VIEWSTATE": refresh_state["viewstate"],
                "__VIEWSTATEGENERATOR": refresh_state["viewstate_gen"],
                "__EVENTVALIDATION": refresh_state["eventvalidation"],
            }

        payload_page = _build_common_payload(state, property_no, hidden_state)
        payload_page["__EVENTTARGET"] = "RegistrationGrid"
        payload_page["__EVENTARGUMENT"] = f"Page${next_page}"

        response_page = _request_with_retry(
            lambda: session.post(URL, data=payload_page, headers=headers),
            label=f"page_post property={property_no} page={next_page}",
        )
        print("STATUS(page):", response_page.status_code)
        print((response_page.text or "")[:500])

        if _is_terminal_page_response(response_page.text):
            print(f"[PAGE END] property={property_no}, next_page={next_page} terminal response")
            break

        page_updates = _extract_hidden_fields_from_msajax_delta(response_page.text)
        if not page_updates:
            print(f"[PAGE END] property={property_no}, next_page={next_page} no hidden updates")
            break

        hidden_state["__VIEWSTATE"] = page_updates.get("__VIEWSTATE", hidden_state["__VIEWSTATE"])
        hidden_state["__VIEWSTATEGENERATOR"] = page_updates.get("__VIEWSTATEGENERATOR", hidden_state["__VIEWSTATEGENERATOR"])
        hidden_state["__EVENTVALIDATION"] = page_updates.get("__EVENTVALIDATION", hidden_state["__EVENTVALIDATION"])

        page_no = next_page
        if not index_had_activity and page_no > 1:
            print(f"[PAGE END] property={property_no}, no index activity")
            break


def main():
    for property_no in range(PROPERTY_START, PROPERTY_END + 1):
        try:
            print(f"[PROPERTY START] property={property_no}")
            process_property(property_no)
        except Exception as e:
            print(f"[PROPERTY SKIP] property={property_no} failed: {e}")
            continue


if __name__ == "__main__":
    main()
