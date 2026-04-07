import os
import re
import sys
import time
import base64
import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# ==============================
# CONFIG
# ==============================
URL = "https://freesearchigrservice.maharashtra.gov.in/"
CAPTCHA_API_KEY = os.environ.get(
    "CAPTCHA_API_KEY",
    "CAP-03DD9281E150148DCB0705A6F665CF337303C5FDC399749D977BEAC6CD398191",
).strip()
REPORT_URL = "https://freesearchigrservice.maharashtra.gov.in/isaritaHTMLReportSuchiKramank2_RegLive.aspx"
# Browser opens HtmlReport.aspx after index click; session-backed report GET sometimes needs a fallback.
REPORT_URL_ALT = os.environ.get(
    "IGR_REPORT_URL_ALT",
    urljoin(URL, "HtmlReport.aspx"),
).strip()

headers_ajax = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "X-MicrosoftAjax": "Delta=true",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://freesearchigrservice.maharashtra.gov.in",
    "Referer": "https://freesearchigrservice.maharashtra.gov.in/",
    "Accept": "*/*",
}

headers_get = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HEADLESS = int(sys.argv[1]) if len(sys.argv) > 1 else 1
YEAR = sys.argv[2] if len(sys.argv) > 2 else "2020"
DISTRICT_INDEX = int(sys.argv[3]) if len(sys.argv) > 3 else 1
TAHSIL_INDEX = int(sys.argv[4]) if len(sys.argv) > 4 else 1

PROPERTY_START = 0
PROPERTY_END = 9
PROPERTY_RETRY_MAX = 3
BOOTSTRAP_BATCH_MAX = 4
HTTP_RETRY_MAX = 4
HTTP_RETRY_SLEEP_SEC = 2.0
PAGE_RECOVERY_MAX = 3
REPORT_NO_DATA_RETRY_MAX = 3
REPORT_NO_DATA_RETRY_SLEEP_SEC = 0.3

print(
    f"HEADLESS(ignored)={HEADLESS}, YEAR={YEAR}, D={DISTRICT_INDEX}, "
    f"T={TAHSIL_INDEX}, V=AUTO, PROPS={PROPERTY_START}-{PROPERTY_END}"
)

# Raw response dumps (GET landing → first index document). Set IGR_HTTP_TRACE=0 to disable.
HTTP_TRACE_DIR = os.environ.get("IGR_HTTP_TRACE_DIR", "http_trace")
HTTP_TRACE_ENABLED = os.environ.get("IGR_HTTP_TRACE", "1").strip() not in ("0", "false", "no")

# Log each request on one line: bracket tag + status + up to 200 chars req/srsp previews.
HTTP_LOG_PREVIEW = 200

_http_counter = 0


def _next_http_id() -> int:
    global _http_counter
    _http_counter += 1
    return _http_counter


def _preview(s: str, n: int = HTTP_LOG_PREVIEW) -> str:
    if not s:
        return ""
    one = s.replace("\r", " ").replace("\n", " ")
    return one if len(one) <= n else one[: n - 3] + "..."


def _compact_post_body(data: dict) -> str:
    if not data:
        return ""
    parts = []
    for k in sorted(data.keys()):
        v = data[k]
        if k in ("__VIEWSTATE", "__EVENTVALIDATION"):
            parts.append(f"{k}=<{len(str(v))}ch>")
        else:
            sv = str(v)
            if len(sv) > 48:
                sv = sv[:45] + "..."
            parts.append(f"{k}={sv}")
    return _preview(" ".join(parts), HTTP_LOG_PREVIEW)


def _response_flags(text: str) -> list:
    flags = []
    if not text:
        flags.append("empty")
        return flags
    if "0|error|500" in text:
        flags.append("MSAJAX_500")
    if "RegistrationGrid" in text:
        flags.append("grid")
    if "|updatePanel|" in text or text.lstrip().startswith("1|"):
        flags.append("delta")
    if "Handler.ashx" in text:
        flags.append("handler")
    return flags


def _log_http_line(tag: str, resp: requests.Response, req_summary: str = "") -> None:
    hid = _next_http_id()
    req = resp.request
    method = getattr(req, "method", "?")
    text = resp.text if resp.text is not None else ""
    flags = _response_flags(text)
    print(
        f"[HTTP #{hid}] {tag} {method} status={resp.status_code} len={len(text)} "
        f"flags={flags} req={_preview(req_summary)} rsp={_preview(text)}"
    )


