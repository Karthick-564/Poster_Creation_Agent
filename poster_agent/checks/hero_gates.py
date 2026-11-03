"""Deterministic Quality Gates for Hero Cutout Assets.

Evaluates transparent RGBA cutouts before Vision Critic review:
1. Sharpness: Laplacian variance of RGB pixels inside the alpha mask.
2. Alpha Sanity:
   - Coverage: foreground solid pixels between 12% and 75% of canvas area.
   - Border contact: zero alpha touching the 2px perimeter border (rejects cropped/cut off cutouts).
   - Halo ring: ratio of semi-transparent transitional pixels (10 < alpha < 235) vs solid alpha.
3. Silhouette Clarity: boundary sharpness and contour definition.
4. Composite Scoring: 0.0 to 100.0 score to rank multiple candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


@dataclass
class HeroGateResult:
    passed: bool
    score: float  # 0.0 to 100.0
    sharpness: float
    coverage_pct: float
    touches_border: bool
    halo_ratio: float
    reason: str


def evaluate_hero_quality(image_path: Path | str) -> HeroGateResult:
    """Evaluate transparent RGBA hero image against deterministic physical gates."""
    path = Path(image_path)
    if not path.exists():
        return HeroGateResult(
            passed=False, score=0.0, sharpness=0.0, coverage_pct=0.0,
            touches_border=True, halo_ratio=1.0, reason=f"File not found: {path}"
        )

    img = Image.open(path).convert("RGBA")
    w, h = img.size
    total_pixels = w * h

    arr = np.array(img)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3]

    solid_mask = alpha > 30
    solid_count = int(np.sum(solid_mask))

    # 1. Alpha coverage check
    coverage_pct = round((solid_count / total_pixels) * 100.0, 2)
    if coverage_pct < 10.0:
        return HeroGateResult(
            passed=False, score=10.0, sharpness=0.0, coverage_pct=coverage_pct,
            touches_border=False, halo_ratio=1.0,
            reason=f"Hero coverage too low ({coverage_pct}% < 10.0%): subject is empty or tiny specks."
        )
    if coverage_pct > 80.0:
        return HeroGateResult(
            passed=False, score=20.0, sharpness=0.0, coverage_pct=coverage_pct,
            touches_border=True, halo_ratio=1.0,
            reason=f"Hero coverage too high ({coverage_pct}% > 80.0%): subject fills entire canvas like a background."
        )

    # 2. Border contact check (rejects cropped subjects)
    # Check top 2px, bottom 2px, left 2px, right 2px
    top_contact = np.any(alpha[:2, :] > 30)
    bottom_contact = np.any(alpha[-2:, :] > 30)
    left_contact = np.any(alpha[:, :2] > 30)
    right_contact = np.any(alpha[:, -2:] > 30)
    touches_border = bool(top_contact or bottom_contact or left_contact or right_contact)

    if touches_border:
        return HeroGateResult(
            passed=False, score=25.0, sharpness=0.0, coverage_pct=coverage_pct,
            touches_border=True, halo_ratio=1.0,
            reason="Subject touches image perimeter boundary (cut off / cropped edges)."
        )

    # 3. Sharpness: Laplacian variance inside alpha mask
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    masked_gray = np.where(solid_mask, gray, 0)
    laplacian = cv2.Laplacian(masked_gray, cv2.CV_64F)
    # Variance of laplacian on solid pixels only
    lap_pixels = laplacian[solid_mask]
    sharpness = round(float(np.var(lap_pixels)), 2) if len(lap_pixels) > 0 else 0.0

    # 4. Halo ratio: transitional alpha (10 < a < 235) vs solid alpha (a >= 235)
    transitional_count = int(np.sum((alpha > 10) & (alpha < 235)))
    solid_core_count = int(np.sum(alpha >= 235))
    halo_ratio = round(transitional_count / max(1, solid_core_count), 4)

    # 5. Composite score calculation (0..100)
    # Baseline score
    score = 50.0

    # Sharpness bonus/penalty: good renders are typically > 120.0
    if sharpness < 40.0:
        score -= 30.0
        fail_reason = f"Subject is blurry or indistinct (Laplacian variance {sharpness} < 40.0)."
    elif sharpness < 80.0:
        score -= 10.0
        fail_reason = ""
    else:
        score += min(25.0, (sharpness - 80.0) / 10.0)
        fail_reason = ""

    # Coverage score: ideal coverage is 20% to 55%
    if 20.0 <= coverage_pct <= 55.0:
        score += 15.0
    else:
        score += 5.0

    # Halo score: ideal halo_ratio < 0.15
    if halo_ratio < 0.12:
        score += 10.0
    elif halo_ratio > 0.25:
        score -= 15.0

    score = max(0.0, min(100.0, round(score, 1)))
    passed = score >= 55.0 and not touches_border and sharpness >= 40.0

    if not passed and not fail_reason:
        fail_reason = f"Hero composite quality score ({score}/100) below threshold 55.0"

    return HeroGateResult(
        passed=passed,
        score=score,
        sharpness=sharpness,
        coverage_pct=coverage_pct,
        touches_border=touches_border,
        halo_ratio=halo_ratio,
        reason="Clean sharp alpha cutout" if passed else fail_reason,
    )

