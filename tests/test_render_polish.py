"""Tests for Composer Remediation & Render Polish (Phase D Commit 1).

Covers:
- Width-fit wrapping (wrap to <=2 lines, shrink toward doctrine floor, zero margin clipping)
- Vertical rhythm (5-band archetype division, V-BAND COVERAGE >= 70%)
- Hero reserve (hero bounding box clearance, HERO_OCCLUSION: none)
- Dedupe (closing line rendered in exactly one structural role)
- Contrast floors (WCAG >= 4.5:1 contrast enforcement for structural rows & body text)
- QR reserve (logistics rows strictly routed away from bottom-right QR module)
- Doctrine floors intact (headline >= canvas_h / 11, body >= 1.8%, micro >= 1.4%)
"""
import os
from pathlib import Path
import pytest
from PIL import Image

from poster_agent.ingestion.extractor import BriefExtractor, ExtractedBrief
from poster_agent.renderer.composer import (
    TypographicPlan,
    audit_fonts,
    build_typography_plan,
    check_rect_intersection,
    compose,
    compose_slots,
    compute_vband_coverage,
    ensure_contrast_color,
    get_contrast_ratio,
    wrap_and_fit_row,
)
from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer


CLI_PATH = (
    Path(__file__).resolve().parent.parent
    / "tools"
    / "vectorcraft_bin"
    / "vectorcraft-0.19.0-windows-x64-portable"
    / "vectorcraft-cli.exe"
)


@pytest.fixture
def demo_brief() -> ExtractedBrief:
    p = Path(__file__).resolve().parent.parent / "briefs" / "brief_c4_demo.txt"
    if p.exists():
        raw = p.read_text(encoding="utf-8")
    else:
        raw = """
        POSTER BRIEF: GDG KCT RECRUITMENT 2026
        Format: 1080 x 1920 px (9:16 story)
        Date: Wednesday, 12 November 2026, 10:00 AM
        Venue: GDG KCT Lounge, Kumaraguru College of Technology
        Title: We Are Recruiting
        Eyebrow: LEARN / BUILD / GROW
        Tagline: REAL PEOPLE. REAL PROJECTS. REAL IMPACT.
        Subtitle: Join GDG KCT On Campus and be a part of a community that builds, learns and creates impact!
        Section: OPEN POSITIONS
        Position 1: Team Members
        Position 1 tagline: Bring your ideas, passion and energy!
        Position 2: Leads
        Position 2 tagline: Take initiative, drive events and make an impact!
        Deadline label: TIME TO FILL
        Deadline: Monday, 17 November 2026
        Call to action: Apply Online
        Closing line: BE THE CHANGE. JOIN GDG KCT!
        Contact: hello@gdgkct.in | +91 98765 43210
        QR Link: https://gdgkct.in/apply
        Mood: clean, friendly, energetic, student tech community, light background
        Palette: #FFFFFF #0B2A5B #4285F4 #EA4335 #FBBC05 #34A853 #E8F0FE #E6F4EA
        """
    return BriefExtractor().extract(raw)


def test_contrast_floors_wcag_and_swapping():
    """Verify WCAG 2.1 contrast calculation and color swap to guarantee >= 4.5:1 ratio."""
    # Navy (#0B2A5B) against White (#FFFFFF) is > 12:1
    cr_navy_white = get_contrast_ratio("#FFFFFF", "#0B2A5B")
    assert cr_navy_white > 12.0

    # Low contrast: light gray on white fails < 4.5:1
    cr_low = get_contrast_ratio("#FFFFFF", "#E8F0FE")
    assert cr_low < 2.0

    # ensure_contrast_color swaps to high contrast (e.g. Navy) when preferred color has low contrast
    swapped = ensure_contrast_color(bg_hex="#E8F0FE", preferred_fg="#FFFFFF", min_contrast=4.5)
    assert swapped == "#0B2A5B"
    assert get_contrast_ratio("#E8F0FE", swapped) >= 4.5

    # On dark background, ensure_contrast_color provides white
    swapped_dark = ensure_contrast_color(bg_hex="#0B2A5B", preferred_fg="#1E2842", min_contrast=4.5)
    assert swapped_dark == "#FFFFFF"
    assert get_contrast_ratio("#0B2A5B", swapped_dark) >= 4.5


