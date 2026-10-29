"""Unit and fixture tests for deterministic quality checks."""
import sys
from pathlib import Path
import pytest

from poster_agent.context.loader import load_context
from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
from poster_agent.renderer.renderer import DOMBoundingBox
from poster_agent.checks.runner import CheckRunner
from poster_agent.checks.ocr import run_ocr_check, extract_text_from_image
from poster_agent.checks.geometry import run_geometry_check
from poster_agent.checks.contrast import run_contrast_check, calculate_contrast_ratio, hex_to_rgb
from poster_agent.checks.logo import run_logo_check


@pytest.fixture
def base_spec():
    return PosterSpec(
        canvas_width_px=1200,
        canvas_height_px=1600,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=200, x_min=50, y_max=900, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="APEX TECH SUMMIT 2026",
                source="brief",
                font="Outfit",
                size=36,
                weight=800,
                color="#FFFFFF",
                box=BBox(y_min=180, x_min=80, y_max=280, x_max=920),
            ),
            TextElement(
                id="subhead_1",
                role="subheadline",
                text="ANNUAL AI AND ROBOTICS SHOWCASE",
                source="brief",
                font="Inter",
                size=20,
                weight=600,
                color="#00F5D4",
                box=BBox(y_min=300, x_min=80, y_max=360, x_max=920),
            ),
            TextElement(
                id="date_1",
                role="date",
                text="OCTOBER 30 2026",
                source="brief",
                font="Inter",
                size=18,
                weight=600,
                color="#FEE440",
                box=BBox(y_min=750, x_min=80, y_max=800, x_max=600),
            ),
            TextElement(
                id="venue_1",
                role="venue",
                text="MAIN AUDITORIUM TECH CAMPUS",
                source="brief",
                font="Inter",
                size=16,
                weight=500,
                color="#FFFFFF",
                box=BBox(y_min=820, x_min=80, y_max=870, x_max=800),
            ),
        ],
        logos=[
            LogoPlacement(
                file="college_logo.png",
                box=BBox(y_min=40, x_min=80, y_max=120, x_max=350),
                clear_space_px=20,
            )
        ],
        art_slots=[],
        assumptions=["Standard promotional poster"],
        missing_fields=[],
        qr_code="https://apextech.edu/summit",
    )


@pytest.fixture
def context():
    return load_context()


# -------------------------------------------------------------
# Acceptance Criteria: Fixture Tests
# -------------------------------------------------------------

def test_clean_poster_passes_all_checks(base_spec, context):
    """Fixture 1: clean_poster.png MUST pass all checks."""
    img_path = Path("tests/fixtures/clean_poster.png")
    assert img_path.exists(), "clean_poster.png fixture must exist"

    runner = CheckRunner()
    report = runner.run_all(spec=base_spec, context=context, image_path=img_path)

    blocking = [r for r in report.results if r.severity == "blocking"]
    assert len(blocking) == 0, f"Expected 0 blocking errors, got: {[b.detail for b in blocking]}"
    assert report.passed is True


def test_duplicated_headline_fails_ocr(base_spec, context):
    """Fixture 2: duplicated_headline.png MUST fail OCR duplication check."""
    img_path = Path("tests/fixtures/duplicated_headline.png")
    assert img_path.exists()

    runner = CheckRunner()
    report = runner.run_all(spec=base_spec, context=context, image_path=img_path)

    assert report.passed is False
    assert report.blocking_count >= 1

    dup_failures = [
        r for r in report.results
        if r.severity == "blocking" and "duplicated" in r.detail.lower()
    ]
    assert len(dup_failures) >= 1, f"Expected duplication blocking error, got: {[r.detail for r in report.results]}"


def test_wrong_order_fails_ocr(base_spec, context):
    """Fixture 3: wrong_order.png MUST fail OCR ordering check."""
    img_path = Path("tests/fixtures/wrong_order.png")
    assert img_path.exists()

    runner = CheckRunner()
    report = runner.run_all(spec=base_spec, context=context, image_path=img_path)

    assert report.passed is False
    assert report.blocking_count >= 1

    order_failures = [
        r for r in report.results
        if r.severity == "blocking" and any(k in r.detail.lower() for k in ("order", "interrupted", "violation"))
    ]
    assert len(order_failures) >= 1, f"Expected order violation, got: {[r.detail for r in report.results]}"


