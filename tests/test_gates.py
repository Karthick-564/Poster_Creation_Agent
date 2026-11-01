"""Unit tests for standalone QA gates module (Phase D foundations).

Tests pure deterministic gates:
- Canvas margin bounds escape detection
- Pairwise row overlap detection with intersection rect reporting
- Empty content and zero-geometry row validation
- Horizontal margin seam defect detection & exemption bands
- WCAG 2.1 relative luminance contrast sampling
- Pathological defect reproduction (z_pattern collisions, grid_3col right escape)
- Complete verification of Task 1's archetype_check_v3 renders producing ZERO failures
"""
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from poster_agent.qa.gates import (
    GateFailure,
    check_canvas_bounds,
    check_empty_rows,
    check_row_overlap,
    check_seams,
    run_all_gates,
    run_all_manifest_gates,
    run_all_pixel_gates,
    sample_contrast,
)


@pytest.fixture
def clean_manifest() -> list[dict]:
    return [
        {
            "id": 1,
            "role": "organizer",
            "text": "PRESENTED BY ECO CLUB",
            "bounds": {"x": 50.0, "y": 50.0, "width": 300.0, "height": 20.0},
            "size": 14.0,
        },
        {
            "id": 2,
            "role": "title",
            "text": "GREEN LOOP 2027",
            "bounds": {"x": 50.0, "y": 120.0, "width": 800.0, "height": 80.0},
            "size": 72.0,
        },
        {
            "id": 3,
            "role": "venue",
            "text": "KOCHI CONVENTION CENTRE",
            "bounds": {"x": 50.0, "y": 900.0, "width": 400.0, "height": 30.0},
            "size": 18.0,
        },
    ]


def test_check_canvas_bounds_clean(clean_manifest):
    failures = check_canvas_bounds(clean_manifest, canvas_w=1080.0, canvas_h=1350.0, margin_px=40.0)
    assert len(failures) == 0


def test_check_canvas_bounds_catches_all_four_escapes():
    escaped_rows = [
        {"id": "left_esc", "text": "Escaping Left", "bounds": {"x": 20.0, "y": 100.0, "width": 200.0, "height": 30.0}},
        {"id": "top_esc", "text": "Escaping Top", "bounds": {"x": 100.0, "y": 25.0, "width": 200.0, "height": 30.0}},
        {"id": "right_esc", "text": "Escaping Right", "bounds": {"x": 900.0, "y": 300.0, "width": 200.0, "height": 30.0}},
        {"id": "bottom_esc", "text": "Escaping Bottom", "bounds": {"x": 100.0, "y": 1320.0, "width": 200.0, "height": 30.0}},
    ]
    failures = check_canvas_bounds(escaped_rows, canvas_w=1080.0, canvas_h=1350.0, margin_px=40.0)
    assert len(failures) == 4
    kinds = [f.kind for f in failures]
    assert all(k == "canvas_bounds" for k in kinds)
    targets = [f.target for f in failures]
    assert targets == ["left_esc", "top_esc", "right_esc", "bottom_esc"]


def test_check_row_overlap_clean(clean_manifest):
    failures = check_row_overlap(clean_manifest)
    assert len(failures) == 0


def test_check_row_overlap_catches_collision_and_measures_rect():
    colliding_rows = [
        {"id": "box_a", "text": "Box A", "bounds": {"x": 100.0, "y": 100.0, "width": 200.0, "height": 50.0}},
        {"id": "box_b", "text": "Box B", "bounds": {"x": 250.0, "y": 120.0, "width": 150.0, "height": 60.0}},
    ]
    failures = check_row_overlap(colliding_rows)
    assert len(failures) == 1
    f = failures[0]
    assert f.kind == "row_overlap"
    assert "box_a" in f.target and "box_b" in f.target
    # Intersection is x in [250, 300] (w=50), y in [120, 150] (h=30)
    rect = f.measured["intersection_rect"]
    assert rect == [250.0, 120.0, 50.0, 30.0]
    assert f.measured["overlap_area"] == 1500.0


def test_check_empty_rows():
    rows = [
        {"id": "valid", "text": "Valid Text", "bounds": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 20.0}},
        {"id": "empty_str", "text": "   ", "bounds": {"x": 50.0, "y": 80.0, "width": 100.0, "height": 20.0}},
        {"id": "zero_w", "text": "Zero Width", "bounds": {"x": 50.0, "y": 110.0, "width": 0.0, "height": 20.0}},
        {"id": "zero_h", "text": "Zero Height", "bounds": {"x": 50.0, "y": 140.0, "width": 100.0, "height": 0.0}},
    ]
    failures = check_empty_rows(rows)
    assert len(failures) == 3
    targets = {f.target for f in failures}
    assert targets == {"empty_str", "zero_w", "zero_h"}


def test_check_seams_clean_and_detection():
    # Clean smooth image
    clean_img = Image.new("RGB", (200, 300), (10, 15, 25))
    clean_failures = check_seams(clean_img, delta_threshold=6.0)
    assert len(clean_failures) == 0

    # Image with a seam artifact (sharp jump >= 6.0 across row y=150)
    seam_arr = np.zeros((300, 200, 3), dtype=np.uint8)
    seam_arr[:150, :] = 20
    seam_arr[150:, :] = 50  # Jump of 30 units
    seam_failures = check_seams(seam_arr, delta_threshold=6.0)
    assert len(seam_failures) >= 1
    assert seam_failures[0].kind == "seam"
    assert seam_failures[0].target == "frame"
    assert seam_failures[0].measured["y"] in (149, 150)


