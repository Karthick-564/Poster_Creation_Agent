"""Palette Policy & Chromatic Validation Engine.

Implements:
1. Priority resolution: (1) brief palette -> (2) hero-derived palette -> (3) genre preset config.
2. Soft 60-30-10 role-based color assignment with +/-15% tolerance.
3. WCAG contrast ratio calculations for body (>=4.5:1) and large display (>=3.0:1).
4. Hue family clustering and counter with 360-degree circular red wrap-around.
5. DOM color validation returning typed patch actions.
"""
import colorsys
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import yaml


@dataclass
class ResolvedPalette:
    """Resolved color palette with role assignments."""
    source: Literal["brief", "hero_derived", "genre_preset"]
    canvas_base: str       # 60% dominant (background / negative space)
    structural: str        # 30% structural (body text, dates, venues, primary headers)
    accent: str            # 10% high-impact accent (focal pop: prize, CTA)
    secondary_accent: str  # Optional secondary accent if allowed
    surface: str           # Subtle card/line backdrop tone
    palette_list: list[str] = field(default_factory=list)
    title_treatment: str = "css_gradient_glow"


@dataclass
class ValidationIssue:
    """A chromatic issue detected by the palette validator."""
    issue_type: str
    severity: Literal["blocking", "warning", "info"]
    message: str
    element_id: str | None = None
    role: str | None = None
    measured_value: float | None = None
    target_value: float | None = None
    suggested_patch: dict[str, Any] | None = None


@dataclass
class PaletteValidationReport:
    """Report produced by the palette validator."""
    passed: bool
    blocking_count: int
    warning_count: int
    issues: list[ValidationIssue]
    contrast_checks: list[dict[str, Any]]
    hue_family_count: int
    area_shares: dict[str, float]