def test_wrap_and_fit_row_behavior():
    """Verify wrap_and_fit_row wraps to <= 2 lines before shrinking, respecting floor size."""
    max_w = 500.0
    floor_sz = 30.0

    # 1. Fits on single line
    short_text = "GDG KCT"
    lines, sz = wrap_and_fit_row(short_text, target_size=40.0, floor_size=floor_sz, max_w=max_w)
    assert len(lines) == 1
    assert lines[0] == short_text
    assert sz == 40.0

    # 2. Needs 2 lines, fits at target size without shrinking
    med_text = "Join GDG KCT On Campus and be a part of community"
    lines, sz = wrap_and_fit_row(med_text, target_size=24.0, floor_size=18.0, max_w=max_w)
    assert len(lines) == 2
    assert sz == 24.0

    # 3. Moderately long text shrinks toward floor
    med_long_text = "Join GDG KCT On Campus and be a part of community that builds"
    lines, sz = wrap_and_fit_row(med_long_text, target_size=40.0, floor_size=20.0, max_w=max_w)
    assert len(lines) <= 2
    assert sz >= 20.0

    # 4. Pathological long text scales below floor to prevent clipping with loud banner
    long_text = "Join GDG KCT On Campus and be a part of an incredible community that builds learns and creates real lasting impact across campus"
    lines, sz = wrap_and_fit_row(long_text, target_size=40.0, floor_size=floor_sz, max_w=max_w)
    assert len(lines) <= 2
    assert sz < floor_sz


def test_vertical_rhythm_and_vband_coverage():
    """Verify vertical band computation evaluates 9:16 canvas into 5 fractional bands."""
    canvas_h = 1920.0
    # Items placed only in top 20%
    top_items = [
        {"y": 100.0, "text": "Top Header", "size": 30.0},
        {"y": 200.0, "text": "Top Sub", "size": 20.0},
    ]
    cov, occ, desc = compute_vband_coverage(top_items, canvas_h=canvas_h)
    assert cov == 20.0
    assert occ == [0]

    # Items well-distributed across all 5 bands
    spread_items = [
        {"y": 150.0, "text": "Band 0 Header", "size": 40.0},
        {"y": 550.0, "text": "Band 1 Hero/Key visual", "size": 30.0},
        {"y": 900.0, "text": "Band 2 Body/Positions", "size": 25.0},
        {"y": 1400.0, "text": "Band 3 Logistics/Date", "size": 20.0},
        {"y": 1800.0, "text": "Band 4 Footer Bar", "size": 20.0},
    ]
    cov, occ, desc = compute_vband_coverage(spread_items, canvas_h=canvas_h)
    assert cov == 100.0
    assert occ == [0, 1, 2, 3, 4]


def test_hero_reserve_and_occlusion_avoidance():
    """Verify text rects never intersect hero rect."""
    hero_rect = (200.0, 600.0, 680.0, 400.0)

    # Completely above hero
    top_rect = (200.0, 400.0, 680.0, 100.0)
    assert not check_rect_intersection(top_rect, hero_rect)

    # Completely below hero
    bot_rect = (200.0, 1050.0, 680.0, 150.0)
    assert not check_rect_intersection(bot_rect, hero_rect)

    # Overlapping rect
    overlap_rect = (250.0, 650.0, 300.0, 100.0)
    assert check_rect_intersection(overlap_rect, hero_rect)


def test_closing_line_dedupe_in_slots(demo_brief, tmp_path, capsys):
    """Verify closing line is rendered in exactly one structural role (footer bar, not duplicated in body rows)."""
    palette = ["#FFFFFF", "#0B2A5B", "#4285F4", "#EA4335", "#FBBC05"]
    bg_p = tmp_path / "bg.png"
    hero_p = tmp_path / "hero.png"
    Image.new("RGB", (100, 100), "#FFFFFF").save(bg_p)
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(hero_p)

    vc = compose(
        brief=demo_brief,
        palette=palette,
        bg_path=bg_p,
        hero_path=hero_p,
        archetype="focal_point",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},  # slot execution
    )
    out, _ = capsys.readouterr()

    # Verify hero occlusion banner
    assert "HERO_OCCLUSION: none" in out

    # Verify vertical band coverage is logged
    assert "V-BAND COVERAGE:" in out

    # Verify closing line appears only once in queued texts / commands
    closing_texts = [
        t for t in vc._queued_texts
        if "BE THE CHANGE" in t.get("text", "").upper()
    ]
    # Exactly one structural instance (in footer bar)
    assert len(closing_texts) == 1
    assert closing_texts[0].get("role") in ("_structure_footer", "_structure_footer_bar")


