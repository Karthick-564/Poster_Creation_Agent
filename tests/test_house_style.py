"""Unit tests for House Style System (Commit 2).

Tests:
- configs/house_style.yaml loading & brand palettes/fonts per school
- Canvas dimension resolution from brief: default 1080x1920 (9:16 story), A3/A4, square, 4:5
- School voice autodetection (Barlow for KCTBS, Montserrat for KCT/KCLAS, Noto Sans Tamil for Tamil)
- Genre taxonomy & structural policy (institutional vs cultural)
- Structural rows: logo_row, banner_tab_row, pill_row, footer_bar_row, qr_row (with _structure_* roles in manifest)
- Stage 6 exact size gate deriving dynamically from canvas dimensions
"""
from pathlib import Path
import pytest
from PIL import Image

from poster_agent.house_style import (
    load_house_style,
    resolve_canvas_dimensions,
    resolve_school,
    resolve_genre,
)
from poster_agent.ingestion.extractor import BriefExtractor, ExtractedBrief
from poster_agent.renderer.composer import (
    audit_fonts,
    emit_logo_row,
    emit_banner_tab_row,
    emit_pill_row,
    emit_footer_bar_row,
    emit_qr_row,
    compose,
)
from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer
from poster_agent.unified_pipeline import UnifiedPosterPipeline


def test_house_style_config_and_school_palette_lookup():
    cfg = load_house_style()
    assert "schools" in cfg
    assert "formats" in cfg
    assert "genres" in cfg
    assert "structural_policies" in cfg

    # Verify KCT brand facts
    kct = cfg["schools"]["KCT"]
    assert kct["palette"]["primary"] == "#1E2842"
    assert kct["palette"]["secondary"] == "#85CEBD"
    assert kct["fonts"]["display"] == "Montserrat"

    # Verify KCTBS brand facts
    kctbs = cfg["schools"]["KCTBS"]
    assert kctbs["palette"]["primary"] == "#1F3E8A"
    assert kctbs["palette"]["secondary"] == "#F2B61E"
    assert kctbs["fonts"]["display"] == "Barlow"

    # Verify KCLAS brand facts
    kclas = cfg["schools"]["KCLAS"]
    assert kclas["palette"]["primary"] == "#0A5BB5"
    assert kclas["palette"]["secondary"] == "#7A1A45"


def test_school_resolution_from_brief_text():
    # KCTBS brief
    raw_kctbs = """
    Title: Management Conclave 2026
    Organizer: Kumaraguru Center for Technology and Business Studies (KCTBS)
    """
    brief_kctbs = BriefExtractor().extract(raw_kctbs)
    sch_key, sch_info = resolve_school(brief_kctbs)
    assert sch_key == "KCTBS"
    assert sch_info["fonts"]["display"] == "Barlow"

    # KCLAS brief
    raw_kclas = """
    Title: Literature Festival 2026
    Organizer: Kumaraguru College of Liberal Arts and Science
    """
    brief_kclas = BriefExtractor().extract(raw_kclas)
    sch_key, sch_info = resolve_school(brief_kclas)
    assert sch_key == "KCLAS"

    # Default anchor school: KCT
    raw_kct = """
    Title: Tech Innovate 2026
    Organizer: Google Developer Groups On Campus • KCT, Coimbatore
    """
    brief_kct = BriefExtractor().extract(raw_kct)
    sch_key, sch_info = resolve_school(brief_kct)
    assert sch_key == "KCT"


def test_resolve_canvas_dimensions_from_brief():
    # Default when absent: 1080x1920 (9:16 story)
    raw_no_format = "Title: GDG Recruitment 2026\nOrganizer: GDG KCT"
    brief_no_format = BriefExtractor().extract(raw_no_format)
    w, h = resolve_canvas_dimensions(brief_no_format)
    assert (w, h) == (1080.0, 1920.0)

    # Named formats
    assert resolve_canvas_dimensions("story") == (1080.0, 1920.0)
    assert resolve_canvas_dimensions("9:16") == (1080.0, 1920.0)
    assert resolve_canvas_dimensions("A3") == (842.0, 1191.0)
    assert resolve_canvas_dimensions("A4") == (595.0, 842.0)
    assert resolve_canvas_dimensions("square") == (1080.0, 1080.0)
    assert resolve_canvas_dimensions("1:1") == (1080.0, 1080.0)
    assert resolve_canvas_dimensions("4:5") == (1080.0, 1350.0)

    # Explicit WxH
    assert resolve_canvas_dimensions("1024 x 1536 px") == (1024.0, 1536.0)


