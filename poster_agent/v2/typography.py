"""Pure typography and color helpers for the v2 planner.

These are intentionally local to v2: the v2 core must not depend on the
legacy composer monolith. The math mirrors the proven helpers so plans made
here behave the same way on the VectorCraft renderer.
"""
from __future__ import annotations

from typing import Iterable


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _channel_luminance(channel: float) -> float:
    channel = channel / 255.0
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    r, g, b = hex_to_rgb(color)
    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)


def ensure_contrast(background: str, preferred: str, minimum: float = 4.5) -> str:
    """Return the preferred foreground if it passes, otherwise black or white."""
    if contrast_ratio(background, preferred) >= minimum:
        return preferred
    return "#FFFFFF" if contrast_ratio(background, "#FFFFFF") >= contrast_ratio(background, "#000000") else "#000000"


def estimate_text_width(text: str, size: float, uppercase: bool = False, tracking: float = 0.0) -> float:
    if not text:
        return 0.0
    ratio = 0.66 if uppercase else 0.58
    tracking_offset = (tracking / 1000.0) * size * max(0, len(text) - 1)
    return len(text) * size * ratio + tracking_offset


def wrap_text(
    text: str,
    size: float,
    max_width: float,
    uppercase: bool = False,
    tracking: float = 0.0,
    max_lines: int = 4,
) -> list[str]:
    """Wrap by words, then hard-split any single word that still overflows."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if not current or estimate_text_width(candidate, size, uppercase, tracking) <= max_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))

    # Hard split words that are wider than the box on their own.
    resolved: list[str] = []
    for line in lines:
        if estimate_text_width(line, size, uppercase, tracking) <= max_width:
            resolved.append(line)
            continue
        chunk = ""
        for char in line:
            if estimate_text_width(chunk + char, size, uppercase, tracking) > max_width and chunk:
                resolved.append(chunk)
                chunk = char
            else:
                chunk += char
        if chunk:
            resolved.append(chunk)
    return resolved[:max_lines]


def fit_text(
    text: str,
    target_size: float,
    min_size: float,
    max_width: float,
    max_lines: int,
    uppercase: bool = False,
    tracking: float = 0.0,
) -> tuple[list[str], float]:
    """Shrink until the wrapped block fits the width and line budget."""
    size = target_size
    while size >= min_size:
        lines = wrap_text(text, size, max_width, uppercase, tracking, max_lines)
        if lines and all(
            estimate_text_width(line, size, uppercase, tracking) <= max_width for line in lines
        ):
            return lines, size
        size *= 0.94
    return wrap_text(text, min_size, max_width, uppercase, tracking, max_lines), min_size


def block_height(lines: Iterable[str], size: float, line_height: float) -> float:
    return max(1, len(list(lines))) * size * line_height


def estimated_block(
    text: str,
    target_size: float,
    min_size: float,
    box_width: float,
    box_height: float,
    max_lines: int,
    uppercase: bool = False,
    tracking: float = 0.0,
    line_height: float = 1.12,
) -> dict[str, float | list[str] | bool]:
    """Fit text into a box and report whether it overflowed."""
    lines, size = fit_text(
        text=text,
        target_size=target_size,
        min_size=min_size,
        max_width=box_width,
        max_lines=max_lines,
        uppercase=uppercase,
        tracking=tracking,
    )
    height = block_height(lines, size, line_height)
    width = max((estimate_text_width(line, size, uppercase, tracking) for line in lines), default=0.0)
    return {
        "lines": lines,
        "size": size,
        "width": width,
        "height": height,
        "fits": width <= box_width * 1.001 and height <= box_height * 1.001,
        "shrunk": size < target_size - 0.01,
    }
