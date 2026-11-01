"""Smoke test for ThemePackRenderer: verifies that palette changes alter rendered DOM colors."""
from pathlib import Path
from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.vision.art_measurer import MeasuredArtBundle
from poster_agent.palette_policy import PalettePolicy
from poster_agent.renderer.theme_renderer import ThemePackRenderer


def test_theme_renderer_palette_smoke_test(tmp_path):
    """Smoke test proving that changing the palette config changes the rendered colors."""
    raw_brief = """POSTER BRIEF: COLOR TEST 2027
Title: COLOR TEST 2027
Date: 10 MARCH 2027
Venue: AUDITORIUM HALL
Prize: ₹10,000
"""
    extractor = BriefExtractor()
    brief = extractor.extract(raw_brief)

    art_bundle = MeasuredArtBundle(
        canvas_w=600,
        canvas_h=800,
        optical_center_x=300,
        optical_center_y=400,
    )

    policy = PalettePolicy("configs/palette_policy.yaml")

    # Render 1: Cyber CTF Palette (Neon Green accent #00FF9C)
    palette_cyber = policy.resolve_palette(genre_hint="cyber_ctf")
    css_cyber = policy.generate_css_variables(palette_cyber)

    renderer = ThemePackRenderer(theme_name="cyber_ctf")
    res1 = renderer.render(
        brief=brief,
        art_bundle=art_bundle,
        output_dir=tmp_path / "run_cyber",
        base_slug="test_cyber",
        bg_path="",
        palette_vars_css=css_cyber,
        title_treatment="css_gradient_glow",
    )

    # Render 2: Green Loop Palette (Warm Earthy #E9A23B / #1F2A24)
    palette_green = policy.resolve_palette(
        brief_palette=["#F4EBD0", "#2F5D50", "#E9A23B", "#C8553D", "#1F2A24"]
    )
    css_green = policy.generate_css_variables(palette_green)

    res2 = renderer.render(
        brief=brief,
        art_bundle=art_bundle,
        output_dir=tmp_path / "run_green",
        base_slug="test_green",
        bg_path="",
        palette_vars_css=css_green,
        title_treatment="flat",
    )

    assert res1.full_png_path.exists()
    assert res2.full_png_path.exists()

    # Compare HTML files to prove CSS variables differ
    html1 = res1.html_path.read_text(encoding="utf-8")
    html2 = res2.html_path.read_text(encoding="utf-8")

    assert "--color-canvas-base: #0A0E1A" in html1
    assert "--color-canvas-base: #F4EBD0" in html2
    assert html1 != html2