def test_check_seams_respects_exempt_bands():
    seam_arr = np.zeros((300, 200, 3), dtype=np.uint8)
    seam_arr[:150, :] = 20
    seam_arr[150:, :] = 50
    # Exempt the y in [140, 160] band
    failures = check_seams(seam_arr, known_bands=[(140, 160)], delta_threshold=6.0)
    assert len(failures) == 0


def test_sample_contrast_wcag():
    # Create dark image (background)
    img = Image.new("RGB", (400, 400), (10, 10, 20))
    arr = np.array(img)
    # Row 1 patch has bright text glyphs on dark background (glyphs occupy inner subset)
    arr[55:85, 60:190] = (255, 255, 255)
    # Row 2 patch has dark gray text (low contrast against dark background)
    arr[155:185, 60:190] = (20, 20, 30)

    rows = [
        {"id": "good_contrast", "text": "High Contrast", "bounds": {"x": 50, "y": 50, "width": 150, "height": 40}, "size": 18.0},
        {"id": "bad_contrast", "text": "Low Contrast", "bounds": {"x": 50, "y": 150, "width": 150, "height": 40}, "size": 14.0},
    ]

    failures = sample_contrast(arr, rows, scale=1.0)
    assert len(failures) == 1
    assert failures[0].target == "bad_contrast"
    assert failures[0].kind == "contrast"
    assert failures[0].measured["contrast_ratio"] < 4.5


def test_pathological_synthetic_manifest_reproduces_historical_bugs():
    """Reproduces historical bugs: z_pattern presenter×date, venue×awards, and grid_3col right escape."""
    buggy_manifest = [
        # Bug 2a: z_pattern presenter mark colliding with date badge
        {
            "id": "row_org",
            "role": "organizer_mark",
            "text": "PRESENTED BY THE DEPARTMENT OF SUSTAINABLE ENGINEERING",
            "bounds": {"x": 45.0, "y": 50.0, "width": 600.0, "height": 30.0},
            "size": 16.0,
        },
        {
            "id": "row_date",
            "role": "date_badge",
            "text": "MARCH 28-30 2027",
            "bounds": {"x": 550.0, "y": 50.0, "width": 450.0, "height": 30.0},
            "size": 18.0,
        },
        # Bug 2b: venue colliding with grand prize
        {
            "id": "row_venue",
            "role": "venue",
            "text": "INTERNATIONAL CONVENTION CENTRE",
            "bounds": {"x": 45.0, "y": 900.0, "width": 400.0, "height": 40.0},
            "size": 18.0,
        },
        {
            "id": "row_prize",
            "role": "grand_prize",
            "text": "PRIZE POOL RS 10 LAKHS",
            "bounds": {"x": 45.0, "y": 920.0, "width": 400.0, "height": 40.0},
            "size": 24.0,
        },
        # Bug 1: grid_3col right column overflow past right margin
        {
            "id": "row_col3_escaped",
            "role": "col3_cta",
            "text": "REGISTER AT BIOECONOMY2027.EXAMPLE.ORG/APPLY",
            "bounds": {"x": 750.0, "y": 600.0, "width": 350.0, "height": 30.0},
            "size": 14.0,
        },
    ]

    report = run_all_manifest_gates(buggy_manifest, canvas_w=1080.0, canvas_h=1350.0, margin_px=45.0)
    assert not report["passed"]
    assert report["summary"]["row_overlap_failures"] == 2  # org×date and venue×prize
    assert report["summary"]["canvas_bounds_failures"] == 1  # col3_escaped: 750 + 350 = 1100 > 1035

    overlap_targets = [f["target"] for f in report["failures"] if f["kind"] == "row_overlap"]
    assert any("row_org" in t and "row_date" in t for t in overlap_targets)
    assert any("row_venue" in t and "row_prize" in t for t in overlap_targets)

    bounds_targets = [f["target"] for f in report["failures"] if f["kind"] == "canvas_bounds"]
    assert bounds_targets == ["row_col3_escaped"]


def test_archetype_check_v3_renders_produce_zero_failures():
    """Verify that all Task 1 renders in runs/archetype_check_v3/ pass 100% of manifest and pixel gates."""
    base_dir = Path("runs/archetype_check_v3")
    if not base_dir.exists():
        pytest.skip("runs/archetype_check_v3 directory does not exist")

    archetypes = ["focal_point", "z_pattern", "split", "grid_3col"]

    for arch in archetypes:
        arch_dir = base_dir / arch
        manifest_p = arch_dir / "text_manifest.json"
        img_p = arch_dir / "master_render_2x.png"

        assert manifest_p.exists(), f"Missing text_manifest.json for {arch}"
        assert img_p.exists(), f"Missing master_render_2x.png for {arch}"

        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))

        report = run_all_gates(
            rows=manifest,
            image=img_p,
            canvas_w=1080.0,
            canvas_h=1350.0,
            margin_px=40.0,
            scale=2.0,
        )

        assert report["passed"] is True, f"Gates failed for {arch}: {report['failures']}"
        assert report["failure_count"] == 0, f"Expected 0 failures in {arch}, got {report['failure_count']}"
