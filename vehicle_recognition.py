"""
Vehicle Recognition Module

Uses OpenAI GPT-4o vision to extract license plate, make, model,
and color from vehicle photos for the HOA parking compliance tracker.
"""

import base64
import json
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import openai
from PIL import Image, ImageOps


@dataclass
class VehicleInfo:
    """Extracted vehicle information from photo analysis."""
    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    confidence_notes: Optional[str] = None


def is_recognition_available() -> bool:
    """Check if vehicle recognition is configured (OPENAI_API_KEY is set)."""
    return bool(os.getenv("OPENAI_API_KEY"))


# OpenAI Vision scales images to fit 2048px max and then tiles at 512px.
# Anything above ~1280px adds tiles (cost) with negligible recognition gain.
_MAX_DIMENSION = 1280
_JPEG_QUALITY = 85


def _prepare_image_for_api(image_bytes: bytes) -> bytes:
    """
    Resize and compress an image before sending to the vision API.

    - Auto-rotates using EXIF data.
    - Scales so the longest side is at most _MAX_DIMENSION pixels.
    - Re-encodes as JPEG at _JPEG_QUALITY%.

    This cuts the base64 payload from several MB to ~100-300 KB,
    reducing latency and per-request token cost without hurting
    license-plate readability.
    """
    img = Image.open(BytesIO(image_bytes))
    try:
        img = ImageOps.exif_transpose(img)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Only downscale — never upscale a small image
        w, h = img.size
        if max(w, h) > _MAX_DIMENSION:
            scale = _MAX_DIMENSION / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        return buf.getvalue()
    finally:
        # Explicitly close the image to free memory
        img.close()


def analyze_vehicle_photo(image_bytes: bytes) -> VehicleInfo:
    """
    Use OpenAI vision to extract vehicle details from a photo.

    Args:
        image_bytes: Raw bytes of the uploaded image file.

    Returns:
        VehicleInfo dataclass with extracted fields.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
        Exception: If the API call fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Add it to your .env file to enable photo analysis."
        )

    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

    client = openai.OpenAI(api_key=api_key)

    # Resize / compress to cut cost and latency
    optimized = _prepare_image_for_api(image_bytes)
    b64 = base64.b64encode(optimized).decode()

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "You are analyzing a vehicle photo for a parking compliance system. "
                    "Extract the following information and return ONLY valid JSON:\n"
                    "{\n"
                    '  "license_plate": "plate text in uppercase, no spaces or dashes, or null if unreadable",\n'
                    '  "make": "vehicle manufacturer (e.g., Toyota, Honda, Ford) or null if not identifiable",\n'
                    '  "model": "vehicle model (e.g., Camry, Civic, F-150) or null if not identifiable",\n'
                    '  "color": "primary body color (e.g., White, Black, Silver, Red) or null",\n'
                    '  "confidence_notes": "brief note about readability issues or null if everything is clear"\n'
                    "}\n\n"
                    "Rules:\n"
                    "- For license_plate, remove ALL spaces and dashes, use UPPERCASE letters only\n"
                    "- If the plate is partially obscured, provide your best reading and note it\n"
                    "- For make/model, identify based on visible badges, emblems, and body style\n"
                    "- For color, use common color names (White, Black, Silver, Gray, Red, Blue, Green, etc.)\n"
                    "- Use null for any field you truly cannot determine\n"
                    "- Do NOT guess or hallucinate plate characters you cannot see"
                )},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "high"
                }}
            ]
        }],
        response_format={"type": "json_object"},
        max_tokens=300,
    )

    data = json.loads(response.choices[0].message.content)

    return VehicleInfo(
        license_plate=data.get("license_plate"),
        make=data.get("make"),
        model=data.get("model"),
        color=data.get("color"),
        confidence_notes=data.get("confidence_notes"),
    )
