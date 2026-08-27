"""WMF/EMF (MathType formula ko'rinishlari) ni brauzerbop PNG (base64 data URL) ga o'tkazadi.

Konvertor tanlash tartibi (mavjudini ishlatadi):
  1) libwmf  — `wmf2gd` (juda yengil va tez; Render Docker uchun ideal)
  2) LibreOffice — `soffice --convert-to png` (og'irroq, zaxira)
Hech biri bo'lmasa None qaytaradi (tizim buzilmaydi — formula shunchaki chiqmaydi).
"""
import base64
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops


def _tool():
    if shutil.which("wmf2gd"):
        return "libwmf"
    if shutil.which("soffice") or shutil.which("libreoffice"):
        return "soffice"
    return None


def available():
    return _tool() is not None


def _trim(png_path):
    """Oq bo'sh joyni kesib, faqat formulani qoldiradi."""
    try:
        im = Image.open(png_path).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bbox = ImageChops.difference(im, bg).getbbox()
        if bbox:
            # ozgina hoshiya
            x0, y0, x1, y1 = bbox
            pad = 3
            im = im.crop((max(0, x0 - pad), max(0, y0 - pad),
                          min(im.width, x1 + pad), min(im.height, y1 + pad)))
        buf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        im.save(buf.name, "PNG")
        return buf.name
    except Exception:
        return png_path


def wmf_bytes_to_data_url(data, ext=".wmf"):
    """WMF/EMF baytlarini PNG data URL ('data:image/png;base64,...') ga o'tkazadi.
    Muvaffaqiyatsiz bo'lsa None."""
    tool = _tool()
    if not tool or not data:
        return None
    tmpdir = tempfile.mkdtemp(prefix="fx_")
    src = os.path.join(tmpdir, "f" + ext)
    out = os.path.join(tmpdir, "f.png")
    try:
        with open(src, "wb") as fh:
            fh.write(data)
        if tool == "libwmf":
            subprocess.run(["wmf2gd", "-t", "png", "-o", out, src],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=False)
        else:
            subprocess.run(["soffice", "--headless", "--convert-to", "png",
                            "--outdir", tmpdir, src],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=40, check=False)
        if not os.path.exists(out) or os.path.getsize(out) == 0:
            return None
        cropped = _trim(out)
        with open(cropped, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