def test_genre_policy_mapping():
    # Hiring / Recruitment -> institutional
    raw_hiring = """
    Title: We Are Hiring
    Section: OPEN POSITIONS
    Tagline: Join our developer community
    """
    brief_hiring = BriefExtractor().extract(raw_hiring)
    g_name, g_policy = resolve_genre(brief_hiring)
    assert g_name in ("hiring", "recruitment")
    assert g_policy["allow_pills"] is True
    assert g_policy["allow_banner_tab"] is True
    assert g_policy["allow_cards"] is True
    assert g_policy["allow_footer_bar"] is True
    assert g_policy["allow_qr"] is True

    # Cultural -> cultural
    raw_cultural = """
    Title: Grand Gaana Concert & Dance Fest
    Mood: energetic, cultural, live music
    """
    brief_cultural = BriefExtractor().extract(raw_cultural)
    g_name, g_policy = resolve_genre(brief_cultural)
    assert g_name == "cultural"
    assert g_policy["allow_pills"] is False
    assert g_policy["allow_banner_tab"] is False
    assert g_policy["allow_cards"] is False
    assert g_policy["allow_footer_bar"] is True
    assert g_policy["allow_qr"] is True


def test_school_display_font_selection():
    # KCTBS display voice is Barlow
    fonts_kctbs = audit_fonts(school="KCTBS")
    assert fonts_kctbs["display"] == "Barlow"

    # KCT display voice is Montserrat
    fonts_kct = audit_fonts(school="KCT")
    assert fonts_kct["display"] == "Montserrat"

    # Tamil font is Noto Sans Tamil
    assert fonts_kct["tamil"] == "Noto Sans Tamil"


def test_structural_rows_emission_and_manifest(tmp_path):
    vc = VectorCraftRenderer()
    vc.new_document(width=1080.0, height=1920.0, units="Points", color_mode="rgb", raster_resolution=300)

    # 1. Logo row
    raw_brief = """
    Title: We Are Recruiting
    Organizer: GDG KCT
    Partner: Kumaraguru Institutions
    CTA: Apply Online
    QR Link: https://forms.example/apply
    Closing line: BE THE CHANGE. JOIN GDG KCT!
    """
    brief = BriefExtractor().extract(raw_brief)
    sch_key, sch_info = resolve_school(brief)
    logo_res = emit_logo_row(vc, brief, sch_info, width=1080.0, height=1920.0, margin_x=48.0, margin_y=86.0)
    assert len(logo_res) >= 1

    # 2. Banner tab row
    _, tab_res = emit_banner_tab_row(
        vc, text="LEARN / BUILD / GROW", width=1080.0, height=1920.0,
        font="Montserrat", fill_color="#1E2842", y=86.0,
    )
    assert tab_res["role"] == "_structure_banner_tab"

    # 3. Pill row
    pill_res = emit_pill_row(
        vc, text="TIME TO FILL: MONDAY", x=540.0, y=1400.0,
        font="Inter", fill_color="#4285F4", role="_structure_pill",
    )
    assert pill_res["role"] == "_structure_pill"

    # 4. QR row
    qr_res = emit_qr_row(
        vc, qr_link="https://forms.example/apply", cta_text="SCAN TO APPLY",
        x=800.0, y=1600.0, qr_size=90.0, run_dir=tmp_path,
    )
    assert qr_res["role"] == "_structure_qr"
    assert Path(qr_res["qr_path"]).exists()

    # 5. Footer bar row
    footer_res = emit_footer_bar_row(
        vc, text="BE THE CHANGE. JOIN GDG KCT!", width=1080.0, height=1920.0,
        font="Inter", fill_color="#1E2842",
    )
    assert footer_res["role"] == "_structure_footer"

    # Execute headless and inspect text_manifest roles
    res = vc.execute(work_dir=tmp_path)
    assert res.success is True

    manifest_roles = [t.get("role") for t in vc.text_manifest]
    assert "_structure_banner_tab" in manifest_roles
    assert "_structure_pill" in manifest_roles
    assert "_structure_qr" in manifest_roles
    assert "_structure_footer" in manifest_roles


