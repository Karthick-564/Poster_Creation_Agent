"""Unit tests for HTML/CSS and Playwright PosterRenderer."""
import os
from pathlib import Path
import pytest

from poster_agent.spec.models import PosterSpec, BBox, TextElement, LogoPlacement
from poster_agent.renderer.renderer import PosterRenderer


@pytest.fixture
def test_spec():
    return PosterSpec(
        canvas_width_px=800,
        canvas_height_px=1200,
        dpi=300,
        template_id="event_portrait_hero",
        palette=["#0B132B", "#00F5D4", "#F72585", "#FFFFFF"],
        text_safe_zones=[BBox(y_min=200, x_min=50, y_max=900, x_max=950)],
        elements=[
            TextElement(
                id="headline_1",
                role="headline",
                text="TEST EVENT",
                source="brief",
                font="Outfit",
                size=32,
                weight=700,
                color="#FFFFFF",
                box=BBox(y_min=100, x_min=100, y_max=200, x_max=700),
            )
        ],
        logos=[
            LogoPlacement(
                file="college_logo.png",
                box=BBox(y_min=20, x_min=50, y_max=80, x_max=250),
            )
        ],
        art_slots=[],
        assumptions=[],
        missing_fields=[],
        qr_code="https://example.com",
    )


def test_html_composition_strategy_b(test_spec):
    renderer = PosterRenderer()
    html = renderer.compose_html(test_spec, strategy="B")
    assert "TEST EVENT" in html
    assert "data-role=\"headline\"" in html
    assert "logo_0" in html
    assert "qr_code" in html


def test_html_composition_strategy_a(test_spec):
    renderer = PosterRenderer()
    # Strategy A omits text from HTML
    html = renderer.compose_html(test_spec, strategy="A")
    assert "TEST EVENT" not in html
    assert "logo_0" in html


def test_full_render(tmp_path, test_spec):
    renderer = PosterRenderer()
    result = renderer.render(
        spec=test_spec,
        output_dir=tmp_path,
        strategy="B",
        base_name="test_out",
    )

    assert result.png_path.exists()
    assert result.png_path.stat().st_size > 0
    assert result.html_path.exists()
    assert "headline_1" in result.dom_boxes
    assert "logo_0" in result.dom_boxes

