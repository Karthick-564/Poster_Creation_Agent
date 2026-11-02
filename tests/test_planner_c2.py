"""Unit and integration tests for Phase C2 Two-Call Planner and Schema Enforcement."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest
from PIL import Image

from poster_agent.gemini_client import (
    GeminiClient,
    CONCEPT_SCHEMA,
    LAYOUT_SCHEMA,
    AVAILABLE_ARCHETYPES,
    AVAILABLE_MOVEMENTS,
    AVAILABLE_BLEND_MODES,
    AVAILABLE_ROLES,
    AVAILABLE_TREATMENTS,
    validate_concept_plan,
    validate_layout_plan,
    validate_repair_plan,
)
from poster_agent.vision.bg_measurer import measure_background
from poster_agent.renderer.composer import MICROCOPY_ALLOWLIST
from poster_agent.unified_pipeline import UnifiedPosterPipeline


def get_valid_concept_fixture() -> dict:
    return {
        "thesis": "Circular sustainability hackathon empowering youth innovation.",
        "archetype": "focal_point",
        "archetype_rationale": "Central hero commanding the composition.",
        "movement": "orbital",
        "light_plan": {
            "key_direction": "top_left",
            "key_intensity": 85,
            "fill_intensity": 40,
            "rim": {"enabled": True, "color_hex": "#00F5D4"},
            "notes": "Directional rim light from top left",
        },
        "palette": {
            "bg_60": "#070B19",
            "hero_30": "#00F5D4",
            "accent_10": "#FEE440",
            "notes": "60/30/10 compliant palette",
        },
        "typography": {
            "body_stance": "Swiss clean grotesque",
            "tracking_stance": "Wide uppercase tracking",
        },
        "accent_row_choice": "Grand prize ribbon and register CTA",
        "assets": {
            "hero": {
                "ideogram_caption": "3D organic crystalline core",
                "negative_caption": "text, letters, numbers, words, watermark",
                "aspect": "4:5",
            },
            "background": {
                "ideogram_caption": "Atmospheric mist and fiber optics backdrop",
            },
            "accents": [
                {"id": "accent_glow", "ideogram_caption": "Subtle radial cyan light spill"}
            ],
        },
        "calm_regions_requested": [
            [0, 0, 350, 1000],
            [680, 0, 1000, 1000],
        ],
        "self_check": {
            "assumptions": "Standard mock run parameters",
            "unsupported_artifacts": [],
        },
    }


def get_valid_layout_fixture() -> dict:
    return {
        "slots": [
            {
                "row_id": "title_main",
                "role": "headline",
                "zone": [120, 60, 240, 940],
                "justify": "center",
                "align": "middle",
                "size_class": "headline",
                "font": "Inter",
                "treatment": "none",
                "max_lines": 1,
            },
            {
                "row_id": "date_main",
                "role": "subhead",
                "zone": [720, 60, 780, 940],
                "justify": "center",
                "align": "middle",
                "size_class": "subhead",
                "font": "Inter",
                "treatment": "none",
                "max_lines": 1,
            },
            {
                "row_id": "cta_main",
                "role": "cta",
                "zone": [900, 60, 950, 940],
                "justify": "center",
                "align": "middle",
                "size_class": "body",
                "font": "Inter",
                "treatment": "none",
                "max_lines": 1,
            },
        ],
        "layer_plan": [
            {"asset": "bg", "z": 0, "blend": "normal", "opacity": 100},
            {"asset": "hero", "z": 3, "blend": "screen", "opacity": 90},
        ],
        "scrims": [
            {
                "zone": [650, 0, 1000, 1000],
                "direction": "to_bottom",
                "opacity_start": 0.0,
                "opacity_end": 0.75,
            }
        ],
        "checks": [
            {"id": "c1", "assertion": "Headline fits in calm top zone"}
        ],
        "calm_regions_used": [
            [0, 0, 350, 1000],
            [680, 0, 1000, 1000],
        ],
        "rationale": "High-contrast layout placing text in upper and lower calm bands.",
    }


# 1. Concept + Layout Schema Validators
def test_concept_schema_validator_accepts_valid():
    fixture = get_valid_concept_fixture()
    ok, err = validate_concept_plan(fixture)
    assert ok, f"Expected valid, got error: {err}"


def test_concept_schema_validator_rejects_enum_and_coords():
    fixture = get_valid_concept_fixture()
    fixture["archetype"] = "invalid_archetype"
    ok, err = validate_concept_plan(fixture)
    assert not ok
    assert "Invalid archetype" in err

    fixture = get_valid_concept_fixture()
    fixture["light_plan"]["key_direction"] = "diagonal_somewhere"
    ok, err = validate_concept_plan(fixture)
    assert not ok
    assert "Invalid key_direction" in err

    fixture = get_valid_concept_fixture()
    fixture["calm_regions_requested"] = [[500, 100, 200, 900]]  # y0 > y1 inverted
    ok, err = validate_concept_plan(fixture)
    assert not ok
    assert "inverted" in err.lower() or "coordinates" in err.lower()


def test_layout_schema_validator_accepts_valid():
    fixture = get_valid_layout_fixture()
    ok, err = validate_layout_plan(fixture, available_fonts=["Inter", "JetBrainsMono"])
    assert ok, f"Expected valid, got error: {err}"


def test_layout_schema_validator_rejects_duplicates_and_unknown_fonts():
    fixture = get_valid_layout_fixture()
    # Duplicate row_id
    fixture["slots"].append({
        "row_id": "title_main",
        "role": "headline",
        "zone": [300, 60, 400, 940],
        "justify": "center",
        "align": "middle",
        "size_class": "headline",
        "font": "Inter",
        "treatment": "none",
        "max_lines": 1,
    })
    ok, err = validate_layout_plan(fixture)
    assert not ok
    assert "Duplicate row_id" in err

    fixture = get_valid_layout_fixture()
    fixture["slots"][0]["font"] = "UnknownFontExtra"
    ok, err = validate_layout_plan(fixture, available_fonts=["Inter"])
    assert not ok
    assert "not in available_fonts" in err


def test_repair_plan_schema_validator():
    repair_fixture = {
        "operations": [
            {"op": "resize", "target_id": "title_main", "params": {"scale": 0.9}, "reason": "Slight margin crowding"},
            {"op": "rescrim", "target_id": "footer_scrim", "params": {"opacity": 0.8}, "reason": "WCAG contrast boost"},
        ],
        "notes": "Phase D repair operations",
    }
    ok, err = validate_repair_plan(repair_fixture)
    assert ok, err

    bad_fixture = {"operations": [{"op": "invalid_op", "target_id": "x", "params": {}, "reason": "y"}], "notes": "z"}
    bad_ok, bad_err = validate_repair_plan(bad_fixture)
    assert not bad_ok


# 2. Fake GeminiClient returning garbage -> 1 retry -> PLANNING_FALLBACK state
def test_gemini_client_retry_and_explicit_failure():
    client = GeminiClient(api_key="fake-test-key")
    call_count = 0

    def fake_call(model, payload, timeout=30):
        nonlocal call_count
        call_count += 1
        return {"candidates": [{"content": {"parts": [{"text": "THIS IS NOT JSON"}]}}]}

    client._call_api = fake_call
    result = client.generate_json(prompt="Test prompt", timeout=5)
    # Must attempt exactly 2 times (initial + 1 bounded retry)
    assert call_count == 2
    assert isinstance(result, dict)
    assert "error" in result
    assert "failed after retry" in result["error"].lower()


def _save_noise_png(path, size, mode):
    """Random-noise PNG — large enough to pass the live-mode min-size gate (>30KB)."""
    rng = np.random.default_rng(42)
    channels = 4 if mode == "RGBA" else 3
    arr = rng.integers(0, 256, size=(size[1], size[0], channels), dtype=np.uint8)
    Image.fromarray(arr, mode).save(path)


def test_mock_pipeline_never_consults_planner_and_writes_plan():
    """Mock mode: the canned plan is unconditional — the Gemini client must NEVER be
    called and PLANNING_FALLBACK must remain unset (mock can't fail planning)."""
    pipeline = UnifiedPosterPipeline(run_id="test_mock_canned_run", use_mock=True)
    fake_client = MagicMock()
    pipeline.gemini = fake_client

    brief_text = "Title: SUSTAINABLE CITY 2027\nDate: MARCH 20\nVenue: EXPO HALL"
    try:
        res = pipeline.execute(brief_text=brief_text)
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"Windows-host_required: WSL path-interop at render stage ({e})")
        raise
    assert res is not None
    fake_client.generate_json.assert_not_called()
    assert pipeline.planning_fallback is None
    assert (pipeline.run_dir / "plan.json").exists()


