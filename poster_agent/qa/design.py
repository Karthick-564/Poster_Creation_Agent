"""Design quality metrics module for evaluating poster aesthetics and layout dynamics.

Pure functions only. Zero pipeline dependencies or side effects.
Evaluates typographic text manifests and rendered raster images against
compositional design quality dimensions:
1. Palette coverage: representation of the designated color palette.
2. Typographic scale contrast: ratio between headline scale and meta/body scale.
3. Asymmetric balance index: horizontal dynamic offset vs static centered stack.
4. Hero presence & integration: visibility, contrast, and edge feathering.
5. Whitespace balance: ratio of active breathing room vs clutter/void.
6. Focal point hierarchy: primary and secondary visual anchors.
"""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Optional, Sequence, Union

import numpy as np
from PIL import Image


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex color string (#RGB or #RRGGBB) to integer RGB tuple."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (0, 0, 0)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate perceived photometric luminance (0.0 - 255.0)."""
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _get_bounds(row: dict[str, Any]) -> tuple[float, float, float, float]:
    """Extract (x, y, w, h) from row dict, handling bounds subdict or direct keys."""
    b = row.get("bounds")
    if isinstance(b, dict):
        x = float(b.get("x", row.get("x", 0.0)))
        y = float(b.get("y", row.get("y", 0.0)))
        w = float(b.get("width", b.get("w", row.get("width", row.get("w", 0.0)))))
        h = float(b.get("height", b.get("h", row.get("height", row.get("h", 0.0)))))
    else:
        x = float(row.get("x", 0.0))
        y = float(row.get("y", 0.0))
        w = float(row.get("width", row.get("w", 0.0)))
        h = float(row.get("height", row.get("h", 0.0)))
    return x, y, w, h


def palette_coverage(
    image_input: Union[Path, str, Image.Image],
    palette_hexes: Sequence[str],
    tolerance: float = 48.0,
    min_pixel_share: float = 0.003,
) -> dict[str, Any]:
    """Measure how well the image represents the designated brand/brief color palette.
    
    tolerance: Euclidean RGB distance threshold to count a pixel as matching a palette color.
    min_pixel_share: Minimum fraction of pixels (e.g. 0.3%) for a color to be considered represented.
    """
    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if not p.exists():
            return {"coverage_ratio": 0.0, "represented_colors": [], "missing_colors": list(palette_hexes), "pixel_shares": {}}
        im = Image.open(p).convert("RGB")
    else:
        im = image_input.convert("RGB")

    # Downsample for fast vectorized distance computation
    im_small = im.resize((180, 225), Image.Resampling.BOX)
    arr = np.array(im_small, dtype=np.float32)
    flat_pixels = arr.reshape(-1, 3)
    n_pixels = flat_pixels.shape[0]

    represented = []
    missing = []
    shares = {}

    for hex_code in palette_hexes:
        target_rgb = np.array(hex_to_rgb(hex_code), dtype=np.float32)
        # Euclidean RGB distance
        dist = np.linalg.norm(flat_pixels - target_rgb, axis=1)
        matches = np.sum(dist <= tolerance)
        share = float(matches) / float(n_pixels)
        shares[hex_code] = round(share, 4)
        if share >= min_pixel_share:
            represented.append(hex_code)
        else:
            missing.append(hex_code)

    coverage_ratio = len(represented) / max(1, len(palette_hexes))
    return {
        "coverage_ratio": round(coverage_ratio, 3),
        "represented_colors": represented,
        "missing_colors": missing,
        "pixel_shares": shares,
    }


def type_scale_contrast(manifest_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Compute typographic dynamic scale contrast (max_size / min_size).
    
    A dynamic, authoritative design achieves > 3.0:1 hierarchy ratio between
    headline and meta/body copy.
    """
    sizes = []
    for r in manifest_rows:
        s = r.get("size")
        if s is not None and float(s) > 0:
            sizes.append(float(s))

    if not sizes:
        return {"ratio": 1.0, "max_size": 0.0, "min_size": 0.0, "dynamic_hierarchy": False}

    max_s = max(sizes)
    min_s = min(sizes)
    ratio = max_s / max(1.0, min_s)

    return {
        "ratio": round(ratio, 2),
        "max_size": max_s,
        "min_size": min_s,
        "dynamic_hierarchy": ratio >= 3.0,
    }


def asymmetry_index(
    manifest_rows: Sequence[dict[str, Any]],
    canvas_w: float,
) -> dict[str, Any]:
    """Calculate horizontal center-of-mass offset from center line.
    
    0.0 = completely centered stack (Word document syndrome).
    0.10 - 0.40 = dynamic asymmetric balance (Swiss / modern editorial).
    > 0.60 = unbalanced extreme drift.
    """
    total_weight = 0.0
    weighted_x = 0.0
    half_w = canvas_w / 2.0

    for r in manifest_rows:
        x, y, w, h = _get_bounds(r)
        area = max(1.0, w * h)
        cx = x + w / 2.0
        weighted_x += cx * area
        total_weight += area

    if total_weight <= 0:
        return {"asymmetry_index": 0.0, "center_of_mass_x": half_w, "is_asymmetric": False}

    com_x = weighted_x / total_weight
    offset_from_center = abs(com_x - half_w)
    index = offset_from_center / half_w

    return {
        "asymmetry_index": round(index, 3),
        "center_of_mass_x": round(com_x, 1),
        "canvas_center_x": round(half_w, 1),
        "is_asymmetric": index >= 0.08,
    }


def hero_presence(
    image_input: Union[Path, str, Image.Image],
    hero_rect: Optional[Sequence[float]] = None,
) -> dict[str, Any]:
    """Analyze the hero zone for presence, contrast, luminance, and edge feathering."""
    if not hero_rect or len(hero_rect) < 4:
        return {
            "present": False,
            "hero_rect": None,
            "mean_luminance": 0.0,
            "contrast_std": 0.0,
            "is_void": True,
            "feathered": False,
            "hero_score": 0.0,
        }

    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if not p.exists():
            return {"present": False, "hero_rect": list(hero_rect), "error": "file_not_found"}
        im = Image.open(p).convert("RGB")
    else:
        im = image_input.convert("RGB")

    w_im, h_im = im.size
    hx, hy, hw, hh = [int(v) for v in hero_rect]
    # Bound within image coordinates
    x1 = max(0, min(hx, w_im - 1))
    y1 = max(0, min(hy, h_im - 1))
    x2 = max(x1 + 1, min(hx + hw, w_im))
    y2 = max(y1 + 1, min(hy + hh, h_im))

    crop = im.crop((x1, y1, x2, y2))
    crop_arr = np.array(crop, dtype=np.float32)
    gray = 0.299 * crop_arr[:, :, 0] + 0.587 * crop_arr[:, :, 1] + 0.114 * crop_arr[:, :, 2]

    mean_lum = float(np.mean(gray))
    std_lum = float(np.std(gray))

    # A near-black void has mean_lum < 15 and std < 10
    is_void = mean_lum < 15.0 and std_lum < 12.0

    # Edge feathering check: sample 4-pixel border strip vs interior
    feathered = False
    if gray.shape[0] > 16 and gray.shape[1] > 16:
        border_top = gray[:4, :]
        border_bot = gray[-4:, :]
        border_left = gray[:, :4]
        border_right = gray[:, -4:]
        border_mean = (float(np.mean(border_top)) + float(np.mean(border_bot)) +
                       float(np.mean(border_left)) + float(np.mean(border_right))) / 4.0

        interior = gray[8:-8, 8:-8]
        interior_mean = float(np.mean(interior))
        # If border softly approaches adjacent tone with gradual transition
        edge_delta = abs(interior_mean - border_mean)
        if edge_delta < 45.0 or std_lum > 20.0:
            feathered = True

    hero_score = 1.0
    if is_void:
        hero_score -= 0.6
    if not feathered:
        hero_score -= 0.3
    hero_score = max(0.0, hero_score)

    return {
        "present": True,
        "hero_rect": [hx, hy, hw, hh],
        "mean_luminance": round(mean_lum, 1),
        "contrast_std": round(std_lum, 1),
        "is_void": is_void,
        "feathered": feathered,
        "hero_score": round(hero_score, 2),
    }


def whitespace_balance(
    manifest_rows: Sequence[dict[str, Any]],
    hero_rect: Optional[Sequence[float]],
    canvas_w: float,
    canvas_h: float,
) -> dict[str, Any]:
    """Calculate the fraction of active negative space vs occupied geometry."""
    total_canvas_area = canvas_w * canvas_h
    if total_canvas_area <= 0:
        return {"whitespace_ratio": 1.0, "balanced": False}

    # Estimate occupied area (union approximation)
    occupied = 0.0
    for r in manifest_rows:
        _, _, w, h = _get_bounds(r)
        occupied += w * h

    if hero_rect and len(hero_rect) >= 4:
        occupied += hero_rect[2] * hero_rect[3]

    whitespace_area = max(0.0, total_canvas_area - occupied)
    ratio = whitespace_area / total_canvas_area

    # Balanced range: 35% to 75% active whitespace
    balanced = 0.35 <= ratio <= 0.75

    return {
        "whitespace_ratio": round(ratio, 3),
        "occupied_fraction": round(occupied / total_canvas_area, 3),
        "balanced": balanced,
    }


def focal_count(
    manifest_rows: Sequence[dict[str, Any]],
    hero_rect: Optional[Sequence[float]],
    canvas_w: float,
    canvas_h: float,
) -> dict[str, Any]:
    """Identify dominant focal points (headline and large hero)."""
    focals = []
    canvas_area = canvas_w * canvas_h

    # Check for dominant headline
    for r in manifest_rows:
        role = r.get("role", "")
        size = float(r.get("size", 0))
        _, _, w, h = _get_bounds(r)
        if role == "headline" or size >= 64 or (w * h) / canvas_area >= 0.04:
            focals.append(f"text:{r.get('id', r.get('text', 'headline'))}")

    # Check for hero
    if hero_rect and len(hero_rect) >= 4:
        hero_area = hero_rect[2] * hero_rect[3]
        if hero_area / canvas_area >= 0.08:
            focals.append("image:hero")

    count = len(focals)
    # Ideal poster has 1 to 2 focal anchors
    balanced = (1 <= count <= 3)

    return {
        "focal_count": count,
        "focals": focals,
        "balanced": balanced,
    }


def evaluate_design_quality(
    manifest_rows: Sequence[dict[str, Any]],
    image_input: Union[Path, str, Image.Image],
    palette_hexes: Sequence[str],
    canvas_w: float = 1080.0,
    canvas_h: float = 1350.0,
    hero_rect: Optional[Sequence[float]] = None,
) -> dict[str, Any]:
    """Run full compositional design quality suite and compute composite score."""
    p_cov = palette_coverage(image_input, palette_hexes)
    t_scale = type_scale_contrast(manifest_rows)
    asym = asymmetry_index(manifest_rows, canvas_w)
    hero_info = hero_presence(image_input, hero_rect)
    ws = whitespace_balance(manifest_rows, hero_rect, canvas_w, canvas_h)
    focals = focal_count(manifest_rows, hero_rect, canvas_w, canvas_h)

    # Compute composite 10-point design quality rubric:
    # 1. Palette coverage (max 2.0 pts): ratio * 2.0
    # 2. Type scale contrast (max 2.5 pts): ratio >= 3.5 -> 2.5, ratio >= 2.5 -> 2.0, else 1.0
    # 3. Asymmetry & layout dynamic (max 2.0 pts): index >= 0.08 -> 2.0, else 1.0
    # 4. Hero presence & integration (max 2.0 pts): hero_score * 2.0
    # 5. Whitespace balance (max 1.5 pts): balanced -> 1.5, else 0.8
    score = 0.0
    score += p_cov["coverage_ratio"] * 2.0

    if t_scale["ratio"] >= 3.5:
        score += 2.5
    elif t_scale["ratio"] >= 2.5:
        score += 2.0
    elif t_scale["ratio"] >= 1.8:
        score += 1.5
    else:
        score += 1.0

    if asym["is_asymmetric"]:
        score += 2.0
    else:
        score += 1.0

    score += hero_info.get("hero_score", 1.0) * 2.0

    if ws["balanced"]:
        score += 1.5
    else:
        score += 0.8

    return {
        "design_score": round(min(10.0, max(0.0, score)), 2),
        "palette_coverage": p_cov,
        "type_scale": t_scale,
        "asymmetry": asym,
        "hero_presence": hero_info,
        "whitespace": ws,
        "focal_point": focals,
    }
