"""
Photo processing helpers for the Add Vehicle flow.

Ported from the original app.py — same memory-safety behavior (explicit
img.close() + gc.collect() after every PIL operation) since these run on
the same small container that previously hit libjpeg SIGSEGVs under load.
"""
import gc
from datetime import datetime
from io import BytesIO
from typing import Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, ImageDraw, ImageFont

# Prevent decompression bombs from consuming all RAM.
Image.MAX_IMAGE_PIXELS = 30_000_000  # ~30 megapixels

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # HEIC support optional — JPG/PNG still work


def stamp_photo_with_timestamp(image_bytes: bytes, stamp_datetime: Optional[datetime] = None) -> bytes:
    """Add a white timestamp to the bottom-right corner of a photo."""
    now = stamp_datetime or datetime.now(ZoneInfo("America/Los_Angeles"))
    timestamp_text = now.strftime("%b %d, %Y %-I:%M:%S %p")

    img = Image.open(BytesIO(image_bytes))
    try:
        img = ImageOps.exif_transpose(img)

        if img.mode != 'RGB':
            img = img.convert('RGB')

        draw = ImageDraw.Draw(img)
        font_size = max(20, img.width // 40)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), timestamp_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        padding = max(10, img.width // 80)
        x = img.width - text_width - padding
        y = img.height - text_height - padding

        draw.text((x + 2, y + 2), timestamp_text, fill=(0, 0, 0), font=font)
        draw.text((x, y), timestamp_text, fill=(255, 255, 255), font=font)

        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        return output.getvalue()
    finally:
        img.close()
        gc.collect()


def downscale_for_upload(image_bytes: bytes, max_dim: int = 2048) -> bytes:
    """
    Downscale and normalise raw upload/capture bytes.

    Always re-encodes to a capped-resolution JPEG regardless of input size —
    prevents full-resolution pixel buffers from being held/decoded multiple
    times downstream (preview, stamp, AI analysis) on a memory-constrained container.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        try:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=92, optimize=True)
            buf.seek(0)
            return buf.getvalue()
        finally:
            img.close()
            gc.collect()
    except Exception:
        return image_bytes


def extract_photo_datetime(image_bytes: bytes):
    """Read the original capture date/time from a photo's EXIF metadata.

    Must be called on raw upload bytes before downscale_for_upload re-encodes
    the image, since re-encoding strips EXIF tags.

    Returns a naive datetime (camera's local time), or None if unavailable.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        try:
            exif = img.getexif()
            date_str = None
            try:
                exif_ifd = exif.get_ifd(0x8769)  # Exif IFD pointer
                date_str = exif_ifd.get(0x9003) or exif_ifd.get(0x9004)  # DateTimeOriginal / DateTimeDigitized
            except Exception:
                pass
            if not date_str:
                date_str = exif.get(0x0132)  # IFD0 DateTime (fallback)
            if not date_str:
                return None
            return datetime.strptime(date_str.strip(), "%Y:%m:%d %H:%M:%S")
        finally:
            img.close()
    except Exception:
        return None
