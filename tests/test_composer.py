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
