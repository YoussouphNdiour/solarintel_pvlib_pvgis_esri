"""QR code generator for SolarIntel v2 online dashboard links.

Generates PNG-encoded QR codes that link to the interactive HTML dashboard
for a given simulation / report URL.
"""

from __future__ import annotations

import io

import qrcode
from qrcode.image.pil import PilImage


def generate_qr_png(
    url: str,
    box_size: int = 6,
    border: int = 2,
) -> bytes:
    """Generate a QR code PNG for the given URL.

    Args:
        url: The URL to encode in the QR code (e.g. dashboard deep link).
        box_size: Pixel size of each QR code box/module.
        border: Width of the quiet zone in boxes.

    Returns:
        Raw PNG bytes with the standard PNG magic header (``\\x89PNG``).
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