class PalettePolicy:
    """Loads config and resolves/validates poster color harmony."""

    DEFAULT_CONFIG_PATH = Path("configs/palette_policy.yaml")

    def __init__(self, config_path: Path | str | None = None):
        cfg_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = {}

        self.policy_cfg = self.config.get("palette", {})
        self.max_accent_hues = self.policy_cfg.get("max_accent_hues", 1)
        self.role_targets = self.policy_cfg.get("role_targets", {"canvas_base": 0.60, "structural": 0.30, "accent": 0.10})
        self.role_tolerance = self.policy_cfg.get("role_tolerance", 0.15)
        self.contrast_thresholds = self.policy_cfg.get("contrast_thresholds", {"body": 4.5, "large_display": 3.0})
        self.presets = self.config.get("genre_presets", {})

    # -------------------------------------------------------------------------
    # 1. RESOLUTION HIERARCHY
    # Priority: (1) brief palette -> (2) hero-derived palette -> (3) genre preset
    # -------------------------------------------------------------------------
    def resolve_palette(
        self,
        brief_palette: list[str] | None = None,
        hero_image_path: Path | str | None = None,
        genre_hint: str = "default",
        requested_title_treatment: str | None = None,
    ) -> ResolvedPalette:
        """Resolve final color palette following strict priority hierarchy."""
        preset = self.presets.get(genre_hint, self.presets.get("default", {
            "canvas_base": "#0B132B",
            "structural": "#FFFFFF",
            "accent": "#00F5D4",
            "secondary_accent": "#00BBF9",
            "surface": "#1C2541",
            "title_treatment": "css_gradient_glow",
        }))

        # Priority 1: Brief palette (NEVER overridden if valid hex codes given)
        cleaned_brief = self._clean_hex_list(brief_palette) if brief_palette else []
        if len(cleaned_brief) >= 2:
            return self._build_from_list(cleaned_brief, source="brief", preset=preset, requested_title_treatment=requested_title_treatment)

        # Priority 2: Palette derived from generated hero/art
        if hero_image_path and Path(hero_image_path).exists():
            extracted = self.extract_palette_from_image(hero_image_path)
            if len(extracted) >= 2:
                return self._build_from_list(extracted, source="hero_derived", preset=preset, requested_title_treatment=requested_title_treatment)

        # Priority 3: Genre preset as last resort
        title_treatment = requested_title_treatment or preset.get("title_treatment", "css_gradient_glow")
        return ResolvedPalette(
            source="genre_preset",
            canvas_base=preset.get("canvas_base", "#0B132B"),
            structural=preset.get("structural", "#FFFFFF"),
            accent=preset.get("accent", "#00F5D4"),
            secondary_accent=preset.get("secondary_accent", "#00BBF9"),
            surface=preset.get("surface", "#1C2541"),
            palette_list=[
                preset.get("canvas_base", "#0B132B"),
                preset.get("structural", "#FFFFFF"),
                preset.get("accent", "#00F5D4"),
                preset.get("secondary_accent", "#00BBF9"),
            ],
            title_treatment=title_treatment,
        )

    def _build_from_list(
        self,
        hex_list: list[str],
        source: Literal["brief", "hero_derived"],
        preset: dict[str, Any],
        requested_title_treatment: str | None = None,
    ) -> ResolvedPalette:
        """Assign roles from a raw hex list based on luminance and saturation."""
        # Sort colors by relative luminance
        sorted_by_lum = sorted(hex_list, key=self.calculate_relative_luminance)
        
        # In design briefs, the first color listed is conventionally the intended background / canvas tone!
        # If the first color in hex_list is very light (lum > 0.5), it's a light canvas.
        # If the first color is dark (lum <= 0.5), it's a dark canvas.
        first_lum = self.calculate_relative_luminance(hex_list[0])
        max_lum = max(self.calculate_relative_luminance(c) for c in hex_list)
        min_lum = min(self.calculate_relative_luminance(c) for c in hex_list)

        if first_lum > 0.5 or (first_lum == max_lum and max_lum > 0.4):
            is_dark_canvas = False
        else:
            is_dark_canvas = True

        if is_dark_canvas:
            canvas_base = hex_list[0] if first_lum <= 0.25 else sorted_by_lum[0]
            structural = sorted_by_lum[-1]          # Brightest tone (maximum text contrast)
            other_colors = [c for c in hex_list if c not in (canvas_base, structural)]
            if other_colors:
                other_colors.sort(key=lambda c: self.get_hsv(c)[1], reverse=True)
                accent = other_colors[0]
                secondary_accent = other_colors[1] if len(other_colors) > 1 else accent
            else:
                accent = preset.get("accent", "#00F5D4")
                secondary_accent = preset.get("secondary_accent", "#00BBF9")
            surface = sorted_by_lum[1] if len(sorted_by_lum) > 2 else canvas_base
        else:
            # Light canvas (e.g. GREEN LOOP warm daylight / paper-cut #F4EBD0)
            canvas_base = hex_list[0] if first_lum >= 0.5 else sorted_by_lum[-1]
            structural = sorted_by_lum[0]           # Darkest tone (e.g. #1F2A24 for readability)
            other_colors = [c for c in hex_list if c not in (canvas_base, structural)]
            if other_colors:
                other_colors.sort(key=lambda c: self.get_hsv(c)[1], reverse=True)
                accent = other_colors[0]
                secondary_accent = other_colors[1] if len(other_colors) > 1 else accent
            else:
                accent = preset.get("accent", "#E9A23B")
                secondary_accent = preset.get("secondary_accent", "#2F5D50")
            surface = sorted_by_lum[-2] if len(sorted_by_lum) > 2 else canvas_base

        title_treatment = requested_title_treatment or preset.get("title_treatment", "css_gradient_glow")
        return ResolvedPalette(
            source=source,
            canvas_base=canvas_base,
            structural=structural,
            accent=accent,
            secondary_accent=secondary_accent,
            surface=surface,
            palette_list=hex_list,
            title_treatment=title_treatment,
        )

    # -------------------------------------------------------------------------
    # 2. ROLE-BASED COLOR ASSIGNMENT FOR TEXT & CSS
    # -------------------------------------------------------------------------
    def assign_role_colors(self, palette: ResolvedPalette) -> dict[str, str]:
        """Map typography and UI roles strictly to resolved palette tones with WCAG contrast enforcement."""
        def ensure_contrast(color: str, min_ratio: float = 4.5) -> str:
            if self.calculate_contrast_ratio(color, palette.canvas_base) >= min_ratio:
                return color
            candidates = [c for c in palette.palette_list if self.calculate_contrast_ratio(c, palette.canvas_base) >= min_ratio]
            if candidates:
                target_h = self.get_hsv(color)[0]
                candidates.sort(key=lambda c: abs(self.get_hsv(c)[0] - target_h))
                return candidates[0]
            return palette.structural

        accent_text = ensure_contrast(palette.accent, 4.5)
        secondary_text = ensure_contrast(palette.secondary_accent, 4.5)
        prize_text = ensure_contrast(palette.accent, 4.5)

        return {
            "title": palette.structural,
            "subtitle": accent_text,
            "tagline": secondary_text,
            "date": palette.structural,
            "time": palette.structural,
            "venue": palette.structural,
            "events": palette.structural,
            "prize": prize_text,
            "cta": accent_text,
            "organizer": secondary_text,
            "blurb": palette.structural,
            "divider": palette.secondary_accent,
            "surface_bg": palette.surface,
            "canvas_bg": palette.canvas_base,
        }

    def generate_css_variables(self, palette: ResolvedPalette) -> str:
        """Emit CSS root variables for seamless template consumption."""
        role_map = self.assign_role_colors(palette)
        r, g, b = self.hex_to_rgb(palette.canvas_base)
        lum = self.calculate_relative_luminance(palette.canvas_base)
        if lum > 0.45:
            # Light canvas: soft ambient scrim matching canvas tone
            scrim_gradient = f"linear-gradient(to top, rgba({r},{g},{b},0.96) 0%, rgba({r},{g},{b},0.82) 65%, transparent 100%)"
        else:
            # Dark canvas: deep atmospheric charcoal/navy scrim
            scrim_gradient = "linear-gradient(to top, rgba(10, 14, 23, 0.94) 0%, rgba(10, 14, 23, 0.75) 60%, transparent 100%)"

        lines = [":root {"]
        lines.append(f"  --color-canvas-base: {palette.canvas_base};")
        lines.append(f"  --color-structural: {palette.structural};")
        lines.append(f"  --color-accent: {palette.accent};")
        lines.append(f"  --color-secondary-accent: {palette.secondary_accent};")
        lines.append(f"  --color-surface: {palette.surface};")
        lines.append(f"  --scrim-gradient: {scrim_gradient};")
        for role, col in role_map.items():
            lines.append(f"  --role-{role}-color: {col};")
        lines.append("}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 3. COLOR MATH (CONTRAST, LUMINANCE, HSV)
    # -------------------------------------------------------------------------
    @staticmethod
    def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
        """Convert #RRGGBB or #RGB to (R, G, B) tuple 0-255."""
        h = hex_code.strip().lstrip("#")
        if len(h) == 3:
            h = "".join([c * 2 for c in h])
        if len(h) != 6:
            return (128, 128, 128)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @classmethod
    def calculate_relative_luminance(cls, hex_code: str) -> float:
        """Calculate WCAG 2.1 relative luminance (0.0 to 1.0)."""
        r, g, b = cls.hex_to_rgb(hex_code)
        rgb_norm = [c / 255.0 for c in (r, g, b)]
        rgb_linear = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            for c in rgb_norm
        ]
        return 0.2126 * rgb_linear[0] + 0.7152 * rgb_linear[1] + 0.0722 * rgb_linear[2]

    @classmethod
    def calculate_contrast_ratio(cls, hex1: str, hex2: str) -> float:
        """Calculate WCAG 2.1 contrast ratio between two hex colors (1.0 to 21.0)."""
        l1 = cls.calculate_relative_luminance(hex1)
        l2 = cls.calculate_relative_luminance(hex2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def get_hsv(cls, hex_code: str) -> tuple[float, float, float]:
        """Return (hue 0..360, saturation 0..1, value 0..1)."""
        r, g, b = cls.hex_to_rgb(hex_code)
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        return (h * 360.0, s, v)

    # -------------------------------------------------------------------------
    # 4. HUE FAMILY CLUSTERING WITH 360-DEGREE RED WRAP-AROUND
    # -------------------------------------------------------------------------
    @classmethod
    def count_saturated_hue_families(
        cls,
        colors: list[str],
        sat_threshold: float = 0.20,
        val_threshold: float = 0.15,
        cluster_angle_deg: float = 35.0,
    ) -> int:
        """Cluster saturated colors into distinct hue families, handling red wrap-around near 0/360."""
        saturated_hues = []
        for col in colors:
            h, s, v = cls.get_hsv(col)
            # Filter out achromatic colors (pure white, deep black, gray)
            if s >= sat_threshold and v >= val_threshold:
                saturated_hues.append(h)

        if not saturated_hues:
            return 0

        # Cluster hues on a circular 360-degree ring
        clusters: list[list[float]] = []
        for h in saturated_hues:
            matched_cluster = None
            for c in clusters:
                # Circular distance
                for member in c:
                    diff = abs(h - member)
                    circular_dist = min(diff, 360.0 - diff)
                    if circular_dist <= cluster_angle_deg:
                        matched_cluster = c
                        break
                if matched_cluster:
                    break

            if matched_cluster:
                matched_cluster.append(h)
            else:
                clusters.append([h])

        return len(clusters)

    # -------------------------------------------------------------------------
    # 5. VALIDATOR: CONTRAST, HUE FAMILIES, & AREA SHARES
    # -------------------------------------------------------------------------
    def validate_rendered_palette(
        self,
        palette: ResolvedPalette,
        rendered_elements: list[dict[str, Any]],
        canvas_bg: str | None = None,
    ) -> PaletteValidationReport:
        """Validate rendered colors, checking WCAG contrast, hue families, and role shares."""
        issues: list[ValidationIssue] = []
        contrast_checks: list[dict[str, Any]] = []
        bg_col = canvas_bg or palette.canvas_base

        # 1. Contrast checks per role
        for elem in rendered_elements:
            elem_id = elem.get("id", "elem")
            role = elem.get("role", "body")
            fg_col = elem.get("color", palette.structural)
            local_bg = elem.get("bg_color", bg_col)
            contrast = self.calculate_contrast_ratio(fg_col, local_bg)

            # Determine threshold
            is_large = role in ("title", "headline", "prize") or elem.get("font_size_pt", 16) >= 24
            thresh = self.contrast_thresholds["large_display"] if is_large else self.contrast_thresholds["body"]

            check_entry = {
                "element_id": elem_id,
                "role": role,
                "color": fg_col,
                "bg_color": local_bg,
                "contrast_ratio": round(contrast, 2),
                "threshold": thresh,
                "passed": contrast >= thresh,
            }
            contrast_checks.append(check_entry)

            # Contrast below threshold is BLOCKING
            if contrast < thresh:
                suggested_col = "#FFFFFF" if self.calculate_relative_luminance(local_bg) < 0.5 else "#1A1A1A"
                issues.append(ValidationIssue(
                    issue_type="contrast_below_threshold",
                    severity="blocking",
                    message=f"Element '{elem_id}' ({role}) contrast {contrast:.2f}:1 is below required {thresh}:1 against {local_bg}.",
                    element_id=elem_id,
                    role=role,
                    measured_value=contrast,
                    target_value=thresh,
                    suggested_patch={"action": "set_color", "element_id": elem_id, "color": suggested_col},
                ))

        # 2. Hue family check (Non-blocking warning with typed patch action)
        rendered_colors = [e.get("color") for e in rendered_elements if e.get("color")]
        hue_count = self.count_saturated_hue_families(rendered_colors)
        if hue_count > (self.max_accent_hues + 1):  # base accents + 1 structural
            issues.append(ValidationIssue(
                issue_type="too_many_hue_families",
                severity="warning",
                message=f"Poster contains {hue_count} distinct saturated hue families (max configured: {self.max_accent_hues}). Rainbow anti-pattern detected.",
                measured_value=float(hue_count),
                target_value=float(self.max_accent_hues),
                suggested_patch={"action": "unify_accents", "target_color": palette.accent},
            ))

        # 3. Approximate area share calculation
        total_chars = sum(len(e.get("text", "")) for e in rendered_elements) or 1
        role_chars: dict[str, int] = {}
        for e in rendered_elements:
            r = e.get("role", "body")
            role_chars[r] = role_chars.get(r, 0) + len(e.get("text", ""))

        area_shares = {r: count / total_chars for r, count in role_chars.items()}

        blocking_count = sum(1 for i in issues if i.severity == "blocking")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        return PaletteValidationReport(
            passed=blocking_count == 0,
            blocking_count=blocking_count,
            warning_count=warning_count,
            issues=issues,
            contrast_checks=contrast_checks,
            hue_family_count=hue_count,
            area_shares=area_shares,
        )

    # -------------------------------------------------------------------------
    # 6. HERO ART EXTRACTION (K-MEANS / OPENCV)
    # -------------------------------------------------------------------------
    @classmethod
    def extract_palette_from_image(cls, image_path: Path | str, k: int = 5) -> list[str]:
        """Extract dominant harmonious colors from hero image, excluding alpha."""
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            return []

        # Mask non-transparent pixels if 4-channel
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            valid_pixels = img[alpha > 80][:, :3]
        else:
            valid_pixels = img[:, :, :3].reshape(-1, 3)

        if len(valid_pixels) < 100:
            return []

        # Downsample for fast clustering
        if len(valid_pixels) > 5000:
            indices = np.random.choice(len(valid_pixels), 5000, replace=False)
            valid_pixels = valid_pixels[indices]

        valid_pixels = np.float32(valid_pixels)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
        _, _, centers = cv2.kmeans(valid_pixels, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS)

        hex_colors = []
        for bgr in centers:
            b, g, r = [int(np.clip(c, 0, 255)) for c in bgr]
            hex_colors.append(f"#{r:02X}{g:02X}{b:02X}")

        return hex_colors

    @staticmethod
    def _clean_hex_list(colors: list[str] | str) -> list[str]:
        """Filter and normalize hex codes from text strings or lists."""
        if isinstance(colors, str):
            # Extract all hex codes using regex from space-separated or raw string
            matches = re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", colors)
            cleaned = []
            for val in matches:
                if len(val) == 3:
                    val = "".join([ch * 2 for ch in val])
                cleaned.append(f"#{val.upper()}")
            return cleaned

        cleaned = []
        for c in colors:
            match = re.search(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", c)
            if match:
                val = match.group(1)
                if len(val) == 3:
                    val = "".join([ch * 2 for ch in val])
                cleaned.append(f"#{val.upper()}")
        return cleaned
