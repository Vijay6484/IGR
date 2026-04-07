from __future__ import annotations

import json
import os
import re
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
# NOTE: PDFs are downloaded serially for reliability.
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from local_captcha_solver import solve_captcha_with_tesseract_from_bytes



BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
FIRST_GET_PATH = "/eDisplay/Propertydetails/index"
CAPTCHA_PATH = "/eDisplay/captcha-image"
SEARCH_POST_PATH = "/eDisplay/Propertydetails/index"

TRACE_DIR = "http_trace"

# Per (village, free_text): max rounds of GET page + captcha + Tesseract + POST until success.
TESSERACT_CAPTCHA_MAX_ATTEMPTS = 100

# After PDF download failures: full re-run (captcha + search + PDFs) with new IP, same village/free_text.
# Env MAX_PDF_FULL_RETRY_ROUNDS overrides (default 20).

# --- IP rotation (VPS): set one or more of ---
# PROXY_LIST=http://user:pass@host:port,...  (comma-separated; cycles on each rotate)
# ROTATE_IP_COMMAND="sudo systemctl restart tor"  or VPN reconnect, etc.
# ROTATE_IP_SCRIPT=/path/to/rotate.sh          (bash; executable)
# Tor-only mode (no PROXY_LIST):
# - USE_TOR=1 (routes via TOR_SOCKS_PROXY; default socks5h://127.0.0.1:9050)
# - TOR_ROTATE_COMMAND can be used as fallback rotate command (default: sudo systemctl restart tor)
# India-only egress (recommended for IGR): REQUIRE_INDIA_EGRESS=1 or REQUIRED_EGRESS_COUNTRY=IN
# EGRESS_COUNTRY_VERIFY_MAX_ATTEMPTS=5       (retries per _rotate_ip when country wrong)

_proxy_index = 0

FIRSTGET_HEADERS = {
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Sec-Gpc": "1",
    "Accept-Language": "en-GB,en;q=0.5",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Accept-Encoding": "gzip, deflate, br",
    "Priority": "u=0, i",
    "Connection": "keep-alive",
}

CAPTCHA_HEADERS = {
    "Sec-Ch-Ua-Platform": '"Android"',
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"
    ),
    "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Sec-Gpc": "1",
    "Accept-Language": "en-GB,en;q=0.5",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Dest": "image",
    "Referer": "https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index",
    "Accept-Encoding": "gzip, deflate, br",
    "Priority": "i",
    "Connection": "keep-alive",
}

POST_HEADERS = {
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Origin": "https://pay2igr.igrmaharashtra.gov.in",
    "Content-Type": "application/x-www-form-urlencoded",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Sec-Gpc": "1",
    "Accept-Language": "en-GB,en;q=0.5",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Referer": "https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index",
    "Accept-Encoding": "gzip, deflate, br",
    "Priority": "u=0, i",
    "Connection": "keep-alive",
}


def _cookie_header_from_session(sess: requests.Session) -> str:
    # Match example ordering: csrf_token first, then PHPSESSID if present.
    c = sess.cookies.get_dict()
    parts: list[str] = []
    if "csrf_token" in c:
        parts.append(f"csrf_token={c['csrf_token']}")
    if "PHPSESSID" in c:
        parts.append(f"PHPSESSID={c['PHPSESSID']}")
    for k, v in c.items():
        if k in {"csrf_token", "PHPSESSID"}:
            continue
        parts.append(f"{k}={v}")
    return "; ".join(parts)


def _ensure_trace_dir() -> str:
    os.makedirs(TRACE_DIR, exist_ok=True)
    return TRACE_DIR