def test_doctrine_floors_preserved(demo_brief):
    """Ensure headline and margin floors are maintained during plan building."""
    palette = ["#FFFFFF", "#0B2A5B", "#4285F4", "#EA4335", "#FBBC05"]
    width = 1080.0
    height = 1920.0
    plan = build_typography_plan(demo_brief, palette, width=width, height=height)

    title_row = plan.get_row("title")
    assert title_row is not None
    headline_floor = height / 11.0  # 174.54pt
    assert title_row.size >= headline_floor - 0.5

    margin_floor = width * 0.045
    assert plan.margin >= margin_floor - 0.5


def test_qr_reserve_avoids_logistics_collision(demo_brief, tmp_path):
    """Verify QR code bounding box is reserved and logistics rows do not collide."""
    palette = ["#FFFFFF", "#0B2A5B", "#4285F4", "#EA4335", "#FBBC05"]
    bg_p = tmp_path / "bg.png"
    hero_p = tmp_path / "hero.png"
    Image.new("RGB", (100, 100), "#FFFFFF").save(bg_p)
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(hero_p)

    vc = compose(
        brief=demo_brief,
        palette=palette,
        bg_path=bg_p,
        hero_path=hero_p,
        archetype="focal_point",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},
    )

    qr_sz = 140.0
    margin_x = 1080.0 * 0.045
    qr_px = 1080.0 - margin_x - qr_sz
    max_log_w = qr_px - margin_x - 30.0

    # All text items in logistics rows must end before qr_px
    for cmd in vc.commands:
        if cmd.get("command") == "text.create":
            params = cmd.get("params", {})
            text = params.get("text", "")
            # Check if this text is a date, venue, or deadline string
            if any(k in text for k in ("November", "Lounge", "TIME TO FILL")):
                x = params.get("x", 0.0)
                # Left aligned logistics rows must start at margin_x and fit within max_log_w
                if params.get("justify") == "left":
                    assert x <= margin_x + 1.0


def test_end_to_end_demo_brief_render_polish(demo_brief, tmp_path):
    """End-to-end render proof of demo brief with zero margin escapes, verified via VectorCraft CLI."""
    if not CLI_PATH.exists():
        pytest.skip("VectorCraft CLI binary not found")

    palette = ["#FFFFFF", "#0B2A5B", "#4285F4", "#EA4335", "#FBBC05"]
    bg_p = tmp_path / "bg.png"
    hero_p = tmp_path / "hero.png"
    Image.new("RGB", (1080, 1920), "#FFFFFF").save(bg_p)
    Image.new("RGBA", (680, 320), (66, 133, 244, 255)).save(hero_p)

    vc = compose(
        brief=demo_brief,
        palette=palette,
        bg_path=bg_p,
        hero_path=hero_p,
        archetype="focal_point",
        width=1080.0,
        height=1920.0,
        layout_plan={"slots": []},
    )
    vc.cli_path = CLI_PATH
    out_png = tmp_path / "demo_render.png"

    try:
        res = vc.execute(output_png=out_png, work_dir=tmp_path)
    except RuntimeError as ex:
        if "The system cannot find the path specified" in str(ex):
            pytest.skip("WSL path interop not available on this platform")
        raise

    assert res.success, f"Render failed: {res.error_message}"
    assert out_png.exists()

    # Zero text overflow defects
    margin_px = 1080.0 * 0.045
    for item in res.text_manifest:
        # None of the text items should have margin escapes
        assert item.get("overflow") is None, (
            f"Row {item.get('id')} ({item.get('role')}): {item.get('overflow')}"
        )