def test_live_pipeline_halt_on_failed_concept_call(monkeypatch):
    """Live mode + failed planner concept call -> honest PLANNING_HALT.
    No canned poster, no silent fallback, plan.json never written."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    pipeline = UnifiedPosterPipeline(run_id="test_halt_concept_run", use_mock=False)
    fake_client = MagicMock()
    fake_client.generate_json.return_value = {"error": "simulated API down"}
    pipeline.gemini = fake_client

    brief_text = "Title: HALT PROOF\nDate: APRIL 2\nVenue: TEST HALL"
    with pytest.raises(RuntimeError, match="PLANNING_HALT"):
        pipeline.execute(brief_text=brief_text)
    fake_client.generate_json.assert_called_once()
    assert not (pipeline.run_dir / "plan.json").exists()


def test_live_pipeline_halt_on_layout_failure_after_valid_concept(monkeypatch):
    """Live mode: valid concept, then failed layout call at Stage 4.5 -> honest PLANNING_HALT.
    Hero/background generators stubbed with deterministic dummy art (no ComfyUI/Ideogram).
    NOTE (environment limitation): the layout-failure code path mirrors the concept-failure
    path exactly; this test exercises the full live chain to Stage 4.5."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    pipeline = UnifiedPosterPipeline(run_id="test_halt_layout_run", use_mock=False)

    # Stub generators: noise art passes the live min-size gate deterministically
    fake_comfy = MagicMock()

    def fake_hero(prompt, output_path, **kw):
        _save_noise_png(output_path, (768, 768), "RGBA")

    def fake_bg(description, palette, output_path, **kw):
        _save_noise_png(output_path, (1080, 1350), "RGB")

    fake_comfy.is_alive.return_value = True
    fake_comfy.generate_qwen_rgba.side_effect = fake_hero
    fake_comfy.generate_ideogram_background.side_effect = fake_bg
    pipeline.comfy = fake_comfy

    # Planner: call #1 returns a valid concept; call #2 (layout) fails
    responses = [get_valid_concept_fixture(), {"error": "simulated API down"}]
    fake_gemini = MagicMock()
    fake_gemini.generate_json = MagicMock(side_effect=lambda **kw: responses.pop(0))
    pipeline.gemini = fake_gemini

    brief_text = "Title: LAYOUT HALT PROOF\nDate: APRIL 3\nVenue: TEST HALL"
    with pytest.raises(RuntimeError, match="PLANNING_HALT"):
        pipeline.execute(brief_text=brief_text)
    assert fake_gemini.generate_json.call_count == 2
    assert not (pipeline.run_dir / "plan.json").exists()