def _dump_raw_http(tag: str, resp: requests.Response) -> None:
    if not HTTP_TRACE_ENABLED:
        return
    try:
        os.makedirs(HTTP_TRACE_DIR, exist_ok=True)
        
        clean_tag = tag.replace("[", "").replace("]", "").replace(":", "_")
        req = resp.request
        
        # Dump Request
        req_lines = [f"{req.method} {req.path_url} HTTP/1.1"]
        
        # Add Host header if not present
        if "Host" not in req.headers:
            from urllib.parse import urlparse
            parsed_url = urlparse(req.url)
            req_lines.append(f"Host: {parsed_url.netloc}")
            
        for k, v in req.headers.items():
            req_lines.append(f"{k}: {v}")
        req_lines.append("")
        if req.body:
            if isinstance(req.body, bytes):
                req_lines.append(req.body.decode('utf-8', errors='replace'))
            else:
                req_lines.append(str(req.body))
                
        with open(os.path.join(HTTP_TRACE_DIR, f"{clean_tag}_req.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(req_lines))
            
        # Dump Response
        res_lines = [f"HTTP/1.1 {resp.status_code} {resp.reason}"]
        for k, v in resp.headers.items():
            res_lines.append(f"{k}: {v}")
        res_lines.append("")
        if resp.content:
            try:
                res_lines.append(resp.content.decode('utf-8'))
            except UnicodeDecodeError:
                res_lines.append(f"<Binary data: {len(resp.content)} bytes>")
                
        with open(os.path.join(HTTP_TRACE_DIR, f"{clean_tag}_res.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(res_lines))
    except Exception as e:
        print(f"[DUMP ERROR] Failed to dump {tag}: {e}")


def _http_get(session: requests.Session, tag: str, url: str, headers=None, timeout=60) -> requests.Response:
    r = session.get(url, headers=headers, timeout=timeout)
    _dump_raw_http(tag, r)
    ct = (r.headers.get("Content-Type") or "").lower()
    if "image" in ct or (r.content and r.content[:4] in (b"GIF8", b"GIF9", b"\xff\xd8\xff")):
        hid = _next_http_id()
        head = r.content[:16].hex() if r.content else ""
        print(
            f"[HTTP #{hid}] {tag} GET status={r.status_code} binary_len={len(r.content or b'')} hex16={head}"
        )
        return r
    _log_http_line(tag, r, "")
    return r


def _http_post(
    session: requests.Session,
    tag: str,
    url: str,
    data=None,
    headers=None,
    timeout=60,
) -> requests.Response:
    summary = _compact_post_body(data) if isinstance(data, dict) else _preview(str(data), HTTP_LOG_PREVIEW)
    r = session.post(url, data=data, headers=headers, timeout=timeout)
    _dump_raw_http(tag, r)
    _log_http_line(tag, r, summary)
    return r




def _form_to_dict(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="form1")
    if not form:
        raise ValueError("form1 not found in HTML")
    data = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        t = (inp.get("type") or "text").lower()
        if t in ("submit", "image", "button"):
            continue
        data[name] = inp.get("value") or ""
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        data[name] = opt.get("value") if opt else ""
    for ta in form.find_all("textarea"):
        name = ta.get("name")
        if name:
            data[name] = (ta.string or "")
    return data


def _parse_hidden_inputs(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for hid in soup.find_all("input", type="hidden"):
        name = hid.get("name")
        if name:
            out[name] = hid.get("value") or ""
    return out


_HIDDEN_FIELD_DELTA_RE = re.compile(r"(\d+)\|hiddenField\|([^|]+)\|")


def _extract_hidden_fields_from_msajax_delta(delta_text: str):
    """Parse hiddenField entries from an MS-AJAX delta. Values are length-prefixed and may contain '|'."""
    if not delta_text:
        return {}
    out = {}
    pos = 0
    while True:
        m = _HIDDEN_FIELD_DELTA_RE.search(delta_text, pos)
        if not m:
            break
        ln = int(m.group(1))
        key = m.group(2)
        start = m.end()
        end = start + ln
        val = delta_text[start:end] if end <= len(delta_text) else delta_text[start:]
        if key:
            out[key] = val
        pos = end if end <= len(delta_text) else len(delta_text)
    if out:
        return out
    parts = delta_text.split("|")
    i = 0
    while i < len(parts) - 2:
        if parts[i] == "hiddenField":
            k = parts[i + 1]
            v = parts[i + 2]
            if k:
                out[k] = v
            i += 3
            continue
        i += 1
    return out


def _is_msajax_delta(text: str) -> bool:
    if not text:
        return False
    s = text.lstrip()
    if s.startswith("1|") or s.startswith("0|"):
        return True
    return "|updatePanel|" in text or "|hiddenField|" in text


def _merge_hidden_from_response(text: str, fd: dict) -> None:
    if not text:
        return
    if _is_msajax_delta(text):
        for k, v in _extract_hidden_fields_from_msajax_delta(text).items():
            fd[k] = v
    else:
        for k, v in _parse_hidden_inputs(text).items():
            if k in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__EVENTTARGET", "__EVENTARGUMENT", "__LASTFOCUS"):
                fd[k] = v


def _upmain_fragment(delta_text: str) -> str:
    marker = "updatePanel|UpMain|"
    i = delta_text.find(marker)
    if i == -1:
        return ""
    rest = delta_text[i + len(marker) :]
    j = rest.find("|updatePanel|")
    if j == -1:
        j = rest.find("|hiddenField|")
    return rest[:j] if j != -1 else rest


def _collect_fields_from_html_snippet(html: str) -> dict:
    """Parse input/select/textarea from an HTML fragment (e.g. UpMain update panel)."""
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        t = (inp.get("type") or "text").lower()
        if t in ("submit", "image", "button"):
            continue
        data[name] = inp.get("value") or ""
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        data[name] = opt.get("value") if opt else ""
    for ta in soup.find_all("textarea"):
        name = ta.get("name")
        if name:
            data[name] = (ta.string or "")
    return data


def _grid_form_baseline_from_search_response(delta_text: str) -> dict:
    """Full field snapshot from UpMain after successful search — closer to browser grid POSTs."""
    frag = _upmain_fragment(delta_text or "")
    if not frag:
        return {}
    return _collect_fields_from_html_snippet(frag)


def _parse_select_options(html_fragment: str, select_id: str):
    soup = BeautifulSoup(html_fragment, "html.parser")
    sel = soup.find("select", id=select_id)
    if not sel:
        return []
    return sel.find_all("option")


def _option_label(opt) -> str:
    return (opt.text or "").strip()


def _post_open_rest_of_maharashtra(session: requests.Session, fd: dict, dump_trace: bool = False) -> str:
    r2 = _ajax_upmain(session, fd, "btnOtherdistrictSearch", "[rest_maharashtra]")
    r2.raise_for_status()
    if "ddlFromYear1" not in r2.text:
        print("[BOOTSTRAP WARN] ddlFromYear1 not in open-form response; snippet:", (r2.text or "")[:1200])
    return r2.text


def _ajax_upmain(session: requests.Session, fd: dict, target: str, log_tag=None) -> requests.Response:
    payload_parts = []
    
    if target == "btnOtherdistrictSearch":
        payload_parts.append(f"ScriptManager1=UpMain%7C{target}")
        payload_parts.append("__EVENTTARGET=")
        payload_parts.append("__EVENTARGUMENT=")
        payload_parts.append("__LASTFOCUS=")
        for key in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
            if key in fd:
                payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
        for key in ["ddlFromYear", "ddlDistrict", "txtAreaName", "ddlareaname", "txtAttributeValue", "txtImg"]:
            if key in fd:
                payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
        payload_parts.append("FS_PropertyNumber=")
        payload_parts.append("FS_IGR_FLAG=")
        payload_parts.append("__ASYNCPOST=true")
        payload_parts.append("btnOtherdistrictSearch=Rest%20of%20Maharashtra%20%2F%20%E0%A4%89%E0%A4%B0%E0%A5%8D%E0%A4%B5%E0%A4%B0%E0%A4%BF%E0%A4%A4%20%E0%A4%AE%E0%A4%B9%E0%A4%BE%E0%A4%B0%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%9F%E0%A5%8D%E0%A4%B0")
    elif target == "btnSearch_RestMaha":
        payload_parts.append(f"ScriptManager1=UpMain%7C{target}")
        for key in ["ddlFromYear1", "ddlDistrict1", "ddltahsil", "ddlvillage", "txtAttributeValue1", "txtImg1", "FS_PropertyNumber", "FS_IGR_FLAG"]:
            if key in fd:
                payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
        payload_parts.append(f"__EVENTTARGET=")
        payload_parts.append("__EVENTARGUMENT=")
        payload_parts.append("__LASTFOCUS=")
        for key in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
            if key in fd:
                payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
        payload_parts.append("__ASYNCPOST=true")
        payload_parts.append("btnSearch_RestMaha=%E0%A4%B6%E0%A5%8B%E0%A4%A7%20%2F%20Search")
    else:
        payload_parts.append(f"ScriptManager1=UpMain%7C{target}")
        for key in ["ddlFromYear1", "ddlDistrict1", "ddltahsil", "ddlvillage", "txtAttributeValue1", "txtImg1", "FS_PropertyNumber", "FS_IGR_FLAG"]:
            if key in fd:
                payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
        payload_parts.append(f"__EVENTTARGET={target}")
        payload_parts.append("__EVENTARGUMENT=")
        payload_parts.append("__LASTFOCUS=")
        for key in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
            if key in fd:
                payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
        payload_parts.append("__ASYNCPOST=true")
        
    payload_str = "&".join(payload_parts)
    
    tag = log_tag or {
        "ddlFromYear1": "[year]",
        "ddlDistrict1": "[district]",
        "ddltahsil": "[tahsil]",
        "ddlvillage": "[village]",
        "btnSearch_RestMaha": "[search]",
    }.get(target, f"[ajax:{target}]")
    
    return _http_post(
        session,
        tag,
        URL,
        data=payload_str,
        headers=headers_ajax,
        timeout=60,
    )


def _extract_handler_path(text: str) -> str:
    m = re.search(r"Handler\.ashx\?txt=[^\s\"'&<>]+", text)
    return m.group(0) if m else ""


def solve_captcha_image_b64(img_b64: str) -> str:
    task = {
        "clientKey": CAPTCHA_API_KEY,
        "task": {"type": "ImageToTextTask", "body": img_b64},
    }
    hid = _next_http_id()
    r = requests.post("https://api.capsolver.com/createTask", json=task, timeout=60)
    print(
        f"[HTTP #{hid}] [capsolver_create] POST status={r.status_code} "
        f"req=b64_len={len(img_b64)} rsp={_preview(r.text)}"
    )
    jr = r.json()
    if jr.get("status") == "ready":
        return jr["solution"]["text"]
    task_id = jr.get("taskId")
    if not task_id:
        raise RuntimeError(f"CapSolver task creation failed: {jr}")
    start = time.time()
    n = 0
    while True:
        if time.time() - start > 90:
            raise RuntimeError("Captcha solve timeout")
        time.sleep(2)
        n += 1
        hid2 = _next_http_id()
        res = requests.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": CAPTCHA_API_KEY, "taskId": task_id},
            timeout=60,
        )
        print(
            f"[HTTP #{hid2}] [capsolver_poll] POST status={res.status_code} try={n} "
            f"rsp={_preview(res.text)}"
        )
        jres = res.json()
        if jres.get("status") == "ready":
            return jres["solution"]["text"]


def _response_has_results_grid(text: str) -> bool:
    if "RegistrationGrid" in text:
        return True
    frag = _upmain_fragment(text)
    return "RegistrationGrid" in frag


def _cookies_as_list(session: requests.Session):
    out = []
    for c in session.cookies:
        out.append({"name": c.name, "value": c.value, "domain": getattr(c, "domain", "") or "", "path": c.path or "/"})
    return out


def _bootstrap_form_to_village_options(session: requests.Session, dump_trace: bool = False):
    # First get the landing page to get the base form data
    r = _http_get(session, "[landing]", URL, headers=headers_get, timeout=60)
    r.raise_for_status()
    fd = _form_to_dict(r.text)
    
    # Then post to open Rest of Maharashtra
    html = _post_open_rest_of_maharashtra(session, fd, dump_trace=dump_trace)
    
    _merge_hidden_from_response(html, fd)

    # Add the fields that are expected in the next request
    fd["ddlFromYear1"] = str(YEAR)
    fd["ddlDistrict1"] = "---Select District----"
    fd["ddltahsil"] = "---Select Tahsil----"
    fd["ddlvillage"] = "-----Select Village----"
    fd["txtAttributeValue1"] = ""
    fd["txtImg1"] = ""
    fd["FS_PropertyNumber"] = ""
    fd["FS_IGR_FLAG"] = ""

    r_y = _ajax_upmain(session, fd, "ddlFromYear1")
    _merge_hidden_from_response(r_y.text, fd)
    frag_y = _upmain_fragment(r_y.text)
    dopts = _parse_select_options(frag_y or r_y.text, "ddlDistrict1")
    if len(dopts) <= DISTRICT_INDEX:
        raise RuntimeError(f"district options too few: need index {DISTRICT_INDEX}, got {len(dopts)}")
    district_name = _option_label(dopts[DISTRICT_INDEX])
    fd["ddlDistrict1"] = dopts[DISTRICT_INDEX].get("value") or ""

    r_d = _ajax_upmain(session, fd, "ddlDistrict1")
    _merge_hidden_from_response(r_d.text, fd)
    frag_d = _upmain_fragment(r_d.text)
    topts = _parse_select_options(frag_d or r_d.text, "ddltahsil")
    if len(topts) <= TAHSIL_INDEX:
        raise RuntimeError(f"tahsil options too few: need index {TAHSIL_INDEX}, got {len(topts)}")
    tahsil_name = _option_label(topts[TAHSIL_INDEX])
    fd["ddltahsil"] = topts[TAHSIL_INDEX].get("value") or ""

    r_t = _ajax_upmain(session, fd, "ddltahsil")
    _merge_hidden_from_response(r_t.text, fd)
    frag_t = _upmain_fragment(r_t.text)
    vopts = _parse_select_options(frag_t or r_t.text, "ddlvillage")
    return fd, vopts, district_name, tahsil_name


def bootstrap_search_state(property_no: int, village_index: int) -> dict:
    session = requests.Session()
    fd, vopts, district_name, tahsil_name = _bootstrap_form_to_village_options(session, dump_trace=True)
    if len(vopts) <= village_index:
        raise RuntimeError(f"village options too few: need index {village_index}, got {len(vopts)}")

    vopt = vopts[village_index]
    # 1) Dummy search to trigger captcha generation
    fd["ddlvillage"] = vopt.get("value") or ""
    fd["txtAttributeValue1"] = str(property_no)
    fd["txtImg1"] = "1"

    r_dummy = _ajax_upmain(session, fd, "btnSearch_RestMaha", "[search_dummy]")
    _merge_hidden_from_response(r_dummy.text, fd)

    # 2) Extract captcha handler URL and solve it
    handler = _extract_handler_path(r_dummy.text)
    if not handler:
        print("[BOOTSTRAP WARN] no Handler.ashx in dummy response:", (r_dummy.text or "")[:1500])
        raise RuntimeError("Captcha handler URL not found after dummy search")

    cap_url = handler if handler.startswith("http") else urljoin(URL, handler.lstrip("/"))
    gr = _http_get(
        session,
        "[captcha_gif]",
        cap_url,
        headers={"User-Agent": headers_get["User-Agent"], "Referer": URL},
        timeout=60,
    )
    gr.raise_for_status()
    img_b64 = base64.b64encode(gr.content).decode("ascii")
    captcha_text = (solve_captcha_image_b64(img_b64) or "").upper()
    print("Captcha solved:", captcha_text)

    # 3) Real search with solved captcha
    fd["txtImg1"] = captcha_text
    r_final = _ajax_upmain(session, fd, "btnSearch_RestMaha", "[search_real]")
    _merge_hidden_from_response(r_final.text, fd)

    if not _response_has_results_grid(r_final.text):
        if "lblMsgCTS1" in r_final.text:
            soup = BeautifulSoup(r_final.text, "html.parser")
            lbl = soup.find(id="lblMsgCTS1")
            msg = lbl.text if lbl else ""
            if "invalid captcha" in msg.lower() or "wrong captcha" in msg.lower():
                raise RuntimeError(f"Invalid captcha: {msg}")
            print(f"[BOOTSTRAP WARN] No records found for property={property_no} (msg: {msg.strip()})")
            return None # Indicate no records
        print("[BOOTSTRAP FAIL] search response snippet:", (r_final.text or "")[:2000])
        raise RuntimeError("Search did not return RegistrationGrid (captcha or validation failed)")

    village_name = _option_label(vopt)
    grid_form_baseline = _grid_form_baseline_from_search_response(r_final.text)
    if grid_form_baseline:
        print(f"[BOOTSTRAP] grid_form_baseline keys={len(grid_form_baseline)} (browser-like grid POSTs)")
    else:
        print("[BOOTSTRAP WARN] grid_form_baseline empty — grid AJAX uses minimal field set only")

    if HTTP_TRACE_ENABLED:
        print(
            f"[http_trace] bootstrap responses saved under {os.path.abspath(HTTP_TRACE_DIR)}/ "
            "(login_response … captcha_real_response; first index dumps written in process_property)"
        )

    return {
        "year_used": str(YEAR),
        "district_used": fd.get("ddlDistrict1", ""),
        "tahsil_used": fd.get("ddltahsil", ""),
        "village_used": fd.get("ddlvillage", ""),
        "captcha_used": captcha_text,
        "district_name": district_name,
        "tahsil_name": tahsil_name,
        "village_name": village_name,
        "viewstate": fd.get("__VIEWSTATE", ""),
        "viewstate_gen": fd.get("__VIEWSTATEGENERATOR", ""),
        "eventvalidation": fd.get("__EVENTVALIDATION", ""),
        "cookies": _cookies_as_list(session),
        "grid_form_baseline": grid_form_baseline,
    }


def _get_bootstrap_state_with_retries(property_no: int, village_index: int, context: str):
    last_exc = None
    for batch in range(1, BOOTSTRAP_BATCH_MAX + 1):
        if batch > 1:
            print(f"[BOOTSTRAP NEW BATCH] property={property_no}, context={context}, batch={batch}/{BOOTSTRAP_BATCH_MAX}")
        for attempt in range(1, PROPERTY_RETRY_MAX + 1):
            try:
                print(
                    f"[BOOTSTRAP START] property={property_no}, village_index={village_index}, "
                    f"context={context}, attempt={attempt}/{PROPERTY_RETRY_MAX}, batch={batch}/{BOOTSTRAP_BATCH_MAX}"
                )
                res = bootstrap_search_state(property_no, village_index)
                if res is None:
                    return None
                return res
            except Exception as e:
                last_exc = e
                print(
                    f"[BOOTSTRAP ERROR] property={property_no}, context={context}, "
                    f"attempt={attempt}/{PROPERTY_RETRY_MAX}: {e}"
                )
                if attempt < PROPERTY_RETRY_MAX:
                    time.sleep(1.5)
                    print(f"[BOOTSTRAP RETRY] property={property_no}, context={context}")
        if batch < BOOTSTRAP_BATCH_MAX:
            time.sleep(2.0)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Bootstrap failed for property={property_no}, village_index={village_index}, context={context}")


def _is_terminal_page_response(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    return "0|error|500||" in t or "0|error|500|" in t


def _is_no_data_report_html(text: str) -> bool:
    t = (text or "").lower()
    return "no data found for this document number in selected database" in t


def _hidden_triple_from_state(hidden_state: dict) -> dict:
    """Latest __VIEWSTATE / __VIEWSTATEGENERATOR / __EVENTVALIDATION for grid AJAX posts."""
    return {
        "__VIEWSTATE": hidden_state.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": hidden_state.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": hidden_state.get("__EVENTVALIDATION", ""),
    }


def _format_grid_payload(state: dict, property_no: int, hidden_state: dict, target: str, argument: str) -> str:
    sm = "ScriptManager1=tupRegistrationGrid%7CRegistrationGrid"
    overlay = {
        "ddlFromYear1": state["year_used"] or YEAR,
        "ddlDistrict1": state["district_used"] or str(DISTRICT_INDEX),
        "ddltahsil": state["tahsil_used"] or str(TAHSIL_INDEX),
        "ddlvillage": state["village_used"] or "",
        "txtAttributeValue1": str(property_no),
        "txtImg1": state["captcha_used"] or "",
        "FS_PropertyNumber": "",
        "FS_IGR_FLAG": "",
        "__EVENTTARGET": target,
        "__EVENTARGUMENT": argument,
        "__LASTFOCUS": "",
        "__VIEWSTATE": hidden_state.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": hidden_state.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": hidden_state.get("__EVENTVALIDATION", ""),
    }

    baseline = state.get("grid_form_baseline")
    if isinstance(baseline, dict) and baseline:
        merged = dict(baseline)
        merged.update(overlay)
        merged.pop("ScriptManager1", None)
        for k in ("btnSearch_RestMaha", "btnOtherdistrictSearch"):
            merged.pop(k, None)
        parts = [sm]
        for k, v in merged.items():
            parts.append(f"{k}={requests.utils.quote(str(v), safe='')}")
        if "__ASYNCPOST" not in merged:
            parts.append("__ASYNCPOST=true")
        return "&".join(parts)

    payload_parts = [sm]
    fd = {k: overlay[k] for k in overlay if k not in ("__EVENTTARGET", "__EVENTARGUMENT", "__LASTFOCUS", "__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")}
    for key in ["ddlFromYear1", "ddlDistrict1", "ddltahsil", "ddlvillage", "txtAttributeValue1", "txtImg1", "FS_PropertyNumber", "FS_IGR_FLAG"]:
        payload_parts.append(f"{key}={requests.utils.quote(str(fd[key]), safe='')}")
    payload_parts.append(f"__EVENTTARGET={requests.utils.quote(target, safe='')}")
    payload_parts.append(f"__EVENTARGUMENT={requests.utils.quote(argument, safe='')}")
    payload_parts.append("__LASTFOCUS=")
    triple = _hidden_triple_from_state(hidden_state)
    for key in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        if key in triple:
            payload_parts.append(f"{key}={requests.utils.quote(str(triple[key]), safe='')}")
    payload_parts.append("__ASYNCPOST=true")
    return "&".join(payload_parts)


def _safe_part(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "unknown"
    return "".join(ch for ch in s if ch not in '/\\:*?"<>|').strip() or "unknown"


def _get_report_document(session: requests.Session, property_no: int, page_no: int, index_no: int):
    """GET report HTML after grid index post; try alternate URL if primary returns no-data stub."""
    referer_headers = {"User-Agent": "Mozilla/5.0", "Referer": URL}
    r = _http_get(session, "[report]", REPORT_URL, headers=referer_headers)
    if not _is_no_data_report_html(r.text):
        return r
    if REPORT_URL_ALT.rstrip("/") != REPORT_URL.rstrip("/"):
        return _http_get(session, "[report_alt]", REPORT_URL_ALT, headers=referer_headers)
    return r


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


def _request_with_retry(send_fn, label: str, max_retries: int = HTTP_RETRY_MAX):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = send_fn()
            status = getattr(resp, "status_code", None)
            text = getattr(resp, "text", "") or ""
            if status is not None and status >= 500:
                print(f"[RETRY] {label} attempt {attempt}/{max_retries} got HTTP {status}")
                if attempt < max_retries:
                    time.sleep(HTTP_RETRY_SLEEP_SEC)
                    continue
            if status is not None and status < 500 and "0|error|500" in text:
                print(
                    f"[RETRY] {label} attempt {attempt}/{max_retries} MS-AJAX 0|error|500 in response body"
                )
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
    state = _get_bootstrap_state_with_retries(property_no, village_index, context="initial")
    if state is None:
        print(f"[SKIP] Property {property_no} has no records or invalid captcha.")
        return

    session = _session_from_cookies(state["cookies"])

    hidden_state = {
        "__VIEWSTATE": state["viewstate"],
        "__VIEWSTATEGENERATOR": state["viewstate_gen"],
        "__EVENTVALIDATION": state["eventvalidation"],
    }

    # Search (`[search_real]`) already returns MS-AJAX with RegistrationGrid for **page 1**.
    # hidden_state holds the post-search triple; we run indexII$0..9 against that state — no Page$1 POST.
    def _build_page_milestones(target_page: int):
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
        payload_page_local = _format_grid_payload(state, property_no, hidden_state, "RegistrationGrid", f"Page${target_page}")

        response_page_local = _request_with_retry(
            lambda pp=payload_page_local, tp=target_page: _http_post(
                session,
                "[grid_page]",
                URL,
                data=pp,
                headers=headers_ajax,
            ),
            label=f"page_post property={property_no} page={target_page}",
        )

        if _is_terminal_page_response(response_page_local.text):
            print(f"[PAGE WARN] property={property_no}, page={target_page} terminal-like response")
            return False, "terminal"

        page_updates_local = _extract_hidden_fields_from_msajax_delta(response_page_local.text)
        if not page_updates_local:
            print(f"[PAGE WARN] property={property_no}, page={target_page} no hidden updates")
            return False, "no_updates"

        hidden_state["__VIEWSTATE"] = page_updates_local.get("__VIEWSTATE", hidden_state["__VIEWSTATE"])
        hidden_state["__VIEWSTATEGENERATOR"] = page_updates_local.get(
            "__VIEWSTATEGENERATOR", hidden_state["__VIEWSTATEGENERATOR"]
        )
        hidden_state["__EVENTVALIDATION"] = page_updates_local.get("__EVENTVALIDATION", hidden_state["__EVENTVALIDATION"])
        return True, "ok"

    def _recover_and_load_page(target_page: int):
        nonlocal state, session, hidden_state
        for rec_try in range(1, PAGE_RECOVERY_MAX + 1):
            print(f"[PAGE RECOVERY] property={property_no}, page={target_page}, attempt={rec_try}/{PAGE_RECOVERY_MAX}")
            refresh_state = _get_bootstrap_state_with_retries(
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
        print(f"[PAGE] property={property_no}, page={page_no}")
        if page_no == 1:
            print(
                "[grid] page 1: grid already loaded after search; "
                "using bootstrap hidden triple for index posts (no Page$1)"
            )
        index_had_activity = False

        for index_no in range(10):
            payload_index = _format_grid_payload(state, property_no, hidden_state, "RegistrationGrid", f"indexII${index_no}")

            response_index = _request_with_retry(
                lambda pi=payload_index, pgn=page_no, ix=index_no: _http_post(
                    session,
                    "[grid_index]",
                    URL,
                    data=pi,
                    headers=headers_ajax,
                ),
                label=f"index_post property={property_no} page={page_no} index={index_no}",
            )

            if _is_terminal_page_response(response_index.text):
                print(f"[INDEX STOP] property={property_no}, page={page_no}, index={index_no} -> terminal response")
                break

            idx_updates = _extract_hidden_fields_from_msajax_delta(response_index.text)
            if idx_updates:
                hidden_state["__VIEWSTATE"] = idx_updates.get("__VIEWSTATE", hidden_state["__VIEWSTATE"])
                hidden_state["__VIEWSTATEGENERATOR"] = idx_updates.get(
                    "__VIEWSTATEGENERATOR", hidden_state["__VIEWSTATEGENERATOR"]
                )
                hidden_state["__EVENTVALIDATION"] = idx_updates.get("__EVENTVALIDATION", hidden_state["__EVENTVALIDATION"])

            response_doc = None
            for report_try in range(1, REPORT_NO_DATA_RETRY_MAX + 1):
                response_doc = _request_with_retry(
                    lambda: _get_report_document(session, property_no, page_no, index_no),
                    label=(
                        f"report_get property={property_no} page={page_no} "
                        f"index={index_no} try={report_try}"
                    ),
                )

                if response_doc is not None and not _is_no_data_report_html(response_doc.text):
                    break

                print(
                    f"[REPORT RETRY] No-data response for property={property_no}, "
                    f"page={page_no}, index={index_no}, try={report_try}/{REPORT_NO_DATA_RETRY_MAX}"
                )

                if report_try < REPORT_NO_DATA_RETRY_MAX:
                    if report_try == REPORT_NO_DATA_RETRY_MAX - 1:
                        time.sleep(REPORT_NO_DATA_RETRY_SLEEP_SEC + 0.7)
                    else:
                        time.sleep(REPORT_NO_DATA_RETRY_SLEEP_SEC)

            if HTTP_TRACE_ENABLED and page_no == 1 and index_no == 0 and response_doc is not None:
                print(
                    f"[http_trace] first index document GET saved under {os.path.abspath(HTTP_TRACE_DIR)}/"
                )

            _save_report_html(state, property_no, page_no, index_no, response_doc.text if response_doc else "")
            index_had_activity = True

        next_page = page_no + 1
        if next_page > 1 and (next_page % 10 == 1):
            print(f"[SESSION REFRESH] property={property_no}, target_page={next_page}")
            refresh_state = _get_bootstrap_state_with_retries(
                property_no, village_index, context=f"refresh_to_page_{next_page}"
            )
            session = _session_from_cookies(refresh_state["cookies"])
            state = refresh_state
            hidden_state = {
                "__VIEWSTATE": refresh_state["viewstate"],
                "__VIEWSTATEGENERATOR": refresh_state["viewstate_gen"],
                "__EVENTVALIDATION": refresh_state["eventvalidation"],
            }

            milestones = _build_page_milestones(next_page)
            refresh_ok = True
            for milestone_page in milestones:
                print(f"[REFRESH PAGE STEP] property={property_no}, page={milestone_page}")
                ok, reason = _post_page_and_update_hidden(milestone_page)
                if not ok:
                    if reason == "terminal" and _recover_and_load_page(milestone_page):
                        continue
                    refresh_ok = False
                    break
            if not refresh_ok:
                break

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
    last_exc = None
    for attempt in range(1, 4):
        try:
            print(f"[VILLAGE DISCOVERY] attempt {attempt}/3 (HTTP)")
            session = requests.Session()
            _, vopts, _, _ = _bootstrap_form_to_village_options(session)
            indices = []
            for idx, opt in enumerate(vopts):
                txt = (opt.text or "").strip().lower()
                val = (opt.get("value") or "").strip()
                if idx == 0:
                    continue
                if not txt:
                    continue
                if "select" in txt:
                    continue
                if not val and len(txt) < 2:
                    continue
                indices.append(idx)
            return indices
        except Exception as e:
            last_exc = e
            print(f"[VILLAGE DISCOVERY RETRY] attempt {attempt}/3 failed: {e}")
            time.sleep(1.5)
    raise last_exc if last_exc else RuntimeError("village discovery failed")


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
            except Exception as e:
                print(f"[PROPERTY SKIP] property={property_no}, village_index={village_index} failed: {e}")
                continue


if __name__ == "__main__":
    main()
