from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from local_captcha_solver import solve_captcha_with_tesseract_from_bytes

BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
FIRST_GET_PATH = "/eDisplay/Propertydetails/index"
CAPTCHA_PATH = "/eDisplay/captcha-image"
SEARCH_POST_PATH = "/eDisplay/Propertydetails/index"

TRACE_DIR = "http_trace"

TESSERACT_CAPTCHA_MAX_ATTEMPTS = 100

# --- IP rotation (shared with igr2_script.py) ---
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
    "Referer": urljoin(BASE_URL, FIRST_GET_PATH),
    "Accept-Encoding": "gzip, deflate, br",
    "Priority": "i",
    "Connection": "keep-alive",
}

POST_HEADERS = {
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Gpc": "1",
    "Accept-Language": "en-GB,en;q=0.5",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": BASE_URL,
    "Referer": urljoin(BASE_URL, FIRST_GET_PATH),
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Accept-Encoding": "gzip, deflate, br",
    "Priority": "u=0, i",
    "Connection": "keep-alive",
}


# Keep dictionaries in sync with igr2_script.py by importing if needed later.
district_dict = {23: "पुणे"}
taluka_dict = {1: "हवेली"}
village_dict = {0: "अवसरेनगर"}

# Using the same example values for now.
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
class TableRow:
    serial: int | None
    columns: list[str]
    url: str | None


def _sanitize_filename_part(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    s = s.replace("/", "-").replace("\\", "-")
    s = re.sub(r"[^A-Za-z0-9\u0900-\u097F _.-]+", "", s)  # keep basic + Devanagari
    s = s.strip(" ._-")
    return s or "unknown"


def _checkpoint_path(output_root: str) -> str:
    return os.path.join(output_root, "checkpoint.json")


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
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _pair_key(village_id: int, free_text: int) -> str:
    return f"{village_id}:{free_text}"


def _should_skip_pair(village_id: int, free_text: int, resume_vid: int, resume_ft: int) -> bool:
    if village_id < resume_vid:
        return True
    if village_id == resume_vid and free_text < resume_ft:
        return True
    return False


def _cookie_header_from_session(session: requests.Session) -> str:
    jar = session.cookies
    items = []
    for c in jar:
        items.append(f"{c.name}={c.value}")
    return "; ".join(items)


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
    return os.environ.get("TOR_SOCKS_PROXY", "").strip() or "socks5h://127.0.0.1:9050"


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


def _expected_egress_country() -> str | None:
    if os.getenv("REQUIRE_INDIA_EGRESS", "").strip().lower() in ("1", "true", "yes"):
        return "IN"
    raw = os.environ.get("REQUIRED_EGRESS_COUNTRY", "").strip().upper()
    if not raw or raw in ("0", "FALSE", "NO", "OFF"):
        return None
    return raw[:2]


def _fetch_egress_country(session: requests.Session) -> str | None:
    for url in ("https://ipapi.co/json/", "https://ifconfig.co/country"):
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


def _new_session_with_proxy() -> requests.Session:
    sess = requests.Session()
    _apply_proxy_to_session(sess)
    need = _expected_egress_country()
    if not need:
        return sess
    cc = _fetch_egress_country(sess)
    if cc == need:
        return sess
    _rotate_ip(sess)
    return sess


def _rotate_ip(session: requests.Session) -> None:
    global _proxy_index
    need = _expected_egress_country()
    max_tries = int(os.getenv("EGRESS_COUNTRY_VERIFY_MAX_ATTEMPTS", "5"))
    attempts = max_tries if need else 1

    for _ in range(attempts):
        cmd = os.environ.get("ROTATE_IP_COMMAND", "").strip()
        if not cmd and _tor_enabled():
            cmd = os.environ.get("TOR_ROTATE_COMMAND", "").strip() or "sudo systemctl restart tor"
        if cmd:
            subprocess.run(cmd, shell=True, timeout=180, check=False)
        script = os.environ.get("ROTATE_IP_SCRIPT", "").strip()
        if script:
            p = os.path.expanduser(script)
            if os.path.isfile(p):
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
            return
    raise RuntimeError("Could not obtain required egress country after rotation attempts.")


def _solve_captcha_from_png_bytes(image_bytes: bytes) -> str:
    return solve_captcha_with_tesseract_from_bytes(image_bytes)


def _parse_table(html: str) -> tuple[list[str], list[TableRow]]:
    soup = BeautifulSoup(html, "html.parser")

    # Try to identify headers.
    headers: list[str] = []
    for tr in soup.select("table thead tr"):
        ths = tr.find_all(["th", "td"])
        h = [t.get_text(" ", strip=True) for t in ths]
        h = [x for x in h if x]
        if h:
            headers = h
            break

    href_re = re.compile(r"/eDisplay/[^\"'\s]*indexii/[^\"'\s]+", re.IGNORECASE)

    rows: list[TableRow] = []
    for tr in soup.select("table tbody tr"):
        tds = tr.find_all("td")
        cols = [td.get_text(" ", strip=True) for td in tds]
        cols = [c for c in cols if c is not None]

        serial: int | None = None
        for c in cols:
            cc = (c or "").strip()
            if re.fullmatch(r"\d{1,5}", cc):
                try:
                    serial = int(cc)
                except Exception:
                    serial = None
                break

        url: str | None = None
        a = tr.find("a", href=True)
        if a and a.get("href") and href_re.search(a.get("href") or ""):
            url = urljoin(BASE_URL, a.get("href") or "")
        else:
            # Sometimes in onclick.
            for a2 in tr.find_all("a"):
                onclick = a2.get("onclick") or ""
                m = href_re.search(onclick)
                if m:
                    url = urljoin(BASE_URL, m.group(0))
                    break

        # Keep only meaningful rows: either has URL or has any non-empty column values.
        if url or any((c or "").strip() for c in cols):
            rows.append(TableRow(serial=serial, columns=cols, url=url))

    # Fallback: if no tbody rows found, scan any tr with indexii link.
    if not rows:
        for a in soup.find_all("a"):
            href = a.get("href") or ""
            onclick = a.get("onclick") or ""
            m = href_re.search(href) or href_re.search(onclick)
            if not m:
                continue
            tr = a.find_parent("tr")
            if not tr:
                continue
            tds = tr.find_all("td")
            cols = [td.get_text(" ", strip=True) for td in tds]
            url = urljoin(BASE_URL, m.group(0))
            serial = None
            for c in cols:
                cc = (c or "").strip()
                if re.fullmatch(r"\d{1,5}", cc):
                    try:
                        serial = int(cc)
                    except Exception:
                        serial = None
                    break
            rows.append(TableRow(serial=serial, columns=cols, url=url))

    # Stable order by serial then url.
    def _k(r: TableRow) -> tuple[int, str]:
        return (r.serial if r.serial is not None else 10**9, r.url or "")

    rows.sort(key=_k)
    return headers, rows


def _write_table_json(
    *,
    output_root: str,
    yearsel: str,
    dist_name: str,
    tal_name: str,
    village_name: str,
    village_id: int,
    free_text: int,
    headers: list[str],
    rows: list[TableRow],
) -> str:
    out_dir = os.path.join(
        output_root,
        _sanitize_filename_part(yearsel),
        _sanitize_filename_part(dist_name),
        _sanitize_filename_part(tal_name),
        _sanitize_filename_part(village_name),
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"free_text_{free_text}.json")

    payload: dict[str, Any] = {
        "meta": {
            "yearsel": yearsel,
            "dist_name": dist_name,
            "tal_name": tal_name,
            "village_id": village_id,
            "village_name": village_name,
            "free_text": free_text,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
        },
        "headers": headers,
        "rows": [
            {"serial": r.serial, "columns": r.columns, "url": r.url}
            for r in rows
        ],
    }

    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)
    return out_path


