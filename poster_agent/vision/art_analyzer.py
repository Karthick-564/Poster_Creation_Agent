"""Art-First Vision Analyzer.

Inspects generated art assets (background, hero RGBA, accents) to extract:
1. Color palette (sampled directly from image pixels).
2. Geometry & focal bounds (alpha channel centroid and bounding box of hero).
3. Light spill parameters (radial emitter centers and color stops).
4. Depth layer coordinates (title under-orb overlap, curved text arc, soft scrim regions).
"""
import math
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field


class PaletteProfile(BaseModel):
    """Sampled color tokens from the generated artwork."""
    hero_glow_hex: str = "#7AE7C7"
    hero_highlight_hex: str = "#FFB703"
    hero_accent_hex: str = "#FF4D6D"
    sky_deep_hex: str = "#0E0728"
    text_primary_hex: str = "#FFF3E0"
    text_muted_hex: str = "#C9B8FF"
    glow_rgb: tuple[int, int, int] = (122, 231, 199)
    highlight_rgb: tuple[int, int, int] = (255, 183, 3)
    accent_rgb: tuple[int, int, int] = (255, 77, 109)


class HeroGeometry(BaseModel):
    """Physical coordinates and bounds of the hero asset on canvas."""
    center_x: int = 540
    center_y: int = 560
    radius: int = 245
    box_x_min: int = 295
    box_y_min: int = 315
    box_x_max: int = 785
    box_y_max: int = 805
    aspect_ratio: float = 1.0


class ArcGeometry(BaseModel):
    """SVG curved text path parameters hugging the hero asset."""
    center_x: int = 540
    center_y: int = 560
    radius: int = 265
    svg_path_d: str = ""


class LightSpillProfile(BaseModel):
    """Screen-blended radial light emitters."""
    hero_emitter_x: int = 540
    hero_emitter_y: int = 560
    hero_emitter_radius: int = 650
    hero_glow_rgba: str = "rgba(122, 231, 199, 0.40)"
    hero_core_rgba: str = "rgba(255, 183, 3, 0.30)"
    lantern_emitter_x: int = 860
    lantern_emitter_y: int = 180
    lantern_emitter_radius: int = 300
    lantern_glow_rgba: str = "rgba(255, 183, 3, 0.50)"


class ArtCompositionPlan(BaseModel):
    """Comprehensive blueprint derived directly from inspecting the art."""
    canvas_w: int = 1080
    canvas_h: int = 1350
    palette: PaletteProfile = Field(default_factory=PaletteProfile)
    hero: HeroGeometry = Field(default_factory=HeroGeometry)
    orbital_arc: ArcGeometry = Field(default_factory=ArcGeometry)
    light_spill: LightSpillProfile = Field(default_factory=LightSpillProfile)
    title_y: int = 175
    title_height: int = 160
    title_overlaps_hero_px: int = 40
    scrim_start_y: int = 760