def test_composer_per_genre_policy(tmp_path):
    bg_path = tmp_path / "bg.png"
    Image.new("RGB", (1080, 1920), "#FFFFFF").save(bg_path)

    # 1. Institutional / Hiring brief -> pill emitted for CTA
    raw_hiring = """
    Title: We Are Recruiting
    Eyebrow: LEARN / BUILD / GROW
    CTA: Apply Online
    Closing: BE THE CHANGE
    """
    brief_hiring = BriefExtractor().extract(raw_hiring)
    vc_hiring = compose(
        brief=brief_hiring,
        palette=["#FFFFFF", "#4285F4", "#0B2A5B", "#EA4335", "#1E2842"],
        bg_path=bg_path,
        width=1080.0,
        height=1920.0,
    )
    res_hiring = vc_hiring.execute(work_dir=tmp_path)
    assert res_hiring.success is True
    roles_hiring = [t.get("role") for t in vc_hiring.text_manifest]
    # Pill emitted for CTA in institutional genre
    assert "_structure_pill" in roles_hiring

    # 2. Cultural brief -> NO pills emitted (clean editorial doctrine preserved)
    raw_cultural = """
    Title: Grand Gaana Music Fest
    Mood: cultural, orchestral, pure art
    CTA: Entry by Passes
    """
    brief_cultural = BriefExtractor().extract(raw_cultural)
    vc_cultural = compose(
        brief=brief_cultural,
        palette=["#FFFFFF", "#4285F4", "#0B2A5B", "#EA4335", "#1E2842"],
        bg_path=bg_path,
        width=1080.0,
        height=1920.0,
    )
    res_cultural = vc_cultural.execute(work_dir=tmp_path)
    assert res_cultural.success is True
    roles_cultural = [t.get("role") for t in vc_cultural.text_manifest]
    assert "_structure_pill" not in roles_cultural


def test_mock_pipeline_renders_at_canvas_dimensions_and_passes_stage6(tmp_path):
    raw_brief = """
    Format: 1080 x 1920 px (9:16 portrait)
    Title: We Are Recruiting
    Eyebrow: LEARN / BUILD / GROW
    Tagline: REAL PEOPLE. REAL PROJECTS. REAL IMPACT.
    Subtitle: Join GDG KCT On Campus and be a part of a community that builds!
    Date: 03/11/2026, 11:59 PM
    Venue: Online & Campus Lab
    CTA: Scan to Apply
    QR link: https://forms.example/apply
    Closing line: BE THE CHANGE. JOIN GDG KCT!
    Organizer: Google Developer Groups On Campus • KCT, Coimbatore
    Partner: KUMARAGURU Institutions
    Mood: clean, friendly, energetic, student tech community, light background
    Palette: #FFFFFF #0B2A5B #4285F4 #EA4335 #FBBC05 #34A853 #E8F0FE #E6F4EA
    """
    pipeline = UnifiedPosterPipeline(
        run_id="test_house_style_mock_story",
        output_base="runs",
        use_mock=True,
    )
    brief = BriefExtractor().extract(raw_brief)
    res = pipeline.execute(brief)

    assert res["score"] >= 8
    # 9:16 story (1080x1920) rendered at 2x: exactly 2160x3840
    with Image.open(res["png_2x"]) as im:
        assert im.size == (2160, 3840)


def test_mock_pipeline_defaults_to_story_9_16_when_no_format_specified(tmp_path):
    raw_brief = """
    Title: We Are Recruiting
    Eyebrow: LEARN / BUILD / GROW
    Tagline: REAL PEOPLE. REAL PROJECTS. REAL IMPACT.
    Subtitle: Join GDG KCT On Campus and be a part of a community that builds!
    Date: 03/11/2026, 11:59 PM
    Venue: Online & Campus Lab
    CTA: Scan to Apply
    QR link: https://forms.example/apply
    Closing line: BE THE CHANGE. JOIN GDG KCT!
    Organizer: Google Developer Groups On Campus • KCT, Coimbatore
    Partner: KUMARAGURU Institutions
    Mood: clean, friendly, energetic, student tech community, light background
    Palette: #FFFFFF #0B2A5B #4285F4 #EA4335 #FBBC05 #34A853 #E8F0FE #E6F4EA
    """
    pipeline = UnifiedPosterPipeline(
        run_id="test_house_style_mock_no_format",
        output_base="runs",
        use_mock=True,
    )
    brief = BriefExtractor().extract(raw_brief)
    res = pipeline.execute(brief)

    assert res["score"] >= 8
    # Absent format defaults to 9:16 story (1080x1920), rendered at 2x: 2160x3840
    with Image.open(res["png_2x"]) as im:
        assert im.size == (2160, 3840)

