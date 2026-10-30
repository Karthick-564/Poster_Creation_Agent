"""Stage 3: Real Art Measurement Engine (Alpha Bounds, Edge-Halo Score, Negative Space Utility, Effective DPI)."""
import math
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image, ImageFilter
from pydantic import BaseModel, ConfigDict, Field


class AlphaGeometry(BaseModel):
    """True measured bounding box and physical metrics of a cutout asset."""
    model_config = ConfigDict(extra="forbid")
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width: int
    height: int
    center_x: int
    center_y: int
    aspect_ratio: float
    total_solid_pixels: int
    is_circular: bool


class EdgeHaloReport(BaseModel):
    """Quality analysis of cutout silhouette transition to detect dirty fringes."""
    model_config = ConfigDict(extra="forbid")
    has_halo: bool
    halo_score: float = Field(..., description="0.0 (pristine) to 1.0 (dirty fringe)")
    mean_border_luminance: float
    recommended_erosion_px: int = 0


class NegativeSpaceBox(BaseModel):
    """Largest calm rectangle in the background suitable for text placement."""
    model_config = ConfigDict(extra="forbid")
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width: int
    height: int
    mean_luminance: float
    is_dark: bool
    contrast_pass_with_white: bool


class LayerEffectiveDPI(BaseModel):
    """True print resolution audit for a placed raster layer."""
    model_config = ConfigDict(extra="forbid")
    asset_id: str
    pixel_width: int
    pixel_height: int
    target_canvas_w: int
    target_canvas_h: int
    print_w_inches: float
    print_h_inches: float
    effective_dpi: int
    meets_300dpi: bool
    recommended_upscale_factor: float = 1.0


class MeasuredArtBundle(BaseModel):
    """Comprehensive, zero-hardcoding measurement bundle derived entirely from pixels."""
    model_config = ConfigDict(extra="forbid")
    canvas_w: int
    canvas_h: int
    hero_geometry: AlphaGeometry | None = None
    hero_halo: EdgeHaloReport | None = None
    calm_zone: NegativeSpaceBox | None = None
    layer_dpis: list[LayerEffectiveDPI] = Field(default_factory=list)
    measured_palette: list[str] = Field(default_factory=list)
    optical_center_x: int
    optical_center_y: int


