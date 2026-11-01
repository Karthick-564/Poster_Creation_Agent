"""Unit tests for Archetype-Native VectorCraft Poster Composer (Phase C).

Covers:
- Typographic plan builder respecting scalar margins (>= 40px equivalent)
- Archetype forcing via POSTER_FORCE_ARCHETYPE environment variable
- Empty-text guard ensuring blank strings are skipped without generating text commands
- Sparse brief handling (no gap placeholders when events/prize/cta omitted)
- Runtime font auditing with graceful fallback
- All 4 archetype composers compiling cleanly
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
    compose,
    compose_focal_point,
    compose_z_pattern,
    compose_split,
    compose_grid_3col,
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
def sample_brief() -> ExtractedBrief:
    raw = """
    Event: NOVA CTF 2026
    Tagline: National Inter-College Cybersecurity Battle
    Subtitle: 48-Hour Defensive Hackathon
    Date: October 24-25, 2026
    Time: 09:00 AM IST
    Venue: KCT Tech Park
    Events: Binary Exploitation / Reverse Engineering / Web Security / Cryptography
    Prize: $10,000 Total Pool
    CTA: Register at ctf.kct.ac.in
    Organizer: Department of Computer Science
    Blurb: Elite collegiate offensive and defensive security teams compete across 48 continuous hours.
    """
    return BriefExtractor().extract(raw)


@pytest.fixture
def sparse_brief() -> ExtractedBrief:
    raw = """
    Event: AI SYMPOSIUM 2026
    Date: November 12, 2026
    Venue: Hall A, Main Campus
    """
    return BriefExtractor().extract(raw)


@pytest.fixture
def pathological_brief() -> ExtractedBrief:
    raw = """
    Event: INTERNATIONAL SUSTAINABLE CIRCULAR BIOECONOMY SUMMIT & EXPO 2027
    Tagline: Accelerating Global Decarbonization Through Regenerative Systems Engineering And Deep Tech Solutions
    Subtitle: 48-Hour High-Intensity Inter-Disciplinary Collaborative Challenge
    Date: March 28-30, 2027 | 08:30 AM - 07:30 PM IST (GMT+5:30)
    Time: 08:30 AM - 07:30 PM IST
    Venue: Dr. APJ Abdul Kalam International Convention & Exhibition Centre, Innovation Park Campus
    Events: Bio-Materials Track / Circular Supply Chains / Carbon Sequestration / Climate FinTech Hack
    Prize: Total Innovation Grant Pool Of Rs 10,00,000 Plus Incubation Support
    CTA: Register Online Immediately At https://bioeconomy2027.example.org/apply
    Organizer: Department of Sustainable Engineering & Global Climate Action Network
    Blurb: Bringing together visionary students, faculty, and industry pioneers to build scalable bio-based technologies.
    """
    return BriefExtractor().extract(raw)


@pytest.fixture
def default_palette() -> list[str]:
    return ["#070B19", "#00F5D4", "#00BBF9", "#FEE440", "#FFFFFF"]


def test_plan_builder_respects_scalar_margins(sample_brief, default_palette):
    """Verify that typography plan obeys minimum margin (>= 40px equivalent) and relative scaling."""
    plan = build_typography_plan(sample_brief, default_palette, width=1080, height=1350)
    assert plan.margin >= 40.0
    assert plan.canvas_width == 1080
    assert plan.canvas_height == 1350

    # Check headline sizing relative to canvas height (>= canvas_h / 11.5)
    title_row = plan.get_row("title")
    assert title_row is not None
    assert title_row.size >= 72.0
    assert title_row.color == "#FFFFFF"

    # Scaled canvas check (e.g. A2-like or 2x dimensions: 2160 x 2700)
    plan_large = build_typography_plan(sample_brief, default_palette, width=2160, height=2700)
    assert plan_large.margin >= 80.0
    large_title = plan_large.get_row("title")
    assert large_title.size > title_row.size


def test_empty_text_guard_and_sparse_brief(sparse_brief, default_palette):
    """Verify that absent optional fields (events, prize, cta, blurb) produce NO gap placeholders."""
    plan = build_typography_plan(sparse_brief, default_palette, width=1080, height=1350)
    # Required rows present
    assert plan.get_row("title") is not None
    assert plan.get_row("date_time") is not None
    assert plan.get_row("venue") is not None

    # Optional rows must NOT exist (no dummy placeholder text)
    assert plan.get_row("events") is None
    assert plan.get_row("prize") is None
    assert plan.get_row("cta") is None
    assert plan.get_row("blurb") is None
    assert plan.get_row("organizer") is None

    # Verify composer builds compact layout without failure
    vc = compose(
        brief=sparse_brief,
        palette=default_palette,
        bg_path=Path("dummy_bg.png"),
        hero_path=Path("dummy_hero.png"),
        archetype="focal_point",
    )
    # Ensure no empty text strings in emitted commands
    text_commands = [c for c in vc.commands if c["command"] == "text.create"]
    assert len(text_commands) > 0
    for cmd in text_commands:
        txt = cmd["params"]["text"]
        assert txt is not None
        assert txt.strip() != "", f"Empty text emitted: {cmd}"
        # Ensure no hardcoded subfooter
        assert "Official National Circuit" not in txt


def test_archetype_forcing_via_env_var(sample_brief, default_palette, monkeypatch):
    """Verify that POSTER_FORCE_ARCHETYPE overrides archetype parameter."""
    monkeypatch.setenv("POSTER_FORCE_ARCHETYPE", "split")
    vc = compose(
        brief=sample_brief,
        palette=default_palette,
        bg_path=Path("dummy_bg.png"),
        hero_path=Path("dummy_hero.png"),
        archetype="focal_point",  # Should be overridden by env var to split
    )
    # Split layout creates lower solid background rectangle and soft scrim
    scrim_commands = [
        c for c in vc.commands
        if c["command"] == "paint.setFill" and "gradient" in c["params"]
    ]
    assert len(scrim_commands) > 0


def test_all_four_archetypes_emit_valid_command_stream(sample_brief, default_palette):
    """Verify that all 4 archetypes compile valid VectorCraft command streams."""
    archetypes = ["focal_point", "z_pattern", "split", "grid_3col"]

    for arch in archetypes:
        vc = compose(
            brief=sample_brief,
            palette=default_palette,
            bg_path=Path("dummy_bg.png"),
            hero_path=Path("dummy_hero.png"),
            archetype=arch,
        )
        assert len(vc.commands) > 10, f"Archetype {arch} generated too few commands ({len(vc.commands)})"

        # Check document initialization
        assert vc.commands[0]["command"] == "file.new"

        # Check background image placement at Layer 0
        place_cmds = [c for c in vc.commands if c["command"] == "file.place"]
        assert len(place_cmds) >= 2, f"Expected bg and hero placement for {arch}, got {len(place_cmds)}"

        # Check text creation
        text_cmds = [c for c in vc.commands if c["command"] == "text.create"]
        assert len(text_cmds) >= 3, f"Expected text commands for {arch}, got {len(text_cmds)}"


def test_font_audit_graceful_degradation(monkeypatch, tmp_path):
    """Verify font auditing returns safe fallbacks when shared fonts dir is empty."""
    monkeypatch.setenv("VECTORCRAFT_CONFIG_DIR", str(tmp_path))
    fonts = audit_fonts()
    assert "display" in fonts
    assert "sans" in fonts
    assert "mono" in fonts
    assert fonts["display"] in ("Inter", "Bahnschrift", "Arial")
    assert fonts["mono"] in ("JetBrains Mono", "Consolas")


def test_scrim_gradient_edge_stops_terminate_at_zero_opacity(sample_brief, default_palette):
    """Verify that every gradient scrim across all archetypes ends at opacity 0.0 at the outer edge."""
    for arch in ["focal_point", "z_pattern", "split", "grid_3col"]:
        vc = compose(
            brief=sample_brief,
            palette=default_palette,
            bg_path=Path("dummy_bg.png"),
            hero_path=Path("dummy_hero.png"),
            archetype=arch,
        )
        scrim_cmds = [
            c for c in vc.commands
            if c["command"] == "paint.setFill" and "gradient" in c["params"]
        ]
        assert len(scrim_cmds) > 0, f"Archetype {arch} has no gradient scrims"
        for cmd in scrim_cmds:
            grad = cmd["params"]["gradient"]
            stops = grad["stops"]
            assert len(stops) >= 2, f"Gradient has <2 stops: {grad}"
            assert stops[-1]["opacity"] == 0.0, (
                f"Outer stop does not terminate at 0.0 opacity in {arch}: {stops[-1]}"
            )


def test_cross_row_band_overlap_resolution(pathological_brief, default_palette):
    """Verify that layout composers prevent vertical/horizontal overlap in dense/pathological content."""
    # 1. Focal point: headline height respected; tagline below headline; hero below tagline
    vc_fp = compose(
        brief=pathological_brief,
        palette=default_palette,
        bg_path=Path("dummy_bg.png"),
        hero_path=Path("dummy_hero.png"),
        archetype="focal_point",
    )
    places_fp = [c["params"] for c in vc_fp.commands if c["command"] == "file.place"]
    headline_cmd = next(c for c in vc_fp.commands if c["command"] == "text.create" and "INTERNATIONAL SUSTAINABLE" in c["params"]["text"].upper())
    tagline_cmd = next(c for c in vc_fp.commands if c["command"] == "text.create" and "ACCELERATING GLOBAL" in c["params"]["text"].upper())
    assert tagline_cmd["params"]["y"] > headline_cmd["params"]["y"] + 200, (
        f"Tagline y={tagline_cmd['params']['y']} overlaps or is too close to headline y={headline_cmd['params']['y']}"
    )
    hero_place = places_fp[1]
    assert hero_place["rect"][1] >= tagline_cmd["params"]["y"] + 20, (
        f"Hero y={hero_place['rect'][1]} overlaps tagline y={tagline_cmd['params']['y']}"
    )

    # 2. Z-pattern: top band organizer mark and date badge are vertically stacked when wide
    vc_zp = compose(
        brief=pathological_brief,
        palette=default_palette,
        bg_path=Path("dummy_bg.png"),
        hero_path=Path("dummy_hero.png"),
        archetype="z_pattern",
    )
    org_cmd = next(c for c in vc_zp.commands if c["command"] == "text.create" and "SUSTAINABLE ENGINEERING" in c["params"]["text"].upper())
    date_cmd = next(c for c in vc_zp.commands if c["command"] == "text.create" and "MARCH 28-30" in c["params"]["text"].upper())
    assert abs(org_cmd["params"]["y"] - date_cmd["params"]["y"]) >= 20.0, (
        f"Z-pattern top band rows collide at same y! org_y={org_cmd['params']['y']}, date_y={date_cmd['params']['y']}"
    )

    # 3. Z-pattern: bottom band elements (events, venue, prize, cta) must have non-overlapping y-slots
    venue_cmd = next(c for c in vc_zp.commands if c["command"] == "text.create" and "ABDUL KALAM" in c["params"]["text"].upper())
    prize_cmd = next(c for c in vc_zp.commands if c["command"] == "text.create" and "INNOVATION GRANT POOL" in c["params"]["text"].upper())
    cta_cmd = next(c for c in vc_zp.commands if c["command"] == "text.create" and "BIOECONOMY2027" in c["params"]["text"].upper())
    assert prize_cmd["params"]["y"] >= venue_cmd["params"]["y"] + 20.0, f"Prize overlaps venue: prize_y={prize_cmd['params']['y']}, venue_y={venue_cmd['params']['y']}"
    assert cta_cmd["params"]["y"] >= prize_cmd["params"]["y"] + 20.0, f"CTA overlaps prize: cta_y={cta_cmd['params']['y']}, prize_y={prize_cmd['params']['y']}"


def test_canvas_bounds_overflow_detection(tmp_path):
    """Verify that VectorCraftRenderer flags text that escapes canvas margin boundaries."""
    if not CLI_PATH.exists():
        pytest.skip("VectorCraft CLI binary not found")

    renderer = VectorCraftRenderer(cli_path=CLI_PATH)
    renderer.new_document(width=1080, height=1350)
    renderer.add_text(
        text="EXTRA LONG ESCAPING STRING THAT RUNS PAST THE RIGHT CANVAS MARGIN",
        x=900,
        y=200,
        size=24,
        font="Arial",
        color="#FFFFFF",
        role="overflow_test_right",
    )
    renderer.add_text(
        text="ESCAPING LEFT",
        x=10,
        y=400,
        size=18,
        font="Arial",
        color="#FFFFFF",
        role="overflow_test_left",
    )
    png_out = tmp_path / "bounds_test.png"
    res = renderer.execute(output_png=png_out, work_dir=tmp_path)
    assert res.success

    manifest = res.text_manifest
    assert len(manifest) == 2
    right_item = next(m for m in manifest if m["role"] == "overflow_test_right")
    assert right_item["overflow"] is not None
    assert any("right_margin_escape" in reason for reason in right_item["overflow"])

    left_item = next(m for m in manifest if m["role"] == "overflow_test_left")
    assert left_item["overflow"] is not None
    assert any("left_margin_escape" in reason for reason in left_item["overflow"])


def test_pathological_brief_headless_all_archetypes(pathological_brief, default_palette, tmp_path):
    """Verify that all 4 archetypes render end-to-end with ZERO bounds escapes or collisions on pathological brief."""
    if not CLI_PATH.exists():
        pytest.skip("VectorCraft CLI binary not found")

    bg_path = tmp_path / "bg.png"
    hero_path = tmp_path / "hero.png"
    Image.new("RGBA", (1080, 1350), (10, 15, 25, 255)).save(bg_path)
    Image.new("RGBA", (600, 600), (0, 200, 150, 255)).save(hero_path)

    for arch in ["focal_point", "z_pattern", "split", "grid_3col"]:
        vc = compose(
            brief=pathological_brief,
            palette=default_palette,
            bg_path=bg_path,
            hero_path=hero_path,
            archetype=arch,
        )
        vc.cli_path = CLI_PATH
        out_png = tmp_path / f"render_{arch}.png"
        res = vc.execute(output_png=out_png, work_dir=tmp_path)

        assert res.success, f"Render failed for {arch}: {res.error_message}"
        assert out_png.exists()

        for item in res.text_manifest:
            assert item["overflow"] is None, (
                f"Defect found in {arch}: node {item['id']} ({item['role']}) has overflow: {item['overflow']}"
            )

