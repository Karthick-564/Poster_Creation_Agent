"""QR generation with an explicit offline fallback.

The fallback is deterministic and visually QR-like, but it is not scannable.
Renderers must surface that in warnings; the mock pipeline never claims a
scannable code when the ``qrcode`` package is unavailable.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw


def make_qr_image(payload: str, size: int, output_path: str | Path) -> tuple[Path, bool]:
    """Return (path, scannable)."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        import qrcode  # type: ignore

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        image = image.resize((size, size), Image.Resampling.NEAREST)
        image.save(out)
        return out, True
    except Exception:
        image = Image.new("RGB", (size, size), "#FFFFFF")
        draw = ImageDraw.Draw(image)
        modules = 25
        quiet = 2
        cell = size / (modules + quiet * 2)
        digest = hashlib.sha256(payload.encode("utf-8")).digest()

        def finder(ox: int, oy: int) -> None:
            draw.rectangle(
                (
                    (ox + quiet) * cell,
                    (oy + quiet) * cell,
                    (ox + quiet + 7) * cell,
                    (oy + quiet + 7) * cell,
                ),
                fill="#000000",
            )
            draw.rectangle(
                (
                    (ox + quiet + 1) * cell,
                    (oy + quiet + 1) * cell,
                    (ox + quiet + 6) * cell,
                    (oy + quiet + 6) * cell,
                ),
                fill="#FFFFFF",
            )
            draw.rectangle(
                (
                    (ox + quiet + 2) * cell,
                    (oy + quiet + 2) * cell,
                    (ox + quiet + 5) * cell,
                    (oy + quiet + 5) * cell,
                ),
                fill="#000000",
            )

        for row in range(modules):
            for col in range(modules):
                in_finder = (
                    (row < 8 and col < 8)
                    or (row < 8 and col >= modules - 8)
                    or (row >= modules - 8 and col < 8)
                )
                if in_finder:
                    continue
                bit = digest[(row * modules + col) % len(digest)] >> ((row + col) % 8) & 1
                if bit:
                    draw.rectangle(
                        (
                            (col + quiet) * cell,
                            (row + quiet) * cell,
                            (col + quiet + 1) * cell - 1,
                            (row + quiet + 1) * cell - 1,
                        ),
                        fill="#000000",
                    )
        finder(0, 0)
        finder(modules - 7, 0)
        finder(0, modules - 7)
        image.save(out)
        return out, False