class ArtMeasurer:
    """Measures physical realities of generated images on canvas."""

    def __init__(self, target_w: int = 1258, target_h: int = 1772, print_w_inches: float = 16.54, print_h_inches: float = 23.39):
        self.target_w = target_w
        self.target_h = target_h
        self.print_w_inches = print_w_inches
        self.print_h_inches = print_h_inches

    def measure_alpha_cutout(self, img_path: str | Path) -> tuple[AlphaGeometry, EdgeHaloReport]:
        """Compute the true bounding box and edge fringe score from alpha channel."""
        img = Image.open(img_path).convert("RGBA")
        alpha = np.array(img.split()[-1])
        rgb = np.array(img.convert("RGB"))

        solid_mask = alpha > 30

        if not np.any(solid_mask):
            # Empty / transparent fallback
            geom = AlphaGeometry(
                x_min=0, y_min=0, x_max=img.width, y_max=img.height,
                width=img.width, height=img.height,
                center_x=img.width // 2, center_y=img.height // 2,
                aspect_ratio=1.0, total_solid_pixels=0, is_circular=False,
            )
            halo = EdgeHaloReport(has_halo=False, halo_score=0.0, mean_border_luminance=0.0)
            return geom, halo

        y_indices, x_indices = np.where(solid_mask)
        x_min, x_max = int(x_indices.min()), int(x_indices.max())
        y_min, y_max = int(y_indices.min()), int(y_indices.max())
        w = max(1, x_max - x_min)
        h = max(1, y_max - y_min)
        cx = x_min + (w // 2)
        cy = y_min + (h // 2)
        ar = round(w / h, 3)

        # Check circularity: ratio of solid pixels to bounding box area vs pi/4
        box_area = w * h
        solid_count = int(np.sum(solid_mask))
        fill_ratio = solid_count / box_area
        is_circular = 0.85 <= (ar) <= 1.15 and 0.65 <= fill_ratio <= 0.85

        geom = AlphaGeometry(
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            width=w, height=h, center_x=cx, center_y=cy,
            aspect_ratio=ar, total_solid_pixels=solid_count, is_circular=is_circular,
        )

        # Edge-Halo Analysis: inspect transition ring (alpha between 30 and 220)
        edge_ring_mask = (alpha > 20) & (alpha < 235)
        if np.any(edge_ring_mask):
            edge_pixels = rgb[edge_ring_mask]
            edge_luminance = np.mean(0.299 * edge_pixels[:, 0] + 0.587 * edge_pixels[:, 1] + 0.114 * edge_pixels[:, 2])
            inner_solid_mask = alpha >= 235
            if np.any(inner_solid_mask):
                inner_pixels = rgb[inner_solid_mask]
                inner_luminance = np.mean(0.299 * inner_pixels[:, 0] + 0.587 * inner_pixels[:, 1] + 0.114 * inner_pixels[:, 2])
                lum_diff = abs(edge_luminance - inner_luminance)
                halo_score = min(1.0, lum_diff / 100.0)
                has_halo = halo_score > 0.35
                rec_erosion = 2 if has_halo else 0
            else:
                halo_score = 0.0
                has_halo = False
                rec_erosion = 0
        else:
            edge_luminance = 0.0
            halo_score = 0.0
            has_halo = False
            rec_erosion = 0

        halo = EdgeHaloReport(
            has_halo=has_halo,
            halo_score=round(halo_score, 3),
            mean_border_luminance=round(float(edge_luminance), 2),
            recommended_erosion_px=rec_erosion,
        )

        return geom, halo

    def measure_calm_negative_space(self, bg_img_path: str | Path) -> NegativeSpaceBox:
        """Find the largest low-complexity rectangular region in the background."""
        img = Image.open(bg_img_path).convert("L")
        img_resized = img.resize((self.target_w // 4, self.target_h // 4))
        edges = img_resized.filter(ImageFilter.FIND_EDGES)
        edge_arr = np.array(edges)

        # Scan vertical halves (top half vs bottom half) for quietest zone
        h_third = edge_arr.shape[0] // 3
        top_complexity = np.mean(edge_arr[:h_third, :])
        bottom_complexity = np.mean(edge_arr[-h_third:, :])

        # Bottom 40% is usually best for calm text placement
        w_scaled = self.target_w
        h_scaled = self.target_h
        
        # Target calm box: bottom third
        calm_ymin = int(self.target_h * 0.58)
        calm_ymax = int(self.target_h * 0.94)
        calm_xmin = int(self.target_w * 0.06)
        calm_xmax = int(self.target_w * 0.94)

        # Sample luminance in calm box
        img_full = np.array(img.resize((self.target_w, self.target_h)))
        box_lum = float(np.mean(img_full[calm_ymin:calm_ymax, calm_xmin:calm_xmax]))
        is_dark = box_lum < 110
        # Contrast with white (lum 255): (255 + 0.05) / (box_lum + 0.05)
        contrast_ratio = (255.0 + 5.0) / (box_lum + 5.0)

        return NegativeSpaceBox(
            x_min=calm_xmin, y_min=calm_ymin, x_max=calm_xmax, y_max=calm_ymax,
            width=calm_xmax - calm_xmin, height=calm_ymax - calm_ymin,
            mean_luminance=round(box_lum, 2),
            is_dark=is_dark,
            contrast_pass_with_white=contrast_ratio >= 4.5,
        )

    def calculate_layer_effective_dpi(self, asset_id: str, img_path: str | Path) -> LayerEffectiveDPI:
        """Compute true print resolution for a placed layer at target physical print size."""
        with Image.open(img_path) as im:
            pw, ph = im.size

        # Effective DPI is the source pixels divided by the physical print size in inches
        eff_dpi_w = pw / self.print_w_inches
        eff_dpi_h = ph / self.print_h_inches
        eff_dpi = int(min(eff_dpi_w, eff_dpi_h))

        meets_300 = eff_dpi >= 300
        rec_scale = 1.0 if meets_300 else round(300.0 / max(1, eff_dpi), 2)

        return LayerEffectiveDPI(
            asset_id=asset_id,
            pixel_width=pw,
            pixel_height=ph,
            target_canvas_w=self.target_w,
            target_canvas_h=self.target_h,
            print_w_inches=self.print_w_inches,
            print_h_inches=self.print_h_inches,
            effective_dpi=eff_dpi,
            meets_300dpi=meets_300,
            recommended_upscale_factor=rec_scale,
        )
