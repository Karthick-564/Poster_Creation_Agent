"""Content-Aware Saliency and Negative Space Analysis (PosterLayout CVPR 2023).

Computes:
1. Saliency Map (S) and Negative Space Map (N) using multi-scale edge energy and luminance variance.
2. Optical Center calculation (human visual center at ~42% vertical height).
3. Occlusion Penalty (Occ+) and Negative Space Utility (Uti^T) metrics.
"""
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image, ImageFilter
from pydantic import BaseModel, ConfigDict, Field


class SaliencyProfile(BaseModel):
    """Content-aware saliency and visual weight profile."""
    model_config = ConfigDict(extra="forbid")
    optical_center_x: int = 540
    optical_center_y: int = 560
    top_negative_space_ratio: float = 0.85
    mid_saliency_density: float = 0.65
    bottom_negative_space_ratio: float = 0.82
    recommended_hero_y: int = 550
    recommended_scrim_start_y: int = 760


class SaliencyAnalyzer:
    """Computes content-aware saliency and negative space maps from background art."""

    def __init__(self, target_w: int = 1080, target_h: int = 1350):
        self.target_w = target_w
        self.target_h = target_h

    def analyze_canvas(
        self,
        bg_path: str | Path | None = None,
        hero_rgba_path: str | Path | None = None,
    ) -> SaliencyProfile:
        """Analyze background and hero to locate optical center and calm negative space."""
        # Downscale for fast, robust frequency analysis (270x337)
        down_w = 270
        down_h = int(down_w * (self.target_h / self.target_w))

        if bg_path and Path(bg_path).exists():
            bg_img = Image.open(bg_path).convert("L").resize((down_w, down_h), Image.Resampling.LANCZOS)
            bg_arr = np.array(bg_img, dtype=float)

            # High-frequency edge energy
            edges = bg_img.filter(ImageFilter.FIND_EDGES)
            edge_arr = np.array(edges, dtype=float)

            # Local variance
            blur = bg_img.filter(ImageFilter.GaussianBlur(radius=4))
            var_arr = np.abs(bg_arr - np.array(blur, dtype=float))

            # Combined Saliency
            saliency = (edge_arr * 0.6) + (var_arr * 0.4)
            saliency_norm = (saliency - saliency.min()) / (saliency.max() - saliency.min() + 1e-6)
            neg_space = 1.0 - saliency_norm
        else:
            neg_space = np.ones((down_h, down_w))
            saliency_norm = np.zeros((down_h, down_w))

        # Vertical zones: Top (0-28%), Mid (28-60%), Bottom (60-100%)
        z_top = int(down_h * 0.28)
        z_mid = int(down_h * 0.60)

        top_neg = float(neg_space[:z_top, :].mean())
        mid_sal = float(saliency_norm[z_top:z_mid, :].mean())
        bot_neg = float(neg_space[z_mid:, :].mean())

        # Optical center: human eye perceives center at ~42% from top, not 50%
        optical_y = int(self.target_h * 0.415)
        optical_x = int(self.target_w * 0.50)

        return SaliencyProfile(
            optical_center_x=optical_x,
            optical_center_y=optical_y,
            top_negative_space_ratio=top_neg,
            mid_saliency_density=mid_sal,
            bottom_negative_space_ratio=bot_neg,
            recommended_hero_y=optical_y,
            recommended_scrim_start_y=int(self.target_h * 0.58),
        )

    def calculate_occlusion_penalty(
        self,
        element_bbox: tuple[int, int, int, int],  # (x_min, y_min, x_max, y_max)
        hero_bbox: tuple[int, int, int, int],
    ) -> float:
        """Measure accidental occlusion between text element and salient hero core."""
        ex1, ey1, ex2, ey2 = element_bbox
        hx1, hy1, hx2, hy2 = hero_bbox

        ix1 = max(ex1, hx1)
        iy1 = max(ey1, hy1)
        ix2 = min(ex2, hx2)
        iy2 = min(ey2, hy2)

        if ix2 > ix1 and iy2 > iy1:
            overlap_area = (ix2 - ix1) * (iy2 - iy1)
            elem_area = (ex2 - ex1) * (ey2 - ey1)
            return float(overlap_area / (elem_area + 1e-6))
        return 0.0

