"""WCAG AA Contrast ratio and minimum font size checks."""
import re
from pathlib import Path
from typing import Literal
from PIL import Image
from pydantic import BaseModel, ConfigDict

from poster_agent.spec.models import PosterSpec, TextElement
from .models import CheckResult


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse #RRGGBB to (r, g, b) tuple."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) != 6:
        return (0, 0, 0)
    return (
        int(hex_clean[0:2], 16),
        int(hex_clean[2:4], 16),
        int(hex_clean[4:6], 16),
    )


def calculate_relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate WCAG 2.1 relative luminance for an RGB tuple."""
    channels = []
    for val in rgb:
        s = val / 255.0
        if s <= 0.04045:
            channels.append(s / 12.92)
        else:
            channels.append(((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def calculate_contrast_ratio(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
    """Calculate WCAG contrast ratio between two colors (range: 1.0 to 21.0)."""
    l1 = calculate_relative_luminance(rgb1)
    l2 = calculate_relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def get_average_background_color(
    image: Image.Image,
    box_coords: tuple[int, int, int, int],
) -> tuple[int, int, int]:
    """Sample the image behind the text box and compute average background color."""
    left, top, right, bottom = box_coords
    w, h = image.size

    left = max(0, min(left, w - 1))
    top = max(0, min(top, h - 1))
    right = max(left + 1, min(right, w))
    bottom = max(top + 1, min(bottom, h))

    crop = image.crop((left, top, right, bottom)).convert("RGB")
    # Resize to 1x1 to get average color
    pixel = crop.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    return pixel


def run_contrast_check(
    spec: PosterSpec,
    poster_image_path: str | Path | None = None,
    min_contrast_ratio: float = 4.5,
    min_font_pt: int = 14,
) -> list[CheckResult]:
    """Run contrast ratio and font size checks on all text elements."""
    results: list[CheckResult] = []

    # Load image if provided
    img: Image.Image | None = None
    if poster_image_path and Path(poster_image_path).exists():
        try:
            img = Image.open(poster_image_path).convert("RGB")
        except Exception:
            img = None

    default_bg_rgb = hex_to_rgb(spec.palette[0]) if spec.palette else (11, 19, 43)

    for elem in spec.elements:
        text_rgb = hex_to_rgb(elem.color)

        if img is not None:
            # Sample background behind text box
            box_px = elem.box.to_pixels(img.width, img.height)
            bg_rgb = get_average_background_color(img, box_px)
        else:
            bg_rgb = default_bg_rgb

        contrast = calculate_contrast_ratio(text_rgb, bg_rgb)

        # Contrast check (WCAG AA threshold is 4.5 for regular, 3.0 for large text)
        threshold = 3.0 if elem.size >= 18 or (elem.size >= 14 and elem.weight >= 700) else min_contrast_ratio
        if contrast < threshold:
            results.append(
                CheckResult(
                    check_name=f"contrast_{elem.id}",
                    severity="blocking",
                    detail=(
                        f"Element '{elem.id}' ({elem.role}) has contrast ratio {contrast:.2f}:1 "
                        f"against background (minimum required is {threshold:.1f}:1)."
                    ),
                    fix_hint=f"Adjust color for '{elem.id}' to provide higher contrast against background.",
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name=f"contrast_{elem.id}",
                    severity="pass",
                    detail=f"Element '{elem.id}' contrast ratio {contrast:.2f}:1 meets WCAG standards.",
                    fix_hint=None,
                )
            )

        # Minimum font size check
        if elem.size < min_font_pt:
            results.append(
                CheckResult(
                    check_name=f"font_size_{elem.id}",
                    severity="blocking",
                    detail=(
                        f"Element '{elem.id}' font size {elem.size}pt is smaller than "
                        f"minimum readable threshold ({min_font_pt}pt)."
                    ),
                    fix_hint=f"Increase font size of '{elem.id}' to at least {min_font_pt}pt.",
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name=f"font_size_{elem.id}",
                    severity="pass",
                    detail=f"Element '{elem.id}' font size {elem.size}pt is readable.",
                    fix_hint=None,
                )
            )

    return results
