import base64
import os
import re
from io import BytesIO


def _get_captcha_png_bytes_via_canvas(driver, img_id: str = "imgCaptcha_new", timeout_ms: int = 15000) -> bytes:
    """
    Extract captcha image bytes from an <img> element without taking a screenshot.
    Works by drawing the image into a canvas and returning a PNG data URL.
    """
    script = r"""
        const imgId = arguments[0];
        const timeoutMs = arguments[1];
        const cb = arguments[2];

        function fail(msg) { cb({ ok: false, error: msg }); }

        const img = document.getElementById(imgId);
        if (!img) return fail("captcha img element not found: " + imgId);

        const start = Date.now();
        (function waitForLoad() {
            try {
                // naturalWidth==0 until loaded
                if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) {
                    const canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth;
                    canvas.height = img.naturalHeight;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    const dataUrl = canvas.toDataURL('image/png');
                    return cb({ ok: true, dataUrl });
                }
                if (Date.now() - start > timeoutMs) {
                    return fail("captcha image did not load within timeout");
                }
                setTimeout(waitForLoad, 100);
            } catch (e) {
                return fail("exception while extracting captcha: " + (e && e.message ? e.message : String(e)));
            }
        })();
    """

    result = driver.execute_async_script(script, img_id, int(timeout_ms))
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(f"Failed to extract captcha image: {result.get('error') if isinstance(result, dict) else result}")

    data_url = result.get("dataUrl", "") or ""
    m = re.match(r"^data:image\/png;base64,(.+)$", data_url)
    if not m:
        raise RuntimeError("Unexpected captcha data URL format")

    return base64.b64decode(m.group(1))


def save_captcha_png_from_driver(driver, path: str, img_id: str = "imgCaptcha_new") -> None:
    """Write the current captcha image to a PNG file (for CapSolver / external APIs)."""
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    png_bytes = _get_captcha_png_bytes_via_canvas(driver, img_id=img_id)
    with open(path, "wb") as f:
        f.write(png_bytes)


def _basic_cleanup(text: str) -> str:
    # Keep only alphanumerics; captcha is typically short.
    text = (text or "").strip()
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def solve_captcha_with_tesseract_from_bytes(png_bytes: bytes) -> str:
    """
    Run Tesseract on raw PNG bytes (e.g. from GET /eDisplay/captcha-image).

    Requires: tesseract binary, pillow, pytesseract.
    Tries several preprocess + OCR settings; returns first non-empty cleaned string,
    or "" if all attempts fail (caller should fetch a new captcha and retry).
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter
    except Exception as e:
        raise RuntimeError(
            "Missing dependencies for local captcha solving. Install pillow + pytesseract and system tesseract."
        ) from e

    base = Image.open(BytesIO(png_bytes)).convert("RGB")
    whitelist = r"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

    def _try_ocr(img: Image.Image, psm: int) -> str:
        cfg = rf"--oem 3 --psm {psm} -c tessedit_char_whitelist={whitelist}"
        raw = pytesseract.image_to_string(img, config=cfg)
        return _basic_cleanup(raw)

    variants: list[tuple[str, Image.Image]] = []

    # 1) Original pipeline (median + upscale + threshold)
    g = ImageOps.grayscale(base)
    g = ImageOps.autocontrast(g)
    g = g.filter(ImageFilter.MedianFilter(size=3))
    g_big = g.resize((g.width * 3, g.height * 3))
    for thr in (150, 130, 170, 110, 190):
        bw = g_big.point(lambda p, t=thr: 255 if p > t else 0)
        variants.append((f"median_thr{thr}", bw))
        variants.append((f"median_thr{thr}_inv", ImageOps.invert(bw)))

    # 2) Simpler: grayscale + autocontrast + upscale, no median
    g2 = ImageOps.grayscale(base)
    g2 = ImageOps.autocontrast(g2)
    g2 = g2.resize((g2.width * 4, g2.height * 4))
    for thr in (140, 160, 120):
        bw2 = g2.point(lambda p, t=thr: 255 if p > t else 0)
        variants.append((f"simple_thr{thr}", bw2))

    # 3) Raw grayscale enlarged (sometimes thresholding loses thin strokes)
    g3 = ImageOps.grayscale(base)
    g3 = ImageOps.autocontrast(g3)
    g3 = g3.resize((g3.width * 4, g3.height * 4))
    variants.append(("autocontrast_only", g3))

    psms = (7, 8, 13, 6)
    for _name, im in variants:
        for psm in psms:
            try:
                t = _try_ocr(im, psm)
                if t:
                    return t
            except Exception:
                continue
    return ""


def solve_captcha_with_tesseract_from_driver(driver, img_id: str = "imgCaptcha_new"):
    """
    Returns a list of candidate captcha strings, similar to the CapSolver helper.

    Requires:
      - `tesseract` binary installed on the system
      - Python packages: pillow, pytesseract
    """
    png_bytes = _get_captcha_png_bytes_via_canvas(driver, img_id=img_id)
    cleaned = solve_captcha_with_tesseract_from_bytes(png_bytes)
    if not cleaned:
        return None

    # Return a few variants, matching the API solver behavior
    return list(dict.fromkeys([cleaned, cleaned.upper(), cleaned.lower()]))

