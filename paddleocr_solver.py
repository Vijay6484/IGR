import base64
import re
from io import BytesIO


def _get_captcha_png_bytes_via_canvas(driver, img_id: str = "imgCaptcha_new", timeout_ms: int = 15000) -> bytes:
    """
    Extract captcha image bytes from an <img> element without taking a screenshot.
    Uses a canvas to capture the image as PNG and return raw bytes.
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
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        raise RuntimeError("Unexpected captcha data URL format")
    return base64.b64decode(data_url[len(prefix):])


def _basic_cleanup(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def solve_captcha_with_paddle_from_driver(driver, img_id: str = "imgCaptcha_new"):
    """
    Returns a list of candidate captcha strings using PaddleOCR.

    Requires (in your venv/system):
      - paddlepaddle
      - paddleocr
      - pillow
    """
    try:
        from paddleocr import PaddleOCR
        from PIL import Image
    except Exception as e:
        raise RuntimeError(
            "Missing dependencies for Paddle captcha solving. "
            "Install paddlepaddle + paddleocr + pillow in your environment."
        ) from e

    png_bytes = _get_captcha_png_bytes_via_canvas(driver, img_id=img_id)
    img = Image.open(BytesIO(png_bytes)).convert("RGB")

    # For this captcha we assume mainly English letters/digits
    ocr = PaddleOCR(lang="en", use_angle_cls=True, show_log=False)
    result = ocr.ocr(png_bytes, cls=True)

    candidates = []
    for line in result:
        for _, (text, _) in line:
            cleaned = _basic_cleanup(text)
            if cleaned:
                candidates.append(cleaned)

    if not candidates:
        return None

    primary = candidates[0]
    # Return unique variants, similar to Tesseract helper API
    ordered = [primary, primary.upper(), primary.lower()]
    seen = set()
    deduped = []
    for v in ordered:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return deduped