def _safe_trace_tag(tag: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", tag).strip("_") or "trace"


def _write_http_request(path: str, prep: requests.PreparedRequest) -> None:
    # Format matches res_req_example/*_request.txt
    url = requests.utils.urlparse(prep.url)
    req_path = url.path or "/"
    if url.query:
        req_path += f"?{url.query}"

    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(f"{prep.method} {req_path} HTTP/1.1\n")
        f.write(f"Host: {url.netloc}\n")
        for k, v in prep.headers.items():
            if k.lower() == "host":
                continue
            f.write(f"{k}: {v}\n")
        f.write("\n")
        body = prep.body
        if body is None:
            return
        if isinstance(body, bytes):
            try:
                f.write(body.decode("utf-8", errors="replace"))
            except Exception:
                f.write("<binary body>\n")
        else:
            f.write(str(body))


def _write_http_response(
    path: str,
    resp: requests.Response,
    *,
    body_text: str | None = None,
    body_binary_path: str | None = None,
) -> None:
    # Format matches res_req_example/*_response.txt
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(f"HTTP/1.1 {resp.status_code} {resp.reason}\n")
        for k, v in resp.headers.items():
            f.write(f"{k}: {v}\n")
        f.write("\n")
        if body_binary_path:
            f.write(f"<binary body saved to {body_binary_path}>\n")
        else:
            if body_text is not None:
                f.write(body_text)
            else:
                ct = (resp.headers.get("Content-Type") or "").lower()
                # For streamed responses (e.g. PDFs), resp.content may be unavailable after consumption.
                clen = resp.headers.get("Content-Length") or "unknown"
                f.write(f"<binary body not saved; Content-Type={ct or 'unknown'}; Content-Length={clen}>\n")


def _trace_pair(
    tag: str,
    prep: requests.PreparedRequest,
    resp: requests.Response,
    *,
    binary_body_ext: str | None = None,
) -> None:
    _ensure_trace_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = _safe_trace_tag(tag)

    req_path = os.path.join(TRACE_DIR, f"{ts}_{safe}_request.txt")
    res_path = os.path.join(TRACE_DIR, f"{ts}_{safe}_response.txt")

    _write_http_request(req_path, prep)

    body_bin_path: str | None = None
    body_text: str | None = None
    if binary_body_ext:
        body_bin_path = os.path.join(TRACE_DIR, f"{ts}_{safe}{binary_body_ext}")
        with open(body_bin_path, "wb") as bf:
            bf.write(resp.content)
    else:
        ct = (resp.headers.get("Content-Type") or "").lower()
        if "text" in ct or "html" in ct or "json" in ct or ct == "":
            body_text = resp.text
        else:
            body_text = None

    _write_http_response(res_path, resp, body_text=body_text, body_binary_path=body_bin_path)

village_dict = {
    0: "अवसरेनगर",
    1: "अष्टापूर",
    2: "अहिरे",
    3: "आकुर्डी",
    4: "आगळंबे",
    5: "आतकरवाडी",
    6: "आंबी",
    7: "आंबेगांव खुर्द",
    8: "आंबेगांव बु ाा",
    9: "आर्वी",
    10: "आळंदी म्हातोबाची",
    11: "आव्हाळवाडी",
    12: "उंडरी",
    13: "उरळी कांचन",
    14: "उरळी देवाची",
    15: "एरंडवणा",
    16: "औताडे हाडेवाडी",
    17: "औंध",
    18: "कदम",
    19: "कदमवाकवस्ती",
    20: "कल्याण",
    21: "कळस",
    22: "कसबा पेठ",
    23: "कात्रज",
    24: "काळेवाडी",
    25: "किन्हई",
    26: "किरकटवाडी",
    27: "किवळे (ंमाळवाडी )",
    28: "कुंजीरवाडी",
    29: "कुडजे",
    30: "केसनंद",
    31: "कोंढवा खुर्द",
    32: "कोंढवा बुद्रुक",
    33: "कोंढवे धावडे",
    34: "कोथरूड",
    35: "कोपरे",
    36: "कोरेगांव मूळ",
    37: "कोलवडी",
    38: "कोळेवाडी",
    39: "कोेंढणपूर",
    40: "खडकवाडी",
    41: "खडकवासला",
    42: "खडकी",
    43: "खराडी (पुणे महापालिकेमध्ये समाविष्ट)",
    44: "खाडेवाडी",
    45: "खानापूर",
    46: "खामगांव टेक",
    47: "खामगांव मावळ",
    48: "खेडशिवापूर",
    49: "गंज पेठ (महात्मा फुले पेठ)",
    50: "गणेश पेठ",
    51: "गावडेवाडी",
    52: "गुजरनिंबाळकरवाडी",
    53: "गुरूवार पेठ",
    54: "गुलटेकडी",
    55: "गोगलवाडी",
    56: "गोऱ्हे खुर्द",
    57: "गोऱ्हे बुद्रुक",
    58: "गौडदरा",
    59: "घेरासिंहगड",
    60: "घोरपडी",
    61: "घोरपडी पेठ",
    62: "चऱ्होली बुद्रुक",
    63: "चिखली",
    64: "चिंचवड",
    65: "चिंचोळी",
    66: "चोवीसवाडी",
    67: "जांभळी",
    68: "जांभुळवाडी",
    69: "टिकेकरवाडी",
    70: "टिळेकरवाडी",
    71: "डुडुळगांव",
    72: "डोंगरगांव",
    73: "डोणजे",
    74: "तरडे",
    75: "तळवडे",
    76: "तळेरानवाडी",
    77: "ताथवडे",
    78: "तानाजीनगर",
    79: "तुळापुर",
    80: "थेऊर",
    81: "थेरगांव",
    82: "थोपटेवाडी",
    83: "दापोडी",
    84: "दिघी",
    85: "देहुगांव",
    86: "देहुरोड-कँन्टोमेंट",
    87: "धनकवडी",
    88: "धानोरी",
    89: "धायरी",
    90: "नऱ्हे",
    91: "नांदेड",
    92: "नांदोशी",
    93: "नाना पेठ",
    94: "नायगांव",
    95: "नारायण पेठ",
    96: "निगडी",
    97: "निरगुडी",
    98: "न्हावी सांडस",
    99: "पर्वती",
    100: "पाषाण",
    101: "पिंपरी-कॅम्प",
    102: "पिंपरी वाघेरे",
    103: "पिंपरी सांडस",
    104: "पिंपळे गुरव",
    105: "पिंपळे निलख",
    106: "पिंपळे सौदागर",
    107: "पिसोली",
    108: "पुणे कॅन्टोमेंट एरिया",
    109: "पुनवळे",
    110: "पेठ",
    111: "पेरणे",
    112: "फुरसुंगी",
    113: "फुलगांव",
    114: "बकोरी",
    115: "बहुली",
    116: "बाणेर",
    117: "बालेवाडी",
    118: "बावधन खुर्द",
    119: "बावधन बुद्रुक",
    120: "बिबवेवाडी",
    121: "बुधवार पेठ",
    122: "बुरकेगांव",
    123: "बोपखेल",
    124: "बोपोडी",
    125: "बोऱ्हाडवाडी",
    126: "भगतवाडी",
    127: "भवरापूर",
    128: "भवानी पेठ",
    129: "भावडी",
    130: "भिलारेवाडी",
    131: "भिवरी",
    132: "भोसरी",
    133: "मंगळवार पेठ",
    134: "मनेरवाडी",
    135: "मलिनगर",
    136: "महंमदवाडी",
    137: "महाळुंगे",
    138: "मांगडेवाडी",
    139: "मांजरी खुर्द",
    140: "मांजरी बुद्रुक",
    141: "मांडवी खुर्द",
    142: "मांडवी बुद्रुक",
    143: "माथाळवाडी",
    144: "मामुरडी",
    145: "माळखेड",
    146: "माळीनगर",
    147: "मुंढवा",
    148: "मोकरवाडी",
    149: "मोगरवाडी",
    150: "मोदरवाडी",
    151: "मोशी",
    152: "येरवडा",
    153: "येवलेवाडी",
    154: "रविवार पेठ",
    155: "रहाटवडे",
    156: "रामनगर",
    157: "रावेत",
    158: "रास्ता पेठ",
    159: "राहाटणी",
    160: "राहाटणी/काळेवाडी",
    161: "लोणीकंद",
    162: "लोणीकाळभोर",
    163: "लोहगांव",
    164: "वडकी",
    165: "वडगांव खुर्द",
    166: "वडगांव बुद्रुक",
    167: "वडगांवशिंदे",
    168: "वडगांव शेरी",
    169: "वडाची वाडी",
    170: "वडूखुर्द",
    171: "वदमुखवाडी",
    172: "वरदाडे",
    173: "वळती",
    174: "वाकड",
    175: "वाघोली (आव्हाळवाडी)",
    176: "वांजळेवाडी",
    177: "वाडेबोल्हाई",
    178: "वानवडी",
    179: "वारजे",
    180: "वासवेवाडी",
    181: "विठ्ठलनगर",
    182: "शनिवार पेठ",
    183: "शिंदवणे",
    184: "शिंदेवाडी",
    185: "शिरसवाडी (मुरकुटेनगर)",
    186: "शिवणे",
    187: "शिवाजीनगर (भांबुर्डा)",
    188: "शुक्रवार पेठ",
    189: "शेवाळेवाडी",
    190: "श्रीप्रयागधाम",
    191: "सणसनगर",
    192: "सणसवाडी",
    193: "सदाशिव पेठ/नवी पेठ",
    194: "सांगरूण",
    195: "सांगवी",
    196: "सांगवी सांडस",
    197: "सांबरेवाडी",
    198: "साष्टे",
    199: "सिरसवडी",
    200: "सुतारवाडी",
    201: "सुस",
    202: "सोनापूर",
    203: "सोमवार पेठ",
    204: "सोरतापवाडी",
    205: "हडपसर",
    206: "हिंगणगांव (शिंदेवाडी)",
    207: "हिंगणे खुर्द",
    208: "हिंगणे बु ाा (म.कर्वे नगर)",
    209: "होळकरवाडी"
}


taluka_dict = {
    5: "आंबेगांव",
    8: "इंदापूर",
    12: "खेड",
    13: "जुन्नर",
    6: "दौंड",
    14: "पुणे शहर",
    4: "पुरंदर",
    7: "बारामती",
    9: "भोर",
    10: "मावळ",
    2: "मुळशी",
    3: "वेल्हा",
    11: "शिरुर",
    1: "हवेली"
}

# Using the same example values for now (you said you'll provide later).
DEFAULT_FORM_VALUES: dict[str, str] = {
    "years": "3",
    "district_id": "23",
    "taluka_id": "1",
    "village_id": "3",
    "article_id": "",
    "free_text": "1",
    "partyname": "",
    "dist_name": "पुणे",
    "tal_name": "हवेली",
    "article_name": "",
    "village_name": "आकुर्डी",
    "freetext": "",
    "yearsel": "2025",
}


@dataclass(frozen=True)
class PdfRow:
    serial: int | None
    filename_base: str
    url: str
    out_dir: str


def _default_headers(referer_path: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
    }
    if referer_path:
        headers["Referer"] = urljoin(BASE_URL, referer_path)
        headers["Origin"] = BASE_URL
    return headers


def _extract_csrf_hidden(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one('input[name="_csrfToken"]')
    if not el or not el.get("value"):
        raise RuntimeError("Could not find hidden input _csrfToken in first page HTML.")
    return str(el["value"])


def _has_invalid_captcha(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    msg = soup.select_one("div.message.error")
    if not msg:
        return False
    text = msg.get_text(" ", strip=True).lower()
    return "captcha" in text and ("invalid" in text or "code" in text)


def _has_daily_search_limit_exceeded(html: str) -> bool:
    """Site returns e.g. div.message.warning: daily search results limit exceeded."""
    low = html.lower()
    if "exceeded the limit of daily search" in low:
        return True
    soup = BeautifulSoup(html, "html.parser")
    for div in soup.select("div.message.warning"):
        t = div.get_text(" ", strip=True).lower()
        if "daily" in t and ("limit" in t or "exceed" in t):
            return True
        if "search" in t and "limit" in t and "exceed" in t:
            return True
    return False


def _proxy_urls() -> list[str]:
    raw = os.environ.get("PROXY_LIST", "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _tor_enabled() -> bool:
    return os.getenv("USE_TOR", "").strip().lower() in ("1", "true", "yes")


def _tor_socks_proxy() -> str:
    # socks5h ensures DNS resolution happens through Tor.
    return os.environ.get("TOR_SOCKS_PROXY", "").strip() or "socks5h://127.0.0.1:9050"


def _expected_egress_country() -> str | None:
    """ISO 3166-1 alpha-2 (e.g. IN). Empty = do not verify."""
    if os.getenv("REQUIRE_INDIA_EGRESS", "").strip().lower() in ("1", "true", "yes"):
        return "IN"
    raw = os.environ.get("REQUIRED_EGRESS_COUNTRY", "").strip().upper()
    if not raw or raw in ("0", "FALSE", "NO", "OFF"):
        return None
    return raw[:2]


def _fetch_egress_country(session: requests.Session) -> str | None:
    """Detect public egress country using the same proxies as `session`."""
    for url in (
        "https://ipapi.co/json/",
        "https://ifconfig.co/country",
    ):
        try:
            r = session.get(url, timeout=25)
            if r.status_code != 200:
                continue
            if url.endswith("/json/"):
                j = r.json()
                c = j.get("country_code") or j.get("country")
                if c and isinstance(c, str) and len(c) >= 2:
                    return c.upper()[:2]
            else:
                t = r.text.strip().upper()
                if len(t) == 2 and t.isalpha():
                    return t
        except Exception:
            continue
    return None


def _apply_proxy_to_session(session: requests.Session) -> None:
    global _proxy_index
    urls = _proxy_urls()
    if not urls:
        if _tor_enabled():
            u = _tor_socks_proxy()
            session.proxies = {"http": u, "https": u}
            return
        session.proxies = {}
        return
    u = urls[_proxy_index % len(urls)]
    session.proxies = {"http": u, "https": u}
    print(f"Using HTTP proxy index {_proxy_index % len(urls)} ({u[:60]}...)", file=sys.stderr)


def _new_session_with_proxy() -> requests.Session:
    sess = requests.Session()
    _apply_proxy_to_session(sess)
    need = _expected_egress_country()
    if not need:
        return sess
    cc = _fetch_egress_country(sess)
    if cc == need:
        return sess
    print(
        f"Initial egress country {cc or '(unknown)'} != required {need}; rotating...",
        file=sys.stderr,
    )
    _rotate_ip(sess)
    return sess


def _rotate_ip(session: requests.Session) -> None:
    """Run optional VPN/proxy hooks, cycle PROXY_LIST, clear cookies, re-apply proxy."""
    global _proxy_index
    need = _expected_egress_country()
    max_tries = int(os.getenv("EGRESS_COUNTRY_VERIFY_MAX_ATTEMPTS", "5"))
    attempts = max_tries if need else 1

    for attempt in range(attempts):
        cmd = os.environ.get("ROTATE_IP_COMMAND", "").strip()
        if not cmd and _tor_enabled():
            cmd = os.environ.get("TOR_ROTATE_COMMAND", "").strip() or "sudo systemctl restart tor"
        if cmd:
            print("ROTATE_IP_COMMAND: rotating egress...", file=sys.stderr)
            subprocess.run(cmd, shell=True, timeout=180, check=False)
        script = os.environ.get("ROTATE_IP_SCRIPT", "").strip()
        if script:
            p = os.path.expanduser(script)
            if os.path.isfile(p):
                print(f"ROTATE_IP_SCRIPT: {p}", file=sys.stderr)
                subprocess.run(["bash", p], timeout=180, check=False)
        urls = _proxy_urls()
        if urls:
            _proxy_index += 1
        session.cookies.clear()
        _apply_proxy_to_session(session)

        if not need:
            return
        cc = _fetch_egress_country(session)
        if cc == need:
            print(f"Egress country OK: {cc}", file=sys.stderr)
            return
        print(
            f"Egress country mismatch: want {need}, got {cc or '(unknown)'} "
            f"({attempt + 1}/{attempts})",
            file=sys.stderr,
        )

    raise RuntimeError(
        f"Could not obtain egress country {need} after {attempts} rotation attempt(s). "
        "Use India-only proxies in PROXY_LIST, or Tor exit nodes (ExitNodes {in}), "
        "or a VPN endpoint in India. Set REQUIRE_INDIA_EGRESS=0 to skip verification."
    )


def _solve_captcha_from_png_bytes(image_bytes: bytes) -> str:
    """Local Tesseract OCR (see local_captcha_solver.py). May return \"\" — retry captcha fetch."""
    return solve_captcha_with_tesseract_from_bytes(image_bytes)


def _sanitize_filename_part(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    s = s.replace("/", "-").replace("\\", "-")
    s = re.sub(r"[^A-Za-z0-9\u0900-\u097F _.-]+", "", s)  # keep basic + Devanagari
    s = s.strip(" ._-")
    return s or "unknown"


def _is_valid_pdf(path: str) -> bool:
    try:
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) < 1024:  # too small to be a real PDF here
            return False
        with open(path, "rb") as f:
            head = f.read(5)
        return head == b"%PDF-"
    except Exception:
        return False


def _parse_pdf_rows(html: str, *, out_dir: str) -> list[PdfRow]:
    soup = BeautifulSoup(html, "html.parser")

    # Heuristic: each record row typically has a link to .../indexii/...
    href_re = re.compile(r"/eDisplay/[^\"'\s]*indexii/[^\"'\s]+", re.IGNORECASE)
    links: list[object] = []

    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if href and href_re.search(href):
            links.append(a)

    if not links:
        # Sometimes the URL is embedded in onclick handlers.
        for a in soup.find_all("a"):
            onclick = a.get("onclick") or ""
            m = href_re.search(onclick)
            if m:
                a.attrs["href"] = m.group(0)
                links.append(a)

    if not links:
        return []

    rows: list[PdfRow] = []
    for a in links:
        href = a.get("href") or ""
        if not href:
            continue
        url = urljoin(BASE_URL, href)

        # Try to name based on the row's <td> values.
        # Requirements:
        # - filename should start with the REAL table serial number
        # - include first 4 columns + last column
        tr = a.find_parent("tr")
        serial: int | None = None
        cols_for_name: list[str] = []
        if tr:
            tds = tr.find_all("td")
            td_texts = [td.get_text(" ", strip=True) for td in tds]

            # Serial: first numeric cell (some rows have an empty/checkbox first cell).
            for t in td_texts:
                tt = (t or "").strip()
                if re.fullmatch(r"\d{1,5}", tt or ""):
                    try:
                        cand = int(tt)
                    except Exception:
                        continue
                    # Basic sanity: serial is usually a small-ish positive integer.
                    if cand >= 1:
                        serial = cand
                        break

            # Name columns: first 4 cells + last cell (as user requested).
            first4 = [t for t in td_texts[:4] if t]
            last1 = [td_texts[-1]] if (td_texts and td_texts[-1]) else []
            cols_for_name = first4 + last1

        if len(cols_for_name) < 4:
            # Fallback: use whatever we got + last path token.
            cols_for_name = cols_for_name + [os.path.basename(href)]

        # Force filename to start with real serial, if we could parse it.
        parts: list[str] = []
        if serial is not None:
            parts.append(str(serial))
        for c in cols_for_name:
            sc = _sanitize_filename_part(c)
            if not sc:
                continue
            # Avoid duplicating serial if the first column already contains it.
            if serial is not None and sc == str(serial):
                continue
            parts.append(sc)
        filename_base = "_".join(parts) if parts else _sanitize_filename_part(os.path.basename(href))
        rows.append(PdfRow(serial=serial, filename_base=filename_base, url=url, out_dir=out_dir))

    # Deduplicate by URL (some pages repeat same link in hidden areas)
    uniq: dict[str, PdfRow] = {}
    for r in rows:
        uniq.setdefault(r.url, r)
    return list(uniq.values())


def _download_pdf(session: requests.Session, row: PdfRow, out_dir: str, *, max_retries: int = 5) -> str:
    # `out_dir` kept for backwards-compat; prefer row.out_dir.
    os.makedirs(row.out_dir, exist_ok=True)
    out_path = os.path.join(row.out_dir, f"{row.filename_base}.pdf")
    if _is_valid_pdf(out_path):
        return out_path
    headers = _default_headers(SEARCH_POST_PATH)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        # Exponential backoff with jitter to avoid hammering the server when it is unstable.
        # (Browser often succeeds after waiting a bit; same idea here.)
        backoff_s = min(30.0, (0.8 * (2 ** (attempt - 1))) + random.random())
        tmp_path = out_path + ".part"
        req = requests.Request("GET", row.url, headers=headers)
        prep = session.prepare_request(req)
        try:
            # Separate connect/read timeouts helps on flaky connections.
            r = session.send(prep, stream=True, timeout=(60, 300))
            try:
                if r.status_code in (429, 500, 502, 503, 504):
                    # Transient server-side failures / rate limiting.
                    retry_after = r.headers.get("Retry-After")
                    r.close()
                    if attempt < max_retries:
                        print(
                            f"PDF GET {r.status_code} for {row.url[:80]}... retry {attempt}/{max_retries}",
                            file=sys.stderr,
                        )
                        if retry_after:
                            try:
                                time.sleep(min(60.0, float(retry_after)))
                            except Exception:
                                time.sleep(backoff_s)
                        else:
                            time.sleep(backoff_s)
                        continue
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                os.replace(tmp_path, out_path)
                # If server returned an HTML error page, it won't start with %PDF-.
                if not _is_valid_pdf(out_path):
                    try:
                        os.remove(out_path)
                    except OSError:
                        pass
                    raise requests.RequestException("Downloaded file is not a valid PDF")
                _trace_pair(
                    tag=f"pdf_request_{row.filename_base}",
                    prep=prep,
                    resp=r,
                )
                return out_path
            finally:
                r.close()
        except requests.RequestException as e:
            last_exc = e
            if attempt < max_retries:
                print(f"PDF GET error (attempt {attempt}/{max_retries}): {e}", file=sys.stderr)
                time.sleep(backoff_s)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("PDF download failed after retries")


CHECKPOINT_VERSION = 1
CHECKPOINT_FILENAME = "checkpoint.json"


def _checkpoint_path(output_root: str) -> str:
    return os.path.join(output_root, CHECKPOINT_FILENAME)


def _default_checkpoint(
    yearsel: str,
    dist_name: str,
    tal_name: str,
    max_free_text: int,
    max_village: int,
    sorted_village_ids: list[int],
) -> dict:
    first_vid = sorted_village_ids[0] if sorted_village_ids else 0
    return {
        "version": CHECKPOINT_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "yearsel": yearsel,
        "dist_name": dist_name,
        "tal_name": tal_name,
        "max_free_text": max_free_text,
        "max_village": max_village,
        "status": "running",
        "resume": {"village_id": first_vid, "free_text": 0},
        "ongoing": None,
        "completed_pairs": [],
    }


def _load_checkpoint(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_checkpoint(path: str, state: dict) -> None:
    state = dict(state)
    state["version"] = CHECKPOINT_VERSION
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _pair_key(village_id: int, free_text: int) -> str:
    return f"{village_id}:{free_text}"


def _next_resume_pair(
    village_id: int,
    free_text: int,
    max_free_text: int,
    sorted_village_ids: list[int],
) -> tuple[int, int] | None:
    if free_text + 1 < max_free_text:
        return (village_id, free_text + 1)
    try:
        idx = sorted_village_ids.index(village_id)
    except ValueError:
        return None
    if idx + 1 < len(sorted_village_ids):
        return (sorted_village_ids[idx + 1], 0)
    return None


def _should_skip_pair(
    village_id: int,
    free_text: int,
    resume_village_id: int,
    resume_free_text: int,
) -> bool:
    if village_id < resume_village_id:
        return True
    if village_id > resume_village_id:
        return False
    return free_text < resume_free_text


def _mark_iteration_done(
    state: dict,
    village_id: int,
    free_text: int,
    max_free_text: int,
    sorted_village_ids: list[int],
    cp_path: str,
) -> None:
    key = _pair_key(village_id, free_text)
    done: list = list(state.get("completed_pairs") or [])
    if key not in done:
        done.append(key)
    state["completed_pairs"] = done
    nxt = _next_resume_pair(village_id, free_text, max_free_text, sorted_village_ids)
    if nxt:
        state["resume"] = {"village_id": nxt[0], "free_text": nxt[1]}
        state["status"] = "running"
    else:
        state["status"] = "completed"
        state["resume"] = {"village_id": village_id, "free_text": free_text}
    state["ongoing"] = None
    state.pop("last_error", None)
    _save_checkpoint(cp_path, state)


def main() -> int:
    out_dir = os.path.join(os.getcwd(), "output")
    s = _new_session_with_proxy()

    first_url = urljoin(BASE_URL, FIRST_GET_PATH)
    captcha_url = urljoin(BASE_URL, CAPTCHA_PATH)
    post_url = urljoin(BASE_URL, SEARCH_POST_PATH)

    # Optional quick limiting for testing (env vars).
    max_free_text = int(os.getenv("MAX_FREE_TEXT", "10"))
    max_village = int(os.getenv("MAX_VILLAGE", "-1"))  # -1 means no limit
    ignore_checkpoint = os.getenv("IGNORE_CHECKPOINT", "").strip() in ("1", "true", "yes")

    form_meta = dict(DEFAULT_FORM_VALUES)
    yearsel = str(form_meta.get("yearsel", "unknown"))
    dist_name = str(form_meta.get("dist_name", "unknown"))
    tal_name = str(form_meta.get("tal_name", "unknown"))

    sorted_village_ids = sorted(village_dict.keys())
    if max_village >= 0:
        sorted_village_ids = sorted_village_ids[:max_village]

    cp_path = _checkpoint_path(out_dir)
    state: dict = _default_checkpoint(
        yearsel, dist_name, tal_name, max_free_text, max_village, sorted_village_ids
    )

    loaded = None if ignore_checkpoint else _load_checkpoint(cp_path)
    if loaded and loaded.get("version") == CHECKPOINT_VERSION:
        if (
            str(loaded.get("yearsel")) == yearsel
            and str(loaded.get("dist_name")) == dist_name
            and str(loaded.get("tal_name")) == tal_name
            and int(loaded.get("max_free_text", max_free_text)) == max_free_text
            and int(loaded.get("max_village", max_village)) == max_village
        ):
            state = loaded
            print(f"Loaded checkpoint: resume village_id={state['resume']['village_id']} free_text={state['resume']['free_text']}")
        else:
            print(
                "Checkpoint ignored (DEFAULT_FORM_VALUES or limits differ from saved file). "
                "Use IGNORE_CHECKPOINT=1 to force ignore, or delete output/checkpoint.json.",
                file=sys.stderr,
            )

    if not sorted_village_ids:
        print("No villages to process (empty selection or MAX_VILLAGE=0).", file=sys.stderr)
        return 1

    resume_vid = int(state["resume"]["village_id"])
    resume_ft = int(state["resume"]["free_text"])
    if resume_vid not in sorted_village_ids:
        resume_vid = sorted_village_ids[0]
        resume_ft = 0
        state["resume"] = {"village_id": resume_vid, "free_text": resume_ft}
        _save_checkpoint(cp_path, state)
    resume_ft = max(0, min(resume_ft, max_free_text - 1))

    # Loop as requested (reversed):
    # - village_id: loop over village_dict keys (uses village_dict to set village_name)
    # - free_text: 0..9
    total_downloaded = 0
    # High concurrency causes many transient 500s / resets on IGR (seen to recover in browser).
    # Keep a conservative default; allow overriding via env.
    max_workers = int(os.getenv("PDF_MAX_WORKERS", "6"))
    max_workers = max(1, min(16, max_workers))

    for village_id in sorted_village_ids:
        village_name = village_dict[village_id]

        for free_text in range(0, max_free_text):
            if _should_skip_pair(village_id, free_text, resume_vid, resume_ft):
                continue

            free_text_value = str(free_text)
            print(
                f"\nSearching village_id={village_id} village_name={village_name} free_text={free_text_value}"
            )

            state["ongoing"] = {"village_id": village_id, "free_text": free_text}
            state["resume"] = {"village_id": village_id, "free_text": free_text}
            state["status"] = "running"
            _save_checkpoint(cp_path, state)

            max_pdf_full_rounds = int(os.getenv("MAX_PDF_FULL_RETRY_ROUNDS", "20"))
            pdf_outer_round = 0
            iteration_finished = False
            pending_serials: set[int] | None = None
            pending_urls: set[str] | None = None
            while not iteration_finished:
                pdf_outer_round += 1
                last_html: str | None = None
                attempt = 0
                while attempt < TESSERACT_CAPTCHA_MAX_ATTEMPTS:
                    attempt += 1
                    # Step 1: fresh csrf cookie + hidden token
                    h1 = dict(FIRSTGET_HEADERS)
                    ck1 = _cookie_header_from_session(s)
                    if ck1:
                        h1["Cookie"] = ck1
                    req1 = requests.Request("GET", first_url, headers=h1)
                    prep1 = s.prepare_request(req1)
                    r1 = s.send(prep1, timeout=40)
                    r1.raise_for_status()
                    _trace_pair(
                        tag=f"firstget_village_{village_id}_free_{free_text_value}_round{pdf_outer_round}_attempt_{attempt}",
                        prep=prep1,
                        resp=r1,
                    )
                    hidden_csrf = _extract_csrf_hidden(r1.text)

                    # Step 2: captcha image (also refreshes PHPSESSID)
                    h2 = dict(CAPTCHA_HEADERS)
                    ck2 = _cookie_header_from_session(s)
                    if ck2:
                        h2["Cookie"] = ck2
                    req2 = requests.Request("GET", captcha_url, headers=h2)
                    prep2 = s.prepare_request(req2)
                    r2 = s.send(prep2, timeout=40)
                    r2.raise_for_status()
                    _trace_pair(
                        tag=f"captcha_get_village_{village_id}_free_{free_text_value}_round{pdf_outer_round}_attempt_{attempt}",
                        prep=prep2,
                        resp=r2,
                        binary_body_ext=".png",
                    )

                    # Step 3: solve captcha (Tesseract)
                    captcha_text = _solve_captcha_from_png_bytes(r2.content)
                    if not captcha_text.strip():
                        print(
                            f"Empty OCR captcha (attempt {attempt}/{TESSERACT_CAPTCHA_MAX_ATTEMPTS}). Retrying..."
                        )
                        time.sleep(0.4)
                        continue

                    # Step 4: post search
                    form_dict = dict(DEFAULT_FORM_VALUES)
                    form_dict["free_text"] = free_text_value
                    form_dict["village_id"] = str(village_id)
                    form_dict["village_name"] = village_name

                    form_items = [
                        ("_csrfToken", hidden_csrf),
                        ("years", form_dict.get("years", "")),
                        ("district_id", form_dict.get("district_id", "")),
                        ("taluka_id", form_dict.get("taluka_id", "")),
                        ("village_id", form_dict.get("village_id", "")),
                        ("article_id", form_dict.get("article_id", "")),
                        ("free_text", form_dict.get("free_text", "")),
                        ("partyname", form_dict.get("partyname", "")),
                        ("captcha", captcha_text),
                        ("dist_name", form_dict.get("dist_name", "")),
                        ("tal_name", form_dict.get("tal_name", "")),
                        ("article_name", form_dict.get("article_name", "")),
                        ("village_name", form_dict.get("village_name", "")),
                        ("freetext", form_dict.get("freetext", "")),
                        ("yearsel", form_dict.get("yearsel", "")),
                    ]

                    h3 = dict(POST_HEADERS)
                    ck3 = _cookie_header_from_session(s)
                    if ck3:
                        h3["Cookie"] = ck3
                    req3 = requests.Request("POST", post_url, headers=h3, data=form_items)
                    prep3 = s.prepare_request(req3)
                    r3 = s.send(prep3, timeout=60)
                    r3.raise_for_status()
                    last_html = r3.text
                    _trace_pair(
                        tag=f"search_post_village_{village_id}_free_{free_text_value}_round{pdf_outer_round}_attempt_{attempt}",
                        prep=prep3,
                        resp=r3,
                    )

                    if _has_daily_search_limit_exceeded(last_html):
                        print(
                            "Daily search limit exceeded; rotating IP and retrying (does not count as captcha attempt).",
                            file=sys.stderr,
                        )
                        _rotate_ip(s)
                        attempt -= 1
                        time.sleep(2.0)
                        continue

                    if _has_invalid_captcha(last_html):
                        print(
                            f"Invalid captcha (attempt {attempt}/{TESSERACT_CAPTCHA_MAX_ATTEMPTS}). Retrying..."
                        )
                        time.sleep(0.4)
                        continue
                    break

                if last_html is None:
                    print(
                        "Search failed (no HTML after captcha attempts). Fix captcha/OCR and rerun; "
                        f"checkpoint left at village_id={village_id} free_text={free_text}.",
                        file=sys.stderr,
                    )
                    state["ongoing"] = {"village_id": village_id, "free_text": free_text}
                    state["resume"] = {"village_id": village_id, "free_text": free_text}
                    _save_checkpoint(cp_path, state)
                    return 1

                # Output structure: output/<yearsel>/<dist_name>/<tal_name>/<village_name>/
                form_for_dirs = dict(DEFAULT_FORM_VALUES)
                form_for_dirs["village_name"] = village_name
                yearsel = str(form_for_dirs.get("yearsel", "unknown"))
                dist_name = str(form_for_dirs.get("dist_name", "unknown"))
                tal_name = str(form_for_dirs.get("tal_name", "unknown"))
                village_dir_name = str(form_for_dirs.get("village_name", "unknown"))

                download_dir = os.path.join(
                    out_dir,
                    _sanitize_filename_part(yearsel),
                    _sanitize_filename_part(dist_name),
                    _sanitize_filename_part(tal_name),
                    _sanitize_filename_part(village_dir_name),
                )

                base_rows = _parse_pdf_rows(last_html, out_dir=download_dir)
                pdf_rows = base_rows
                if not pdf_rows:
                    debug_name = f"debug_search_village_{village_id}_free_text_{free_text}.html"
                    with open(debug_name, "w", encoding="utf-8", errors="ignore") as f:
                        f.write(last_html)
                    print(f"No records. Wrote {debug_name}")
                    _mark_iteration_done(
                        state, village_id, free_text, max_free_text, sorted_village_ids, cp_path
                    )
                    iteration_finished = True
                    break

                # Detect missing serial numbers from the table, if available.
                serials = sorted({r.serial for r in base_rows if r.serial is not None})
                missing_serials: set[int] = set()
                if serials:
                    expected = set(range(1, max(serials) + 1))
                    missing_serials = expected - set(serials)

                # Build pending URL set on first round (only those not already downloaded).
                if pending_urls is None:
                    pending_urls = set()
                    for r in base_rows:
                        out_path = os.path.join(r.out_dir, f"{r.filename_base}.pdf")
                        if not _is_valid_pdf(out_path):
                            pending_urls.add(r.url)

                # If we detected missing/failed serial numbers earlier, only retry those,
                # AND/OR any still-pending URLs.
                if pending_serials is not None:
                    pdf_rows = [
                        r
                        for r in base_rows
                        if (r.serial in pending_serials)
                        or (pending_urls is not None and r.url in pending_urls)
                    ]
                else:
                    pdf_rows = [r for r in base_rows if pending_urls is None or r.url in pending_urls]

                print(
                    f"Found {len(pdf_rows)} PDFs (outer round {pdf_outer_round}/{max_pdf_full_rounds}). "
                    f"Downloading serially to: {out_dir}"
                    + (f" (missing serials in table: {sorted(missing_serials)[:20]}...)" if missing_serials else "")
                )

                failures: list[tuple[PdfRow, str]] = []
                completed = 0
                # Serial / single-threaded PDF downloads (no parallelism).
                # This is slower but far more reliable for this site.
                dl_sess = requests.Session()
                dl_sess.proxies.update(s.proxies)
                dl_sess.cookies.update(s.cookies)

                def _sort_key(r: PdfRow) -> tuple[int, str]:
                    # Serial-first; unknown serials go last, stable by URL.
                    return (r.serial if r.serial is not None else 10**9, r.url)

                for row in sorted(pdf_rows, key=_sort_key):
                    try:
                        path = _download_pdf(dl_sess, row, out_dir)
                        completed += 1
                        total_downloaded += 1
                        if pending_urls is not None:
                            pending_urls.discard(row.url)
                        if completed % 5 == 0 or completed == len(pdf_rows):
                            print(f"Downloaded {completed}/{len(pdf_rows)} (total={total_downloaded})")
                        else:
                            print(f"Downloaded: {os.path.basename(path)}")
                        # Tiny pacing helps reduce server resets.
                        time.sleep(0.15)
                    except Exception as e:
                        failures.append((row, str(e)))
                        print(f"FAILED: {row.url} -> {e}", file=sys.stderr)
                        # Brief pause before continuing to next doc.
                        time.sleep(0.5)

                if failures:
                    fail_log = os.path.join(out_dir, "failed_pdf_downloads.txt")
                    try:
                        with open(fail_log, "a", encoding="utf-8") as lf:
                            ts = datetime.now(timezone.utc).isoformat()
                            for row, err in failures:
                                lf.write(
                                    f"{ts}\tvillage_id={village_id}\tfree_text={free_text}\t{row.url}\t{err}\n"
                                )
                    except OSError:
                        pass
                    state["last_pdf_failures"] = [
                        {"url": r.url, "error": err[:300]} for r, err in failures[:50]
                    ]

                    if pdf_outer_round < max_pdf_full_rounds:
                        # Retry only failed + missing serial numbers next outer round.
                        failed_serials = {r.serial for r, _ in failures if r.serial is not None}
                        pending_serials = set(missing_serials) | set(failed_serials)
                        print(
                            f"{len(failures)} PDF(s) still failing after per-URL retries; "
                            "rotating IP and retrying full flow for missing/failed serials "
                            f"for same village_id={village_id} free_text={free_text}. "
                            f"(round {pdf_outer_round + 1}/{max_pdf_full_rounds}).",
                            file=sys.stderr,
                        )
                        _rotate_ip(s)
                        s = _new_session_with_proxy()
                        continue

                    print(
                        f"{len(failures)} PDF(s) failed; max full IP-rotation rounds ({max_pdf_full_rounds}) reached. "
                        "NOT advancing checkpoint (to avoid losing documents).",
                        file=sys.stderr,
                    )
                    state["status"] = "blocked"
                    state["ongoing"] = {"village_id": village_id, "free_text": free_text}
                    state["resume"] = {"village_id": village_id, "free_text": free_text}
                    _save_checkpoint(cp_path, state)
                    return 2

                state.pop("last_pdf_failures", None)
                # Even if the executor reported no failures, ensure everything is actually on disk.
                if pending_urls is not None and pending_urls:
                    if pdf_outer_round < max_pdf_full_rounds:
                        print(
                            f"{len(pending_urls)} PDF(s) still missing/invalid on disk; retrying same free_text "
                            f"(round {pdf_outer_round + 1}/{max_pdf_full_rounds}).",
                            file=sys.stderr,
                        )
                        _rotate_ip(s)
                        s = _new_session_with_proxy()
                        continue
                    print(
                        f"{len(pending_urls)} PDF(s) still missing/invalid after {max_pdf_full_rounds} rounds. "
                        "NOT advancing checkpoint (to avoid losing documents).",
                        file=sys.stderr,
                    )
                    state["status"] = "blocked"
                    state["ongoing"] = {"village_id": village_id, "free_text": free_text}
                    state["resume"] = {"village_id": village_id, "free_text": free_text}
                    _save_checkpoint(cp_path, state)
                    return 2
                if missing_serials and pdf_outer_round < max_pdf_full_rounds:
                    pending_serials = set(missing_serials)
                    print(
                        f"Table shows missing serials {sorted(missing_serials)}; rotating IP and retrying those only "
                        f"(round {pdf_outer_round + 1}/{max_pdf_full_rounds}).",
                        file=sys.stderr,
                    )
                    _rotate_ip(s)
                    s = _new_session_with_proxy()
                    continue
                _mark_iteration_done(
                    state, village_id, free_text, max_free_text, sorted_village_ids, cp_path
                )
                iteration_finished = True
                break

            # Rotate IP between free_text values (helps avoid per-IP throttles).
            if os.getenv("ROTATE_IP_EACH_FREE_TEXT", "1").strip().lower() in ("1", "true", "yes"):
                try:
                    _rotate_ip(s)
                    s = _new_session_with_proxy()
                except Exception as e:
                    print(f"IP rotation between free_text failed: {e}", file=sys.stderr)

            time.sleep(0.25)

    state["ongoing"] = None
    state["status"] = "completed"
    _save_checkpoint(cp_path, state)
    print(f"\nFinished loops. Total PDFs downloaded: {total_downloaded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