# 3. Composer slot execution: undersized slot clamped, unknown font & degenerate zone fallback
def test_composer_slot_execution_floors_and_fallbacks(capsys, tmp_path):
    from poster_agent.renderer.composer import compose_slots, build_typography_plan
    from poster_agent.renderer.vectorcraft_renderer import VectorCraftRenderer
    from poster_agent.ingestion.extractor import ExtractedBrief, VerbatimField

    brief = ExtractedBrief(
        fields={
            "title": VerbatimField(key="title", text="ROBO CONVERGENCE", source="brief"),
            "date": VerbatimField(key="date", text="OCTOBER 24", source="brief"),
            "venue": VerbatimField(key="venue", text="CENTRAL HUB", source="brief"),
        }
    )
    plan = build_typography_plan(
        brief=brief,
        palette=["#070B19", "#00F5D4", "#FEE440", "#C8553D", "#FFFFFF"],
        width=1080,
        height=1350,
    )
    # Manually make title row undersized
    for r in plan.rows:
        if r.role == "title":
            r.size = 35.0  # severely undersized < 72pt floor

    layout_plan = {
        "slots": [
            {
                "row_id": "title",
                "role": "headline",
                "zone": [100, 50, 300, 950],
                "justify": "center",
                "align": "middle",
                "size_class": "headline",
                "font": "AlienFontXYZ",  # Unknown font
                "treatment": "none",
                "max_lines": 1,
            },
            {
                "row_id": "date_time",
                "role": "body",
                "zone": [500, 500, 505, 505],  # Degenerate zone (<30px width, <15px height)
                "justify": "center",
                "align": "middle",
                "size_class": "body",
                "font": "Inter",
                "treatment": "none",
                "max_lines": 1,
            },
        ],
        "scrims": [],
    }

    # Synthetic dummy images for paths
    bg_p = tmp_path / "bg.png"
    hero_p = tmp_path / "hero.png"
    Image.new("RGB", (100, 100), "#070B19").save(bg_p)
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(hero_p)

    vc = VectorCraftRenderer()
    vc.new_document(width=1080, height=1350, units="Points", color_mode="rgb", raster_resolution=300)

    composed_vc = compose_slots(
        vc=vc,
        brief=brief,
        palette=["#070B19", "#00F5D4", "#FEE440", "#C8553D", "#FFFFFF"],
        plan=plan,
        bg_path=bg_p,
        hero_path=hero_p,
        layout_plan=layout_plan,
        archetype="focal_point",
        width=1080,
        height=1350,
    )
    assert composed_vc is not None
    out, err = capsys.readouterr()

    headline_floor = 1350.0 / 11.0  # ~122.7pt doctrine floor

    # Verify clamped VALUE (doctrine floor), unknown font fallback, degenerate zone fallback
    assert "doctrine floor" in out              # clamp was logged with the real floor value
    assert "to floor 72.0pt" not in out         # the old hardcoded floor is gone
    assert "not installed" in out or "AlienFontXYZ" in out
    assert "degenerate zone" in out
    # The queued title text must sit at-or-above the doctrine floor
    title_sizes = [
        t.get("size", 0.0)
        for t in composed_vc._queued_texts
        if t.get("role") == "title"
    ]
    assert title_sizes, "title row must be queued by compose_slots"
    assert all(s >= headline_floor - 1.0 for s in title_sizes), (
        f"title sizes {title_sizes} sit below the doctrine floor {headline_floor:.1f}pt"
    )