def main() -> int:
    output_root = os.path.join(os.getcwd(), "output_table")

    parser = argparse.ArgumentParser(description="IGR table scraper (no PDFs)")
    parser.add_argument(
        "--yearsel",
        default=os.getenv("YEARSEL", DEFAULT_FORM_VALUES.get("yearsel", "2025")),
        help="Year selection (maps to form field 'yearsel'), e.g. 2025 or 2026. "
        "Can also be set via env YEARSEL.",
    )
    args = parser.parse_args()
    DEFAULT_FORM_VALUES["yearsel"] = str(args.yearsel)

    s = _new_session_with_proxy()

    first_url = urljoin(BASE_URL, FIRST_GET_PATH)
    captcha_url = urljoin(BASE_URL, CAPTCHA_PATH)
    post_url = urljoin(BASE_URL, SEARCH_POST_PATH)

    max_free_text = int(os.getenv("MAX_FREE_TEXT", "10"))
    max_village = int(os.getenv("MAX_VILLAGE", "-1"))
    ignore_checkpoint = os.getenv("IGNORE_CHECKPOINT", "").strip() in ("1", "true", "yes")

    form_meta = dict(DEFAULT_FORM_VALUES)
    yearsel = str(form_meta.get("yearsel", "unknown"))
    dist_name = str(form_meta.get("dist_name", "unknown"))
    tal_name = str(form_meta.get("tal_name", "unknown"))

    sorted_village_ids = sorted(village_dict.keys())
    if max_village >= 0:
        sorted_village_ids = sorted_village_ids[:max_village]

    cp_path = _checkpoint_path(output_root)
    state: dict = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "yearsel": yearsel,
        "dist_name": dist_name,
        "tal_name": tal_name,
        "max_free_text": max_free_text,
        "max_village": max_village,
        "status": "running",
        "resume": {"village_id": sorted_village_ids[0] if sorted_village_ids else 0, "free_text": 0},
        "ongoing": None,
        "completed_pairs": [],
    }

    loaded = None if ignore_checkpoint else _load_checkpoint(cp_path)
    if loaded:
        if (
            str(loaded.get("yearsel")) == yearsel
            and str(loaded.get("dist_name")) == dist_name
            and str(loaded.get("tal_name")) == tal_name
            and int(loaded.get("max_free_text", max_free_text)) == max_free_text
            and int(loaded.get("max_village", max_village)) == max_village
        ):
            state = loaded
            print(
                f"Loaded checkpoint: resume village_id={state['resume']['village_id']} free_text={state['resume']['free_text']}"
            )

    resume_vid = int(state["resume"]["village_id"])
    resume_ft = int(state["resume"]["free_text"])

    total_rows = 0
    for village_id in sorted_village_ids:
        village_name = village_dict[village_id]
        for free_text in range(0, max_free_text):
            if _should_skip_pair(village_id, free_text, resume_vid, resume_ft):
                continue

            free_text_value = str(free_text)
            print(f"\nScraping table village_id={village_id} village_name={village_name} free_text={free_text_value}")

            state["ongoing"] = {"village_id": village_id, "free_text": free_text}
            state["resume"] = {"village_id": village_id, "free_text": free_text}
            state["status"] = "running"
            _save_checkpoint(cp_path, state)

            last_html: str | None = None
            attempt = 0
            while attempt < TESSERACT_CAPTCHA_MAX_ATTEMPTS:
                attempt += 1
                h1 = dict(FIRSTGET_HEADERS)
                ck1 = _cookie_header_from_session(s)
                if ck1:
                    h1["Cookie"] = ck1
                r1 = s.get(first_url, headers=h1, timeout=40)
                r1.raise_for_status()
                hidden_csrf = _extract_csrf_hidden(r1.text)

                h2 = dict(CAPTCHA_HEADERS)
                ck2 = _cookie_header_from_session(s)
                if ck2:
                    h2["Cookie"] = ck2
                r2 = s.get(captcha_url, headers=h2, timeout=40)
                r2.raise_for_status()

                captcha_text = _solve_captcha_from_png_bytes(r2.content)
                if not captcha_text.strip():
                    time.sleep(0.4)
                    continue

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
                r3 = s.post(post_url, headers=h3, data=form_items, timeout=60)
                r3.raise_for_status()
                last_html = r3.text

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
                    print(f"Invalid captcha (attempt {attempt}/{TESSERACT_CAPTCHA_MAX_ATTEMPTS}). Retrying...")
                    time.sleep(0.4)
                    continue
                break

            if last_html is None:
                print(
                    "Search failed (no HTML after captcha attempts).",
                    file=sys.stderr,
                )
                _save_checkpoint(cp_path, state)
                return 1

            headers, rows = _parse_table(last_html)
            out_path = _write_table_json(
                output_root=output_root,
                yearsel=yearsel,
                dist_name=dist_name,
                tal_name=tal_name,
                village_name=village_name,
                village_id=village_id,
                free_text=free_text,
                headers=headers,
                rows=rows,
            )
            total_rows += len(rows)
            print(f"Wrote {len(rows)} row(s) to {out_path}")

            # Mark done and advance resume.
            done = set(state.get("completed_pairs") or [])
            done.add(_pair_key(village_id, free_text))
            state["completed_pairs"] = sorted(done)

            if free_text + 1 < max_free_text:
                state["resume"] = {"village_id": village_id, "free_text": free_text + 1}
                state["status"] = "running"
            else:
                # next village
                try:
                    idx = sorted_village_ids.index(village_id)
                except ValueError:
                    idx = -1
                if 0 <= idx + 1 < len(sorted_village_ids):
                    state["resume"] = {"village_id": sorted_village_ids[idx + 1], "free_text": 0}
                    state["status"] = "running"
                else:
                    state["status"] = "completed"

            state["ongoing"] = None
            _save_checkpoint(cp_path, state)
            time.sleep(0.25)

    state["ongoing"] = None
    state["status"] = "completed"
    _save_checkpoint(cp_path, state)
    print(f"\nFinished loops. Total table rows written: {total_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

