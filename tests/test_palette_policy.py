"""Unit tests for PalettePolicy, Chromatic Math, Hue Clustering, and Contrast Gates."""
import pytest
from pathlib import Path
from poster_agent.palette_policy import PalettePolicy, ResolvedPalette


@pytest.fixture
def policy():
    return PalettePolicy("configs/palette_policy.yaml")


# -----------------------------------------------------------------------------
# 1. RESOLUTION PRIORITY TESTS
# -----------------------------------------------------------------------------
def test_palette_priority_brief_wins(policy, tmp_path):
    """Priority 1: Brief palette must NEVER be overridden by hero or preset."""
    brief_colors = ["#F4EBD0", "#2F5D50", "#E9A23B", "#C8553D", "#1F2A24"]
    # Even with a genre hint like 'cyber_ctf', brief palette must win!
    resolved = policy.resolve_palette(
        brief_palette=brief_colors,
        hero_image_path=None,
        genre_hint="cyber_ctf"
    )
    assert resolved.source == "brief"
    assert resolved.canvas_base == "#F4EBD0"  # Light canvas recognized
    assert resolved.structural == "#1F2A24"   # Dark high-contrast text recognized
    assert any(c in brief_colors for c in [resolved.accent, resolved.secondary_accent])


def test_palette_priority_hero_derived_when_no_brief(policy, tmp_path):
    """Priority 2: Hero-derived palette used when brief palette is absent."""
    import cv2
    import numpy as np

    # Create synthetic hero image with emerald greens
    dummy_hero = tmp_path / "dummy_hero.png"
    img = np.zeros((100, 100, 4), dtype=np.uint8)
    img[:, :, 0] = 50   # B
    img[:, :, 1] = 200  # G (emerald)
    img[:, :, 2] = 30   # R
    img[:, :, 3] = 255  # Alpha
    cv2.imwrite(str(dummy_hero), img)

    resolved = policy.resolve_palette(
        brief_palette=[],
        hero_image_path=dummy_hero,
        genre_hint="aurora"
    )
    assert resolved.source == "hero_derived"
    assert len(resolved.palette_list) >= 2


def test_palette_priority_preset_fallback_as_last_resort(policy):
    """Priority 3: Preset fallback used only when brief and hero are missing."""
    resolved = policy.resolve_palette(
        brief_palette=None,
        hero_image_path=None,
        genre_hint="green_loop"
    )
    assert resolved.source == "genre_preset"
    assert resolved.canvas_base == "#061A14"
    assert resolved.accent == "#10B981"
    assert resolved.title_treatment == "flat"


# -----------------------------------------------------------------------------
# 2. ROLE-BASED COLOR ASSIGNMENT
# -----------------------------------------------------------------------------
def test_role_based_color_assignment(policy):
    """Roles must map predictably to structural, accent, and base colors."""
    palette = ResolvedPalette(
        source="brief",
        canvas_base="#0A0E17",
        structural="#F0F6FC",
        accent="#00FF9C",
        secondary_accent="#00D1FF",
        surface="#161B22",
        palette_list=["#0A0E17", "#00FF9C", "#00D1FF", "#F0F6FC"],
    )
    roles = policy.assign_role_colors(palette)
    assert roles["title"] == palette.structural
    assert roles["date"] == palette.structural
    assert roles["venue"] == palette.structural
    assert roles["prize"] == palette.accent
    assert roles["cta"] == palette.accent
    assert roles["canvas_bg"] == palette.canvas_base


# -----------------------------------------------------------------------------
# 3. CONTRAST MATH & WCAG GATES
# -----------------------------------------------------------------------------
def test_contrast_ratio_math(policy):
    """Verify WCAG contrast calculation against known pairs."""
    # Pure black vs pure white: 21.0
    c_bw = policy.calculate_contrast_ratio("#000000", "#FFFFFF")
    assert round(c_bw, 1) == 21.0

    # Same color: 1.0
    c_same = policy.calculate_contrast_ratio("#2F5D50", "#2F5D50")
    assert round(c_same, 1) == 1.0

    # Dark text on cream background (Green loop)
    c_green = policy.calculate_contrast_ratio("#1F2A24", "#F4EBD0")
    assert c_green >= 7.0  # Outstanding contrast!


def test_validator_detects_blocking_contrast_failure(policy):
    """Validator must produce a blocking failure when contrast is below threshold."""
    palette = ResolvedPalette(
        source="brief",
        canvas_base="#0A0E17",
        structural="#F0F6FC",
        accent="#00FF9C",
        secondary_accent="#00D1FF",
        surface="#161B22",
    )
    # Intentionally low contrast element (dark gray on near-black)
    bad_elements = [
        {"id": "headline", "role": "title", "color": "#1A202C", "bg_color": "#0A0E17", "font_size_pt": 36},
    ]
    report = policy.validate_rendered_palette(palette, bad_elements)
    assert report.passed is False
    assert report.blocking_count >= 1
    assert any(i.severity == "blocking" for i in report.issues)


# -----------------------------------------------------------------------------
# 4. HUE FAMILY CLUSTERING WITH CIRCULAR RED WRAP-AROUND
# -----------------------------------------------------------------------------
def test_hue_family_circular_wrap_around(policy):
    """Hues near 355 deg (deep crimson) and 5 deg (red-orange) must cluster together as 1 hue."""
    crimson = "#FF0015"     # ~355 deg
    red_orange = "#FF2200"  # ~8 deg
    # In a naive distance (355 - 8 = 347 deg), they look like opposite ends!
    # Circular distance min(347, 360-347) = 13 deg <= 35 deg -> 1 cluster!
    cluster_count = policy.count_saturated_hue_families([crimson, red_orange])
    assert cluster_count == 1, f"Expected 1 wrapped cluster for red hues, got {cluster_count}"


def test_hue_family_multi_hues_detection(policy):
    """Distinct hues (Red, Green, Blue) must count as 3 separate families."""
    colors = [
        "#FF0000",  # Red (~0 deg)
        "#00FF00",  # Green (~120 deg)
        "#0000FF",  # Blue (~240 deg)
    ]
    count = policy.count_saturated_hue_families(colors)
    assert count == 3

