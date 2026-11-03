"""Unit tests for poster design quality metrics module."""
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

from poster_agent.qa.design import (
    asymmetry_index,
    evaluate_design_quality,
    focal_count,
    hero_presence,
    palette_coverage,
    type_scale_contrast,
    whitespace_balance,
)


def test_palette_coverage_matches():
    """Canvas painted with palette colors reports high coverage."""
    # Create 200x200 canvas with quadrants of 4 palette colors
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[0:100, 0:100] = [7, 11, 25]      # #070B19
    arr[0:100, 100:200] = [0, 245, 212]  # #00F5D4
    arr[100:200, 0:100] = [123, 47, 255] # #7B2FFF
    arr[100:200, 100:200] = [255, 61, 104] # #FF3D68

    im = Image.fromarray(arr)
    palette = ["#070B19", "#00F5D4", "#7B2FFF", "#FF3D68", "#F0F6FC"]
    res = palette_coverage(im, palette)
    # 4 out of 5 colors present
    assert res["coverage_ratio"] >= 0.8
    assert "#00F5D4" in res["represented_colors"]
    assert "#F0F6FC" in res["missing_colors"]


def test_type_scale_contrast():
    """Calculates max_size / min_size ratio correctly."""
    manifest = [
        {"role": "headline", "size": 96.0, "x": 60, "y": 200, "w": 600, "h": 110},
        {"role": "subtitle", "size": 24.0, "x": 60, "y": 350, "w": 400, "h": 30},
        {"role": "footer", "size": 16.0, "x": 60, "y": 1200, "w": 300, "h": 20},
    ]
    res = type_scale_contrast(manifest)
    assert res["max_size"] == 96.0
    assert res["min_size"] == 16.0
    assert res["ratio"] == 6.0
    assert res["dynamic_hierarchy"] is True

    # Boring single-size layout
    monotone = [{"size": 24.0}, {"size": 22.0}]
    mono_res = type_scale_contrast(monotone)
    assert mono_res["ratio"] < 2.0
    assert mono_res["dynamic_hierarchy"] is False


def test_asymmetry_index():
    """Measures horizontal center-of-mass offset from canvas center."""
    canvas_w = 1000.0

    # Centered rows (center at 500)
    centered_manifest = [
        {"x": 200, "y": 200, "width": 600, "height": 100},  # cx = 500
        {"x": 300, "y": 400, "width": 400, "height": 50},   # cx = 500
    ]
    cent_res = asymmetry_index(centered_manifest, canvas_w)
    assert cent_res["asymmetry_index"] == pytest.approx(0.0, abs=0.01)
    assert cent_res["is_asymmetric"] is False

    # Asymmetric rows (left anchored at x=80, width=400 -> cx=280)
    asym_manifest = [
        {"x": 80, "y": 200, "width": 400, "height": 100},   # cx = 280
        {"x": 80, "y": 350, "width": 300, "height": 50},    # cx = 230
    ]
    asym_res = asymmetry_index(asym_manifest, canvas_w)
    assert asym_res["asymmetry_index"] > 0.35
    assert asym_res["is_asymmetric"] is True


def test_hero_presence_and_void():
    """Detects near-black void hero vs textured/illuminated hero."""
    # Near black void image
    black_im = Image.new("RGB", (1000, 1000), (4, 4, 6))
    void_res = hero_presence(black_im, hero_rect=[100, 200, 600, 500])
    assert void_res["present"] is True
    assert void_res["is_void"] is True
    assert void_res["hero_score"] < 0.5

    # Rich illuminated hero image
    arr = np.random.randint(60, 220, (1000, 1000, 3), dtype=np.uint8)
    rich_im = Image.fromarray(arr)
    rich_res = hero_presence(rich_im, hero_rect=[100, 200, 600, 500])
    assert rich_res["present"] is True
    assert rich_res["is_void"] is False
    assert rich_res["hero_score"] >= 0.7


def test_hero_presence_asset_void_overrides_bright_destination(tmp_path):
    """A near-black hero asset is void even when the destination region is bright.

    Screen-blending black contributes nothing, so atmospheric glows in the
    hero rect must not rescue an invisible asset.
    """
    bright_im = Image.fromarray(
        np.random.randint(120, 220, (1000, 1000, 3), dtype=np.uint8)
    )
    # Asset is fully opaque near-black
    asset = Image.new("RGBA", (400, 400), (3, 3, 5, 255))
    asset_path = tmp_path / "near_black_hero.png"
    asset.save(asset_path)

    res = hero_presence(
        bright_im, hero_rect=[100, 200, 600, 500], hero_asset=asset_path
    )
    assert res["is_void"] is True
    assert res["asset_mean_luminance"] is not None
    assert res["asset_mean_luminance"] < 12.0
    assert res["hero_score"] < 0.5

    # A normal illuminated asset must not be flagged
    lit = Image.new("RGBA", (400, 400), (180, 170, 160, 255))
    lit_path = tmp_path / "lit_hero.png"
    lit.save(lit_path)
    lit_res = hero_presence(
        bright_im, hero_rect=[100, 200, 600, 500], hero_asset=lit_path
    )
    assert lit_res["is_void"] is False


def test_whitespace_balance():
    """Evaluates canvas breathing room."""
    manifest = [{"x": 100, "y": 100, "width": 500, "height": 200}]
    hero_rect = [100, 400, 600, 400]
    res = whitespace_balance(manifest, hero_rect, canvas_w=1000, canvas_h=1000)
    # Area = 1,000,000; text = 100,000; hero = 240,000; occupied = 340,000; whitespace = 0.66
    assert 0.60 <= res["whitespace_ratio"] <= 0.70
    assert res["balanced"] is True


def test_focal_count():
    """Identifies primary headline and hero focal points."""
    manifest = [
        {"role": "headline", "size": 90.0, "x": 60, "y": 100, "width": 800, "height": 100},
        {"role": "date", "size": 20.0, "x": 60, "y": 250, "width": 300, "height": 30},
    ]
    hero_rect = [60, 400, 800, 500]
    res = focal_count(manifest, hero_rect, canvas_w=1080, canvas_h=1350)
    assert res["focal_count"] == 2
    assert res["balanced"] is True


def test_evaluate_design_quality_composite():
    """Composite quality evaluator produces scores in range [0, 10]."""
    manifest = [
        {"role": "headline", "size": 96.0, "x": 80, "y": 150, "width": 700, "height": 120},
        {"role": "date", "size": 22.0, "x": 80, "y": 320, "width": 400, "height": 30},
        {"role": "venue", "size": 18.0, "x": 80, "y": 380, "width": 350, "height": 25},
    ]
    hero_rect = [80, 450, 750, 450]
    im = Image.new("RGB", (1080, 1350), "#070B19")
    palette = ["#070B19", "#00F5D4", "#7B2FFF"]

    report = evaluate_design_quality(
        manifest_rows=manifest,
        image_input=im,
        palette_hexes=palette,
        canvas_w=1080,
        canvas_h=1350,
        hero_rect=hero_rect,
    )
    assert "design_score" in report
    assert 0.0 <= report["design_score"] <= 10.0
    assert "type_scale" in report
    assert "palette_coverage" in report
    assert "asymmetry" in report