# 4. Zone -> pt conversion identity at boundaries
def test_zone_to_pt_conversion_identity():
    canvas_w = 1080.0
    canvas_h = 1350.0

    def zone_to_pt(zone, w=canvas_w, h=canvas_h):
        y0, x0, y1, x1 = zone
        return (y0 * h / 1000.0, x0 * w / 1000.0, y1 * h / 1000.0, x1 * w / 1000.0)

    # 0 -> 0
    top_left = zone_to_pt([0, 0, 100, 100])
    assert top_left[0] == 0.0
    assert top_left[1] == 0.0

    # 1000 -> full width / height
    bottom_right = zone_to_pt([900, 900, 1000, 1000])
    assert bottom_right[2] == canvas_h
    assert bottom_right[3] == canvas_w


# 5. plan.json written before Stage 5 in a mock run
def test_plan_json_written_before_stage5(tmp_path):
    pipeline = UnifiedPosterPipeline(
        run_id="test_plan_provenance",
        output_base="runs",
        use_mock=True,
    )
    brief_text = "Title: SOLAR SUMMIT\nDate: 10 OCT 2027\nVenue: AUDITORIUM A"
    try:
        res = pipeline.execute(brief_text=brief_text)
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"Windows-host_required: WSL path-interop at render stage ({e})")
        raise
    assert res is not None

    plan_path = pipeline.run_dir / "plan.json"
    assert plan_path.exists()
    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "concept" in data
    assert "layout" in data
    assert "measured_art" in data
    assert "allowlists" in data
    assert "microcopy" in data["allowlists"]


# 6. Copy-purge test: no brief field string outside allowlist appears as manufactured constant
def test_copy_purge_in_mock_run():
    pipeline = UnifiedPosterPipeline(run_id="test_copy_purge", use_mock=True)
    brief_text = "Title: CIRCULAR TECH\nDate: APRIL 15\nVenue: TECH PARK"
    try:
        res = pipeline.execute(brief_text=brief_text)
    except RuntimeError as e:
        if "The system cannot find the path specified" in str(e):
            pytest.skip(f"Windows-host_required: WSL path-interop at render stage ({e})")
        raise
    assert res is not None

    plan_path = pipeline.run_dir / "plan.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Inspect captions in plan.json
    concept = data["concept"]
    bg_caption = concept["assets"]["background"]["ideogram_caption"]
    # Background must not contain the verbatim title
    assert "CIRCULAR TECH" not in bg_caption


# 7. Background measurer on synthetic image
def test_background_measurer_synthetic_image():
    # Create synthetic image: top half flat dark (calm), bottom half noisy texture (busy/salient)
    H, W = 1350, 1080
    arr = np.zeros((H, W), dtype=np.uint8)
    arr[:600, :] = 20  # Flat dark
    np.random.seed(42)
    arr[600:, :] = np.random.randint(50, 250, size=(750, W), dtype=np.uint8)  # High noise

    im = Image.fromarray(arr)
    meas = measure_background(im, grid_cols=12, grid_rows=15)

    assert meas["grid_cols"] == 12
    assert meas["grid_rows"] == 15
    assert meas["counts"]["calm"] > 0
    assert meas["counts"]["busy"] + meas["counts"]["salient"] > 0

    # Check calm regions are valid in-bounds [0, 1000]
    for reg in meas["calm_regions"]:
        assert len(reg) == 4
        y0, x0, y1, x1 = reg
        assert 0 <= y0 < y1 <= 1000
        assert 0 <= x0 < x1 <= 1000