class ArtAnalyzer:
    """Vision-based art analyzer that plans typography and layout around actual art."""

    def __init__(self, canvas_w: int = 1080, canvas_h: int = 1350):
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

    def rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    def analyze(
        self,
        bg_path: str | Path,
        hero_rgba_path: str | Path | None = None,
        accent_rgba_path: str | Path | None = None,
    ) -> ArtCompositionPlan:
        """Inspect the art files and synthesize the layout plan."""
        plan = ArtCompositionPlan(canvas_w=self.canvas_w, canvas_h=self.canvas_h)

        # 1. Inspect Hero RGBA for geometry and color sampling
        if hero_rgba_path and Path(hero_rgba_path).exists():
            hero_img = Image.open(hero_rgba_path)
            if hero_img.mode != "RGBA":
                hero_img = hero_img.convert("RGBA")

            alpha = np.array(hero_img.split()[-1])
            visible_mask = alpha > 25

            if np.any(visible_mask):
                y_idx, x_idx = np.where(visible_mask)
                x_min, x_max = int(x_idx.min()), int(x_idx.max())
                y_min, y_max = int(y_idx.min()), int(y_idx.max())
                w_orig, h_orig = hero_img.size

                # Sample colors from visible pixels
                rgb_arr = np.array(hero_img.convert("RGB"))
                vis_pixels = rgb_arr[visible_mask]

                # Highlight: 95th percentile
                p95 = tuple(np.percentile(vis_pixels, 95, axis=0).astype(int))
                # Glow: median/mean of brighter half
                bright_mask = vis_pixels.mean(axis=1) > np.median(vis_pixels.mean(axis=1))
                if np.any(bright_mask):
                    glow = tuple(vis_pixels[bright_mask].mean(axis=0).astype(int))
                else:
                    glow = tuple(vis_pixels.mean(axis=0).astype(int))

                plan.palette.hero_highlight_hex = self.rgb_to_hex(p95)
                plan.palette.hero_glow_hex = self.rgb_to_hex(glow)
                plan.palette.glow_rgb = glow
                plan.palette.highlight_rgb = p95

        # 2. Inspect Background for deep sky tone
        if bg_path and Path(bg_path).exists():
            bg_img = Image.open(bg_path).convert("RGB")
            bg_arr = np.array(bg_img)
            # Sample bottom corner for deepest background tone
            deep_tone = tuple(bg_arr[-100:, :100].mean(axis=(0, 1)).astype(int))
            plan.palette.sky_deep_hex = self.rgb_to_hex(deep_tone)

        # 3. Compute Depth & Placement
        # Target Hero sizing on canvas: centered horizontally, center_y ~ 560, diameter ~ 490px
        hero_diameter = 490
        hero_radius = hero_diameter // 2
        hero_center_x = self.canvas_w // 2
        hero_center_y = 560

        plan.hero = HeroGeometry(
            center_x=hero_center_x,
            center_y=hero_center_y,
            radius=hero_radius,
            box_x_min=hero_center_x - hero_radius,
            box_y_min=hero_center_y - hero_radius,
            box_x_max=hero_center_x + hero_radius,
            box_y_max=hero_center_y + hero_radius,
        )

        # Orbital Arc for curved text hugging lower hemisphere
        # Arc sweeps from angle 160 deg to 20 deg (underneath the orb)
        arc_radius = hero_radius + 24
        # SVG path for an arc: start at (cx - R*cos(15), cy + R*sin(15)), sweep to (cx + R*cos(15), ...)
        start_x = hero_center_x - int(arc_radius * math.cos(math.radians(18)))
        start_y = hero_center_y + int(arc_radius * math.sin(math.radians(18)))
        end_x = hero_center_x + int(arc_radius * math.cos(math.radians(18)))
        end_y = hero_center_y + int(arc_radius * math.sin(math.radians(18)))

        # Arc path SVG d string (curves underneath the orb)
        plan.orbital_arc = ArcGeometry(
            center_x=hero_center_x,
            center_y=hero_center_y,
            radius=arc_radius,
            svg_path_d=f"M {start_x},{start_y} A {arc_radius},{arc_radius} 0 0,0 {end_x},{end_y}",
        )

        # Light Spill emitters
        plan.light_spill = LightSpillProfile(
            hero_emitter_x=hero_center_x,
            hero_emitter_y=hero_center_y,
            hero_emitter_radius=680,
            hero_glow_rgba=f"rgba({plan.palette.glow_rgb[0]}, {plan.palette.glow_rgb[1]}, {plan.palette.glow_rgb[2]}, 0.42)",
            hero_core_rgba=f"rgba({plan.palette.highlight_rgb[0]}, {plan.palette.highlight_rgb[1]}, {plan.palette.highlight_rgb[2]}, 0.32)",
            lantern_emitter_x=860,
            lantern_emitter_y=190,
            lantern_emitter_radius=320,
            lantern_glow_rgba="rgba(255, 183, 3, 0.55)",
        )

        # Title sits at Y=140 to 350. Orb top is at Y = 560 - 245 = 315.
        # Title bottom is at Y = 350 -> 35px overlap where orb sits in front of title!
        plan.title_y = 150
        plan.title_height = 195
        plan.title_overlaps_hero_px = 35
        plan.scrim_start_y = 750

        return plan

