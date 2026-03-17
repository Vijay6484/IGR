import base64
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


def _basic_cleanup(text: str) -> str:
    # Keep only alphanumerics; captcha is typically short.
    text = (text or "").strip()
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def solve_captcha_with_tesseract_from_driver(driver, img_id: str = "imgCaptcha_new"):
    """
    Returns a list of candidate captcha strings, similar to the CapSolver helper.

    Requires:
      - `tesseract` binary installed on the system
      - Python packages: pillow, pytesseract
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter
    except Exception as e:
        raise RuntimeError(
            "Missing dependencies for local captcha solving. Install pillow + pytesseract and system tesseract."
        ) from e

    png_bytes = _get_captcha_png_bytes_via_canvas(driver, img_id=img_id)

    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    # Preprocess: grayscale, increase contrast, denoise, threshold, upscale
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.resize((img.width * 3, img.height * 3))
    img = img.point(lambda p: 255 if p > 150 else 0)

    config = r"--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    raw = pytesseract.image_to_string(img, config=config)
    cleaned = _basic_cleanup(raw)

    if not cleaned:
        return None

    # Return a few variants, matching the API solver behavior
    return list(dict.fromkeys([cleaned, cleaned.upper(), cleaned.lower()]))