# -------------------------------------------------------------
# Unit Tests for Geometry Checks
# -------------------------------------------------------------

def test_geometry_overflow_detected(base_spec):
    boxes = {
        "headline_1": DOMBoundingBox(
            element_id="headline_1",
            role="headline",
            left=100.0,
            top=-20.0,  # Negative top: overflows canvas!
            right=800.0,
            bottom=150.0,
            width=700.0,
            height=170.0,
        )
    }
    results = run_geometry_check(spec=base_spec, dom_boxes=boxes)
    blocking = [r for r in results if r.severity == "blocking"]
    assert len(blocking) == 1
    assert "overflow" in blocking[0].check_name


def test_geometry_collision_detected(base_spec):
    boxes = {
        "elem_1": DOMBoundingBox(
            element_id="elem_1",
            role="headline",
            left=100.0,
            top=100.0,
            right=500.0,
            bottom=250.0,
            width=400.0,
            height=150.0,
        ),
        "elem_2": DOMBoundingBox(
            element_id="elem_2",
            role="subheadline",
            left=120.0,
            top=180.0,  # 70px overlap with elem_1 (> 5px threshold)!
            right=500.0,
            bottom=300.0,
            width=380.0,
            height=120.0,
        ),
    }
    results = run_geometry_check(spec=base_spec, dom_boxes=boxes, max_allowed_overlap_px=5.0)
    blocking = [r for r in results if r.severity == "blocking"]
    assert len(blocking) >= 1
    assert "overlap" in blocking[0].check_name


def test_geometry_margin_warning(base_spec):
    boxes = {
        "elem_1": DOMBoundingBox(
            element_id="elem_1",
            role="headline",
            left=10.0,  # < 40px margin!
            top=60.0,
            right=600.0,
            bottom=150.0,
            width=590.0,
            height=90.0,
        )
    }
    results = run_geometry_check(spec=base_spec, dom_boxes=boxes, min_margin_px=40.0)
    warnings = [r for r in results if r.severity == "warning"]
    assert len(warnings) == 1
    assert "margin" in warnings[0].check_name


# -------------------------------------------------------------
# Unit Tests for Contrast & Font Size Checks
# -------------------------------------------------------------

def test_contrast_calculation():
    # Black on white: 21:1
    ratio = calculate_contrast_ratio((0, 0, 0), (255, 255, 255))
    assert ratio >= 20.9

    # Identical colors: 1:1
    ratio = calculate_contrast_ratio((100, 100, 100), (100, 100, 100))
    assert ratio == 1.0


def test_contrast_blocking_on_low_contrast(base_spec):
    # Alter headline color to dark navy on dark navy
    base_spec.elements[0].color = "#0B1530"
    results = run_contrast_check(spec=base_spec)
    blocking = [r for r in results if r.severity == "blocking" and "contrast" in r.check_name]
    assert len(blocking) >= 1


def test_font_size_blocking_on_tiny_text(base_spec):
    # Alter venue font size to 8pt (< 14pt)
    base_spec.elements[3].size = 8
    results = run_contrast_check(spec=base_spec, min_font_pt=14)
    blocking = [r for r in results if r.severity == "blocking" and "font_size" in r.check_name]
    assert len(blocking) >= 1


# -------------------------------------------------------------
# Unit Tests for Logo Checks
# -------------------------------------------------------------

def test_logo_check_passes_when_present(base_spec, context):
    results = run_logo_check(spec=base_spec, context=context)
    blocking = [r for r in results if r.severity == "blocking"]
    assert len(blocking) == 0


def test_logo_check_fails_when_required_logo_missing(base_spec, context):
    base_spec.logos = []  # Remove all logos
    results = run_logo_check(spec=base_spec, context=context)
    blocking = [r for r in results if r.severity == "blocking"]
    assert len(blocking) >= 1
    assert "required_logo" in blocking[0].check_name


def test_logo_check_fails_when_undersized(base_spec, context):
    # Logo width 50px (minimum is 120px)
    base_spec.logos[0].box = BBox(y_min=40, x_min=80, y_max=60, x_max=120)
    results = run_logo_check(spec=base_spec, context=context)
    blocking = [r for r in results if r.severity == "blocking"]
    assert len(blocking) >= 1
    assert "logo_size" in blocking[0].check_name

